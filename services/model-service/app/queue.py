import json
import aio_pika
import structlog
from app.config import get_settings

settings = get_settings()
log = structlog.get_logger()

_connection = None
_channel = None


async def get_rabbitmq_channel() -> aio_pika.Channel:
    global _connection, _channel
    if _connection is None or _connection.is_closed:
        _connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    if _channel is None or _channel.is_closed:
        _channel = await _connection.channel()
    return _channel


async def publish_build_job(model_id: str, s3_path: str, framework: str, config: dict):
    """Publish a model build job to RabbitMQ for the worker service."""
    channel = await get_rabbitmq_channel()
    await channel.declare_queue("model.build", durable=True)

    message_body = {
        "model_id": model_id,
        "s3_path": s3_path,
        "framework": framework,
        "config": config,
    }

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message_body).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key="model.build",
    )
    log.info("build_job_published", model_id=model_id, framework=framework)


async def publish_undeploy_job(model_id: str, k8s_deployment_name: str, k8s_namespace: str, ecr_image_uri: str):
    """Publish an undeploy job to RabbitMQ."""
    channel = await get_rabbitmq_channel()
    await channel.declare_queue("model.undeploy", durable=True)

    message_body = {
        "model_id": model_id,
        "k8s_deployment_name": k8s_deployment_name,
        "k8s_namespace": k8s_namespace,
        "ecr_image_uri": ecr_image_uri,
    }

    await channel.default_exchange.publish(
        aio_pika.Message(
            body=json.dumps(message_body).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key="model.undeploy",
    )
    log.info("undeploy_job_published", model_id=model_id)


async def close_rabbitmq():
    global _connection, _channel
    if _channel and not _channel.is_closed:
        await _channel.close()
    if _connection and not _connection.is_closed:
        await _connection.close()
