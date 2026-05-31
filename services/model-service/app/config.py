from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SERVICE_NAME: str = "model-service"
    DEBUG: bool = False

    # Database
    MONGO_URI: str = "mongodb://aideploy:mongodb_secret@localhost:27017/aideploy?authSource=admin"

    # Redis
    REDIS_URL: str = "redis://:redis_secret@localhost:6379/1"

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://aideploy:rabbitmq_secret@localhost:5672/"

    # Storage backend: 'local' (no AWS) or 's3' (AWS production)
    STORAGE_BACKEND: str = "local"
    LOCAL_MODEL_STORAGE_PATH: str = "/app/model-storage"

    # AWS S3 (only used when STORAGE_BACKEND=s3)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "ai-deploy-models-dev"

    # JWT (for token validation)
    JWT_SECRET_KEY: str = "super_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"

    # File limits
    MAX_UPLOAD_SIZE_MB: int = 500

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
