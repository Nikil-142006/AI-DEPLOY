import os
import json
import tempfile
import asyncio
import aio_pika
import structlog
import datetime
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.builder import download_model_from_s3, build_and_push_image
from app.k8s_manager import deploy_model_to_k8s, undeploy_model_from_k8s

settings = get_settings()
log = structlog.get_logger()

# Setup MongoDB client
client = AsyncIOMotorClient(settings.MONGO_URI)
db = client.get_default_database()


async def update_model_status(model_id: str, status: str, **kwargs):
    values = {"status": status, "updated_at": datetime.datetime.utcnow(), **kwargs}
    await db.models.update_one({"_id": model_id}, {"$set": values})


async def log_event(model_id: str, event_type: str, status: str, message: str):
    from app.models import DeploymentEvent
    event = DeploymentEvent(
        model_id=model_id,
        event_type=event_type,
        status=status,
        message=message,
    )
    await db.deployment_events.insert_one(event.to_dict())


async def handle_build_job(message: aio_pika.IncomingMessage):
    async with message.process():
        body = json.loads(message.body.decode())
        model_id = body["model_id"]
        s3_path = body["s3_path"]
        framework = body["framework"]
        config = body["config"]

        log.info("build_job_started", model_id=model_id, framework=framework)

        try:
            # Update status → BUILDING
            await update_model_status(model_id, "BUILDING")
            await log_event(model_id, "BUILD_STARTED", "BUILDING", "Docker image build started")

            with tempfile.TemporaryDirectory() as tmpdir:
                build_dir = os.path.join(tmpdir, "build")
                os.makedirs(build_dir)
                model_dir = os.path.join(tmpdir, "model")
                os.makedirs(model_dir)

                # 1. Download model from S3
                model_local_path, model_filename = download_model_from_s3(s3_path, model_dir)

                # 2. Build and push Docker image
                ecr_image_uri = build_and_push_image(
                    model_id=model_id,
                    framework=framework,
                    model_local_path=model_local_path,
                    model_filename=model_filename,
                    build_dir=build_dir,
                )

            await update_model_status(model_id, "DEPLOYING", ecr_image_uri=ecr_image_uri)
            await log_event(model_id, "BUILD_COMPLETE", "SUCCESS", f"Image pushed: {ecr_image_uri}")

            # 3. Deploy to Kubernetes
            dep_name, svc_name = deploy_model_to_k8s(model_id, ecr_image_uri, config)

            await update_model_status(
                model_id, "DEPLOYED",
                k8s_deployment_name=dep_name,
                k8s_service_name=svc_name,
            )
            await log_event(model_id, "DEPLOY_COMPLETE", "SUCCESS",
                            f"Model deployed as {dep_name} in {settings.K8S_NAMESPACE}")
            log.info("model_deployed", model_id=model_id, deployment=dep_name)

        except Exception as e:
            log.error("build_job_failed", model_id=model_id, error=str(e))
            await update_model_status(model_id, "FAILED")
            await log_event(model_id, "BUILD_FAILED", "FAILED", str(e))


async def handle_undeploy_job(message: aio_pika.IncomingMessage):
    async with message.process():
        body = json.loads(message.body.decode())
        model_id = body["model_id"]
        dep_name = body["k8s_deployment_name"]
        namespace = body["k8s_namespace"]

        log.info("undeploy_job_started", model_id=model_id)
        try:
            undeploy_model_from_k8s(dep_name, namespace)
            await update_model_status(
                model_id, "UNDEPLOYED",
                k8s_deployment_name=None,
                k8s_service_name=None,
            )
            await log_event(model_id, "UNDEPLOY_COMPLETE", "SUCCESS",
                            f"Removed K8s resources: {dep_name}")
            log.info("model_undeployed", model_id=model_id)
        except Exception as e:
            log.error("undeploy_failed", model_id=model_id, error=str(e))
            await log_event(model_id, "UNDEPLOY_FAILED", "FAILED", str(e))


async def main():
    log.info("worker_service_starting")
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)

    build_queue = await channel.declare_queue("model.build", durable=True)
    undeploy_queue = await channel.declare_queue("model.undeploy", durable=True)

    await build_queue.consume(handle_build_job)
    await undeploy_queue.consume(handle_undeploy_job)

    log.info("worker_service_ready", queues=["model.build", "model.undeploy"])
    await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
