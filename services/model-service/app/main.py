from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

from app.database import init_db
from app.queue import close_rabbitmq
from app.router import router
from app.config import get_settings

settings = get_settings()

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests",
    ["method", "endpoint", "status_code", "service"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency",
    ["method", "endpoint", "service"]
)
MODEL_UPLOADS_TOTAL = Counter("model_uploads_total", "Total model uploads", ["framework"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_rabbitmq()


app = FastAPI(
    title="AI Deploy – Model Service",
    description="Model registry: upload, manage, and deploy ML models as scalable REST APIs",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=response.status_code,
        service=settings.SERVICE_NAME,
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path,
        service=settings.SERVICE_NAME,
    ).observe(duration)
    return response


app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
