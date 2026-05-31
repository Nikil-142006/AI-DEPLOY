import hashlib
import json
import time
import asyncio
from pathlib import Path
from typing import List, Any

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram

from app.database import get_db
from app.models import Model
from app.redis_client import get_redis
from app.dependencies import get_current_user
from app.config import get_settings

settings = get_settings()
log = structlog.get_logger()
router = APIRouter(prefix="/inference", tags=["Inference"])

INFERENCE_REQUESTS = Counter(
    "model_inference_requests_total", "Total inference requests",
    ["model_id", "cached"]
)
INFERENCE_LATENCY = Histogram(
    "model_inference_duration_seconds", "Inference latency in seconds",
    ["model_id"]
)


class PredictRequest(BaseModel):
    """Request body for prediction. Send a list of input arrays."""
    inputs: List[Any] = Field(..., description="Input data for prediction, e.g. [[5.1, 3.5, 1.4, 0.2]]")


def _cache_key(model_id: str, inputs: list) -> str:
    payload = json.dumps(inputs, sort_keys=True)
    h = hashlib.sha256(f"{model_id}:{payload}".encode()).hexdigest()[:16]
    return f"predict:{model_id}:{h}"


def _pod_url(k8s_service_name: str, k8s_namespace: str) -> str:
    """Build internal Kubernetes service URL."""
    return f"http://{k8s_service_name}.{k8s_namespace}.svc.cluster.local/predict"


def _find_local_model_file(model_id: str) -> Path:
    """Search the local model storage directory for the model file."""
    base_path = Path(settings.LOCAL_MODEL_STORAGE_PATH) / "models" / model_id
    if not base_path.exists():
        raise FileNotFoundError(f"No model directory found at {base_path}")
    # Find any model file in the directory
    for ext in [".pkl", ".joblib", ".pt", ".pth", ".h5", ".keras", ".json"]:
        matches = list(base_path.glob(f"*{ext}"))
        if matches:
            return matches[0]
    raise FileNotFoundError(f"No recognized model file found in {base_path}")


def _run_local_inference(model_path: Path, framework: str, inputs: list) -> dict:
    """
    Load and run the model in-process.
    Supports: sklearn, xgboost (local). pytorch and tensorflow give a clear message.
    """
    if framework in ("sklearn", "xgboost"):
        # Try joblib first, then pickle
        try:
            import joblib
            model_obj = joblib.load(str(model_path))
        except Exception:
            import pickle
            with open(model_path, "rb") as f:
                model_obj = pickle.load(f)

        import numpy as np
        X = np.array(inputs)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        prediction = model_obj.predict(X).tolist()
        confidence = None
        if hasattr(model_obj, "predict_proba"):
            proba = model_obj.predict_proba(X).tolist()
            confidence = max(proba[0]) if proba else None

        return {"prediction": prediction, "confidence": confidence}

    elif framework == "pytorch":
        try:
            import torch
            model_obj = torch.load(str(model_path), map_location="cpu")
            model_obj.eval()
            import numpy as np
            X = torch.tensor(np.array(inputs), dtype=torch.float32)
            if X.ndim == 1:
                X = X.unsqueeze(0)
            with torch.no_grad():
                output = model_obj(X)
            prediction = output.numpy().tolist()
            return {"prediction": prediction, "confidence": None}
        except Exception as e:
            raise RuntimeError(f"PyTorch inference failed: {e}")

    elif framework in ("tensorflow", "keras"):
        try:
            import tensorflow as tf
            import numpy as np
            model_obj = tf.keras.models.load_model(str(model_path))
            X = np.array(inputs)
            if X.ndim == 1:
                X = X.reshape(1, -1)
            output = model_obj.predict(X)
            return {"prediction": output.tolist(), "confidence": None}
        except Exception as e:
            raise RuntimeError(f"TensorFlow inference failed: {e}")

    else:
        raise ValueError(f"Local inference not supported for framework: {framework}")


