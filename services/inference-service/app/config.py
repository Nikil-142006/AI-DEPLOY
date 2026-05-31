from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SERVICE_NAME: str = "inference-service"
    DEBUG: bool = False

    # Database
    MONGO_URI: str = "mongodb://aideploy:mongodb_secret@localhost:27017/aideploy?authSource=admin"
    REDIS_URL: str = "redis://:redis_secret@localhost:6379/2"

    JWT_SECRET_KEY: str = "super_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"

    # Cache TTL for predictions (seconds)
    PREDICTION_CACHE_TTL: int = 300
    K8S_NAMESPACE: str = "model-serving"

    # Storage backend: 'local' (no AWS) or 's3' (AWS production)
    STORAGE_BACKEND: str = "local"
    LOCAL_MODEL_STORAGE_PATH: str = "/app/model-storage"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
