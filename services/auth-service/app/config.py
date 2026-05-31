from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    SERVICE_NAME: str = "auth-service"
    DEBUG: bool = False

    # Database
    MONGO_URI: str = "mongodb://aideploy:mongodb_secret@localhost:27017/aideploy?authSource=admin"

    # Redis
    REDIS_URL: str = "redis://:redis_secret@localhost:6379/0"

    # JWT
    JWT_SECRET_KEY: str = "super_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
