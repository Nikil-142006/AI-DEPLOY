from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
import structlog

from app.database import get_db
from app.models import Model, DeploymentEvent
from app.schemas import (
    ModelResponse, ModelDetailResponse, ModelUpdateRequest,
    DeployRequest, MessageResponse, SUPPORTED_FRAMEWORKS, VALID_EXTENSIONS,
)
from app.storage import upload_model, delete_model, get_download_url
from app.queue import publish_build_job, publish_undeploy_job
from app.dependencies import get_current_user
from app.config import get_settings

settings = get_settings()
log = structlog.get_logger()
router = APIRouter(prefix="/models", tags=["Models"])


@router.post("/upload", response_model=ModelResponse, status_code=201)
async def upload_model_endpoint(
    name: str = Form(...),
    framework: str = Form(...),
    version: str = Form(default="1.0.0"),
    description: str = Form(default=""),
    file: UploadFile = File(...),
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Validate framework
    if framework not in SUPPORTED_FRAMEWORKS:
        raise HTTPException(400, f"Unsupported framework. Supported: {SUPPORTED_FRAMEWORKS}")

    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in VALID_EXTENSIONS[framework]:
        raise HTTPException(
            400,
            f"Invalid file type '{ext}' for {framework}. "
            f"Expected: {VALID_EXTENSIONS[framework]}"
        )

    # Validate file size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(413, f"File too large ({size_mb:.1f}MB). Max: {settings.MAX_UPLOAD_SIZE_MB}MB")

    # Create DB record first (get model ID for storage key)
    model = Model(
        name=name,
        framework=framework,
        version=version,
        description=description,
        owner_id=current_user.id,
        status="UPLOADING",
    )
    await db.models.insert_one(model.to_dict())

    # Upload using configured backend (local disk or S3)
    storage_key = f"models/{str(model.id)}/{file.filename}"
    try:
        storage_uri = await upload_model(contents, storage_key)
    except Exception as e:
        await db.models.delete_one({"_id": model.id})
        log.error("upload_failed", error=str(e), model_id=str(model.id))
        raise HTTPException(500, "Failed to upload model to storage")

    # In LOCAL mode: automatically mark the model as DEPLOYED so inference works immediately.
    # In S3 mode: stays as UPLOADED (worker handles building & deploying to Kubernetes).
    if settings.STORAGE_BACKEND == "local":
        final_status = "DEPLOYED"
        log.info("local_mode_auto_deployed", model_id=str(model.id))
    else:
        final_status = "UPLOADED"

    await db.models.update_one(
        {"_id": model.id},
        {"$set": {"s3_path": storage_uri, "status": final_status}}
    )
    model.s3_path = storage_uri
    model.status = final_status

    # Log event
    event = DeploymentEvent(
        model_id=model.id,
        event_type="UPLOAD",
        status="SUCCESS",
        message=f"Model uploaded to {storage_uri} (backend={settings.STORAGE_BACKEND})",
    )
    await db.deployment_events.insert_one(event.to_dict())

    log.info("model_uploaded", model_id=str(model.id), framework=framework, size_mb=f"{size_mb:.2f}", backend=settings.STORAGE_BACKEND)
    return model


@router.get("/", response_model=list[ModelResponse])
async def list_models(
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    query = {} if current_user.role == "admin" else {"owner_id": current_user.id}
    cursor = db.models.find(query).sort("created_at", -1)
    models_doc = await cursor.to_list(length=100)
    return [Model(**m) for m in models_doc]


@router.get("/{model_id}", response_model=ModelDetailResponse)
async def get_model(
    model_id: str,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if model.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    events_cursor = db.deployment_events.find({"model_id": model_id}).sort("created_at", 1)
    events_doc = await events_cursor.to_list(length=100)
    model.events = [DeploymentEvent(**e) for e in events_doc]

    return model


@router.patch("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str,
    payload: ModelUpdateRequest,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if model.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc)
        await db.models.update_one({"_id": model_id}, {"$set": update_data})

    updated_doc = await db.models.find_one({"_id": model_id})
    return Model(**updated_doc)


@router.post("/{model_id}/deploy", response_model=MessageResponse)
async def deploy_model(
    model_id: str,
    payload: DeployRequest,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if model.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    # LOCAL mode: just mark as DEPLOYED immediately (no Kubernetes)
    if settings.STORAGE_BACKEND == "local":
        if model.status not in ("UPLOADED", "FAILED", "UNDEPLOYED", "DEPLOYED"):
            raise HTTPException(409, f"Cannot deploy model in status '{model.status}'")
        await db.models.update_one(
            {"_id": model_id},
            {"$set": {"status": "DEPLOYED", "updated_at": datetime.now(timezone.utc)}}
        )
        event = DeploymentEvent(
            model_id=model.id,
            event_type="DEPLOY_LOCAL",
            status="SUCCESS",
            message="Local mode: model marked as DEPLOYED instantly (no Kubernetes)",
        )
        await db.deployment_events.insert_one(event.to_dict())
        return {"message": "Local deploy successful — model is ready for inference", "data": {"model_id": model_id, "status": "DEPLOYED"}}

    # S3/AWS mode: queue job to Kubernetes via RabbitMQ
    if model.status not in ("UPLOADED", "FAILED", "UNDEPLOYED"):
        raise HTTPException(409, f"Cannot deploy model in status '{model.status}'")

    update_data = {
        "replicas": payload.replicas,
        "cpu_request": payload.cpu_request,
        "cpu_limit": payload.cpu_limit,
        "memory_request": payload.memory_request,
        "memory_limit": payload.memory_limit,
        "enable_autoscaling": payload.enable_autoscaling,
        "min_replicas": payload.min_replicas,
        "max_replicas": payload.max_replicas,
        "status": "QUEUED",
        "updated_at": datetime.now(timezone.utc)
    }
    await db.models.update_one({"_id": model_id}, {"$set": update_data})

    event = DeploymentEvent(
        model_id=model.id,
        event_type="DEPLOY_REQUESTED",
        status="QUEUED",
        message="Deployment job queued for build",
    )
    await db.deployment_events.insert_one(event.to_dict())

    await publish_build_job(
        model_id=str(model.id),
        s3_path=model.s3_path,
        framework=model.framework,
        config={
            "replicas": payload.replicas,
            "cpu_request": payload.cpu_request,
            "cpu_limit": payload.cpu_limit,
            "memory_request": payload.memory_request,
            "memory_limit": payload.memory_limit,
            "enable_autoscaling": payload.enable_autoscaling,
            "min_replicas": payload.min_replicas,
            "max_replicas": payload.max_replicas,
            "name": model.name,
            "version": model.version,
        },
    )
    log.info("deploy_job_queued", model_id=model_id)
    return {"message": "Deployment job queued successfully", "data": {"model_id": model_id, "status": "QUEUED"}}


@router.post("/{model_id}/undeploy", response_model=MessageResponse)
async def undeploy_model(
    model_id: str,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if model.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")
    if model.status != "DEPLOYED":
        raise HTTPException(409, f"Model is not deployed (status: {model.status})")

    # LOCAL mode: just mark as UNDEPLOYED
    if settings.STORAGE_BACKEND == "local":
        await db.models.update_one(
            {"_id": model_id},
            {"$set": {"status": "UNDEPLOYED", "updated_at": datetime.now(timezone.utc)}}
        )
        return {"message": "Local undeploy successful", "data": {"model_id": model_id}}

    await db.models.update_one(
        {"_id": model_id},
        {"$set": {"status": "UNDEPLOYING", "updated_at": datetime.now(timezone.utc)}}
    )

    event = DeploymentEvent(
        model_id=model.id,
        event_type="UNDEPLOY_REQUESTED",
        status="QUEUED",
        message="Undeployment job queued",
    )
    await db.deployment_events.insert_one(event.to_dict())

    await publish_undeploy_job(
        model_id=str(model.id),
        k8s_deployment_name=model.k8s_deployment_name,
        k8s_namespace=model.k8s_namespace,
        ecr_image_uri=model.ecr_image_uri,
    )
    return {"message": "Undeployment job queued", "data": {"model_id": model_id}}


@router.get("/{model_id}/status", response_model=dict)
async def get_deployment_status(
    model_id: str,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    return {
        "model_id": str(model.id),
        "status": model.status,
        "storage_backend": settings.STORAGE_BACKEND,
        "storage_path": model.s3_path,
        "ecr_image_uri": model.ecr_image_uri,
        "k8s_deployment_name": model.k8s_deployment_name,
        "k8s_namespace": model.k8s_namespace,
    }


@router.get("/{model_id}/download-url", response_model=dict)
async def get_model_download_url(
    model_id: str,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if not model.s3_path:
        raise HTTPException(404, "Model artifact not found")
    if model.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")

    url = await get_download_url(model.s3_path)
    return {"download_url": url, "expires_in": 3600, "backend": settings.STORAGE_BACKEND}


@router.delete("/{model_id}", response_model=MessageResponse)
async def delete_model_endpoint(
    model_id: str,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if model.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Access denied")
    if model.status == "DEPLOYED":
        raise HTTPException(409, "Undeploy the model before deleting")

    if model.s3_path:
        try:
            await delete_model(model.s3_path)
        except Exception:
            log.warning("storage_delete_failed_on_model_delete", model_id=model_id)

    await db.models.delete_one({"_id": model_id})
    await db.deployment_events.delete_many({"model_id": model_id})
    return {"message": "Model deleted successfully"}
