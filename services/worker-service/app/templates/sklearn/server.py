"""
Scikit-learn Model Serving Server
Supports: .pkl (pickle), .joblib formats
"""
import time
import pickle
import joblib
import numpy as np
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="sklearn Model Server", version="1.0.0")

MODEL_PATH = Path("/app/model_artifact")

PREDICTIONS_TOTAL = Counter("predictions_total", "Total prediction requests")
PREDICTION_LATENCY = Histogram("prediction_latency_seconds", "Prediction latency")

model = None


@app.on_event("startup")
async def load_model():
    global model
    try:
        model = joblib.load(MODEL_PATH)
    except Exception:
        try:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load sklearn model: {e}")


class PredictRequest(BaseModel):
    inputs: List[List[float]]


class PredictResponse(BaseModel):
    prediction: List[Any]
    confidence: List[Any]
    latency_ms: float


@app.get("/health")
async def health():
    return {"status": "healthy", "model_loaded": model is not None}


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    PREDICTIONS_TOTAL.inc()
    start = time.perf_counter()

    try:
        arr = np.array(request.inputs)
        prediction = model.predict(arr).tolist()

        if hasattr(model, "predict_proba"):
            confidence = model.predict_proba(arr).max(axis=1).tolist()
        else:
            confidence = [1.0] * len(prediction)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Prediction error: {str(e)}")

    latency_ms = (time.perf_counter() - start) * 1000
    PREDICTION_LATENCY.observe(latency_ms / 1000)

    return PredictResponse(prediction=prediction, confidence=confidence, latency_ms=latency_ms)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
