import os
import asyncio
from pathlib import Path
import aioboto3
from botocore.exceptions import ClientError
import structlog
from app.config import get_settings

settings = get_settings()
log = structlog.get_logger()


# ── Local Storage ─────────────────────────────────────────────────────────────

async def upload_model_local(file_bytes: bytes, storage_key: str) -> str:
    """Save model file to local disk and return a local:// URI."""
    local_path = Path(settings.LOCAL_MODEL_STORAGE_PATH) / storage_key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    # Run blocking file I/O in a thread to keep async
    await asyncio.to_thread(local_path.write_bytes, file_bytes)
    local_uri = f"local://{storage_key}"
    log.info("model_saved_locally", path=str(local_path), uri=local_uri)
    return local_uri


async def delete_model_local(storage_key: str) -> None:
    """Delete a model file from local disk."""
    local_path = Path(settings.LOCAL_MODEL_STORAGE_PATH) / storage_key
    if local_path.exists():
        await asyncio.to_thread(local_path.unlink)
        log.info("model_deleted_locally", path=str(local_path))


async def get_local_download_url(storage_key: str) -> str:
    """Return a placeholder URL for local storage (not a real HTTP URL)."""
    local_path = Path(settings.LOCAL_MODEL_STORAGE_PATH) / storage_key
    return f"file://{local_path}"


# ── S3 Storage ─────────────────────────────────────────────────────────────────

def get_s3_client():
    session = aioboto3.Session(
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    return session.client("s3")


async def upload_model_to_s3(file_bytes: bytes, s3_key: str) -> str:
    """Upload model file to S3 and return the full S3 URI."""
    async with get_s3_client() as s3:
        try:
            await s3.put_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=s3_key,
                Body=file_bytes,
                ServerSideEncryption="AES256",
            )
            s3_uri = f"s3://{settings.AWS_S3_BUCKET}/{s3_key}"
            log.info("model_uploaded_to_s3", s3_uri=s3_uri)
            return s3_uri
        except ClientError as e:
            log.error("s3_upload_failed", error=str(e))
            raise


async def delete_model_from_s3(s3_key: str) -> None:
    """Delete model artifact from S3."""
    async with get_s3_client() as s3:
        try:
            await s3.delete_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
            log.info("model_deleted_from_s3", s3_key=s3_key)
        except ClientError as e:
            log.error("s3_delete_failed", error=str(e))
            raise


async def generate_presigned_url(s3_key: str, expiry: int = 3600) -> str:
    """Generate a pre-signed URL for temporary model access."""
    async with get_s3_client() as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url


# ── Unified Interface (picks backend based on STORAGE_BACKEND) ────────────────

async def upload_model(file_bytes: bytes, storage_key: str) -> str:
    """Upload a model using the configured backend."""
    if settings.STORAGE_BACKEND == "local":
        return await upload_model_local(file_bytes, storage_key)
    return await upload_model_to_s3(file_bytes, storage_key)


async def delete_model(storage_path: str) -> None:
    """Delete a model using the configured backend."""
    if settings.STORAGE_BACKEND == "local":
        # storage_path is like 'local://models/uuid/file.pkl'
        storage_key = storage_path.replace("local://", "")
        await delete_model_local(storage_key)
    else:
        s3_key = storage_path.replace(f"s3://{settings.AWS_S3_BUCKET}/", "")
        await delete_model_from_s3(s3_key)


async def get_download_url(storage_path: str) -> str:
    """Get a download URL for a model using the configured backend."""
    if settings.STORAGE_BACKEND == "local":
        storage_key = storage_path.replace("local://", "")
        return await get_local_download_url(storage_key)
    s3_key = storage_path.replace(f"s3://{settings.AWS_S3_BUCKET}/", "")
    return await generate_presigned_url(s3_key)
