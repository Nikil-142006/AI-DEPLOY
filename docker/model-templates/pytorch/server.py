"""
PyTorch Model Serving Server
Supports: .pt (TorchScript), .pth (state_dict + pickle fallback)
"""
import io
import time
import pickle
import numpy as np
import torch
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

app = FastAPI(title="PyTorch Model Server", version="1.0.0")

MODEL_PATH = Path("/app/model_artifact")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

PREDICTIONS_TOTAL = Counter("predictions_total", "Total prediction requests")
PREDICTION_LATENCY = Histogram("prediction_latency_seconds", "Prediction latency")

model = None
is_torchscript = False


@app.on_event("startup")
async def load_model():
    global model, is_torchscript
    try:
        # Try TorchScript first (preferred for production)
        model = torch.jit.load(str(MODEL_PATH), map_location=DEVICE)
        model.eval()
        is_torchscript = True
    except Exception:
        try:
            # Fallback: full pickle model
            model = torch.load(str(MODEL_PATH), map_location=DEVICE)
            model.eval()
            is_torchscript = False
        except Exception as e:
            raise RuntimeError(f"Failed to load PyTorch model: {e}")


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
        "device": str(DEVICE),
        "torchscript": is_torchscript,
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    PREDICTIONS_TOTAL.inc()
    start = time.perf_counter()

    try:
        tensor = torch.tensor(request.inputs, dtype=torch.float32).to(DEVICE)

        with torch.no_grad():
            output = model(tensor)

        # Handle classification vs regression
        if output.dim() == 2 and output.shape[1] > 1:
            # Multi-class: apply softmax
            probs = torch.softmax(output, dim=1)
            prediction = probs.argmax(dim=1).cpu().tolist()
            confidence = probs.max(dim=1).values.cpu().tolist()
        else:
            # Binary / regression
            raw = output.squeeze(-1).cpu().tolist()
            if isinstance(raw, float):
                raw = [raw]
            prediction = [int(v > 0.5) for v in raw]
            confidence = [float(v) for v in raw]

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Prediction error: {str(e)}")

    latency_ms = (time.perf_counter() - start) * 1000
    PREDICTION_LATENCY.observe(latency_ms / 1000)

    return PredictResponse(prediction=prediction, confidence=confidence, latency_ms=latency_ms)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
