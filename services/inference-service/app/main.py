from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import time
from prometheus_client import Counter, Histogram

from app.database import init_db
from app.redis_client import close_redis
from app.router import router
from app.config import get_settings

settings = get_settings()

REQUEST_COUNT = Counter(
    "http_requests_total", "Total requests",
    ["method", "endpoint", "status_code", "service"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency",
    ["method", "endpoint", "service"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_redis()


app = FastAPI(
    title="AI Deploy – Inference Service",
    description="Routes inference requests to deployed model pods with Redis caching",
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
    dur = time.time() - start
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
    ).observe(dur)
    return response


app.include_router(router)


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
