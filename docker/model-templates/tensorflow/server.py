"""
TensorFlow / Keras Model Serving Server
Supports: .h5 (Keras HDF5), SavedModel directory, .keras (Keras v3)
"""
import time
import numpy as np
import tensorflow as tf
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="TensorFlow Model Server", version="1.0.0")

MODEL_PATH = Path("/app/model_artifact")

PREDICTIONS_TOTAL = Counter("predictions_total", "Total prediction requests")
PREDICTION_LATENCY = Histogram("prediction_latency_seconds", "Prediction latency")

model = None


@app.on_event("startup")
async def load_model():
    global model
    try:
        # Keras .h5 / .keras or SavedModel directory
        model = tf.keras.models.load_model(str(MODEL_PATH))
    except Exception as e:
        raise RuntimeError(f"Failed to load TensorFlow model: {e}")


class PredictRequest(BaseModel):
    inputs: List[List[float]]


class PredictResponse(BaseModel):
    prediction: List[Any]
    confidence: List[Any]
    latency_ms: float


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "tf_version": tf.__version__,
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    PREDICTIONS_TOTAL.inc()
    start = time.perf_counter()

    try:
        arr = np.array(request.inputs, dtype=np.float32)
        output = model.predict(arr, verbose=0)

        # Handle classification vs regression
        if output.ndim == 2 and output.shape[1] > 1:
            # Multi-class softmax output → argmax class + max confidence
            prediction = output.argmax(axis=1).tolist()
            confidence = output.max(axis=1).tolist()
        elif output.ndim == 2 and output.shape[1] == 1:
            # Binary sigmoid output
            raw = output.squeeze(axis=1)
            prediction = (raw > 0.5).astype(int).tolist()
            confidence = raw.tolist()
        else:
            # Regression
            prediction = output.flatten().tolist()
            confidence = [1.0] * len(prediction)

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Prediction error: {str(e)}")

    latency_ms = (time.perf_counter() - start) * 1000
    PREDICTION_LATENCY.observe(latency_ms / 1000)

    return PredictResponse(prediction=prediction, confidence=confidence, latency_ms=latency_ms)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