@router.post("/{model_id}/predict")
async def predict(
    model_id: str,
    payload: PredictRequest,
    db = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_user=Depends(get_current_user),
):
    # Fetch model metadata from MongoDB
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)
    if model.status != "DEPLOYED":
        raise HTTPException(409, f"Model is not deployed (status: {model.status}). "
                                  f"In local mode, upload auto-deploys. In AWS mode, use POST /models/{{id}}/deploy first.")

    inputs = payload.inputs

    cache_key = _cache_key(model_id, inputs)
    start = time.perf_counter()

    # Try Redis cache first
    cached = await redis.get(cache_key)
    if cached:
        latency = time.perf_counter() - start
        INFERENCE_REQUESTS.labels(model_id=model_id, cached="true").inc()
        INFERENCE_LATENCY.labels(model_id=model_id).observe(latency)
        return {
            "model_id": model_id,
            "prediction": json.loads(cached),
            "latency_ms": round(latency * 1000, 2),
            "cached": True,
        }

    # ── LOCAL mode: run inference in-process ──────────────────────────────────
    if settings.STORAGE_BACKEND == "local":
        try:
            model_path = await asyncio.to_thread(_find_local_model_file, model_id)
        except FileNotFoundError as e:
            log.error("local_model_file_not_found", model_id=model_id, error=str(e))
            raise HTTPException(500, f"Model file not found on disk: {e}")

        try:
            result_data = await asyncio.to_thread(
                _run_local_inference, model_path, model.framework, inputs
            )
        except Exception as e:
            log.error("local_inference_error", model_id=model_id, error=str(e))
            raise HTTPException(500, f"Local inference failed: {e}")

    # ── AWS/K8s mode: forward to model pod ───────────────────────────────────
    else:
        pod_url = _pod_url(model.k8s_service_name, model.k8s_namespace)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(pod_url, json={"inputs": inputs})
                response.raise_for_status()
                result_data = response.json()
        except httpx.TimeoutException:
            raise HTTPException(504, "Model pod request timed out")
        except httpx.HTTPStatusError as e:
            raise HTTPException(502, f"Model pod error: {e.response.status_code}")
        except Exception as e:
            log.error("inference_pod_error", model_id=model_id, error=str(e))
            raise HTTPException(502, "Failed to reach model pod")

    latency = time.perf_counter() - start
    prediction = result_data.get("prediction")

    # Cache the result
    await redis.setex(cache_key, settings.PREDICTION_CACHE_TTL, json.dumps(prediction))

    INFERENCE_REQUESTS.labels(model_id=model_id, cached="false").inc()
    INFERENCE_LATENCY.labels(model_id=model_id).observe(latency)

    log.info("inference_complete", model_id=model_id, latency_ms=round(latency * 1000, 2), backend=settings.STORAGE_BACKEND)

    return {
        "model_id": model_id,
        "prediction": prediction,
        "confidence": result_data.get("confidence"),
        "latency_ms": round(latency * 1000, 2),
        "cached": False,
        "backend": settings.STORAGE_BACKEND,
    }


@router.get("/{model_id}/health")
async def model_health(
    model_id: str,
    db = Depends(get_db),
    current_user=Depends(get_current_user),
):
    model_doc = await db.models.find_one({"_id": model_id})
    if not model_doc:
        raise HTTPException(404, "Model not found")

    model = Model(**model_doc)

    # LOCAL mode: check if file exists on disk
    if settings.STORAGE_BACKEND == "local":
        try:
            model_path = await asyncio.to_thread(_find_local_model_file, model_id)
            file_healthy = True
            file_path = str(model_path)
        except FileNotFoundError:
            file_healthy = False
            file_path = None

        return {
            "model_id": model_id,
            "model_status": model.status,
            "backend": "local",
            "file_found": file_healthy,
            "file_path": file_path,
        }

    # AWS/K8s mode: check pod health
    pod_url = _pod_url(model.k8s_service_name, model.k8s_namespace).replace("/predict", "/health")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(pod_url)
            pod_healthy = resp.status_code == 200
    except Exception:
        pod_healthy = False

    return {
        "model_id": model_id,
        "model_status": model.status,
        "backend": "s3",
        "pod_healthy": pod_healthy,
        "k8s_deployment": model.k8s_deployment_name,
        "k8s_namespace": model.k8s_namespace,
    }
