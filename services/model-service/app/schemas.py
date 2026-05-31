import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


SUPPORTED_FRAMEWORKS = ["tensorflow", "pytorch", "sklearn", "xgboost"]
VALID_EXTENSIONS = {
    "tensorflow": [".h5", ".pb", ".keras", ".zip"],
    "pytorch": [".pt", ".pth", ".zip"],
    "sklearn": [".pkl", ".joblib"],
    "xgboost": [".json", ".ubj", ".pkl"],
}


# ── Request Schemas ────────────────────────────────────────────────────────────

class ModelUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    version: Optional[str] = None


class DeployRequest(BaseModel):
    replicas: int = Field(default=1, ge=1, le=20)
    cpu_request: str = "250m"
    cpu_limit: str = "500m"
    memory_request: str = "256Mi"
    memory_limit: str = "512Mi"
    enable_autoscaling: bool = False
    min_replicas: int = Field(default=1, ge=1)
    max_replicas: int = Field(default=10, ge=1, le=50)


# ── Response Schemas ───────────────────────────────────────────────────────────

class DeploymentEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    status: str
    message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ModelResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    description: Optional[str]
    framework: str
    status: str
    s3_path: Optional[str]
    ecr_image_uri: Optional[str]
    k8s_deployment_name: Optional[str]
    k8s_namespace: Optional[str]
    replicas: int
    cpu_limit: str
    memory_limit: str
    enable_autoscaling: bool
    min_replicas: int
    max_replicas: int
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelDetailResponse(ModelResponse):
    events: List[DeploymentEventResponse] = []

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str
    success: bool = True
    data: Optional[dict] = None
