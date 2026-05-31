from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    SERVICE_NAME: str = "worker-service"
    DEBUG: bool = False

    # Database
    MONGO_URI: str = "mongodb://aideploy:mongodb_secret@localhost:27017/aideploy?authSource=admin"
    RABBITMQ_URL: str = "amqp://aideploy:rabbitmq_secret@localhost:5672/"

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "ai-deploy-models-dev"
    ECR_REGISTRY: str = ""

    KUBECONFIG: str = "/app/kubeconfig"
    K8S_NAMESPACE: str = "model-serving"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
