import uuid
from datetime import datetime

class Model:
    def __init__(self, **kwargs):
        self.id = str(kwargs.get("id") or kwargs.get("_id") or uuid.uuid4())
        self.name = kwargs.get("name")
        self.version = kwargs.get("version", "1.0.0")
        self.description = kwargs.get("description")
        self.framework = kwargs.get("framework")
        self.status = kwargs.get("status", "UPLOADED")
        self.s3_path = kwargs.get("s3_path")
        self.ecr_image_uri = kwargs.get("ecr_image_uri")
        self.k8s_deployment_name = kwargs.get("k8s_deployment_name")
        self.k8s_service_name = kwargs.get("k8s_service_name")
        self.k8s_namespace = kwargs.get("k8s_namespace", "model-serving")
        self.replicas = kwargs.get("replicas", 1)
        self.cpu_request = kwargs.get("cpu_request", "250m")
        self.cpu_limit = kwargs.get("cpu_limit", "500m")
        self.memory_request = kwargs.get("memory_request", "256Mi")
        self.memory_limit = kwargs.get("memory_limit", "512Mi")
        self.enable_autoscaling = kwargs.get("enable_autoscaling", False)
        self.min_replicas = kwargs.get("min_replicas", 1)
        self.max_replicas = kwargs.get("max_replicas", 10)
        self.owner_id = str(kwargs.get("owner_id")) if kwargs.get("owner_id") else None
        self.created_at = kwargs.get("created_at") or datetime.utcnow()
        self.updated_at = kwargs.get("updated_at") or datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "framework": self.framework,
            "status": self.status,
            "s3_path": self.s3_path,
            "ecr_image_uri": self.ecr_image_uri,
            "k8s_deployment_name": self.k8s_deployment_name,
            "k8s_service_name": self.k8s_service_name,
            "k8s_namespace": self.k8s_namespace,
            "replicas": self.replicas,
            "cpu_request": self.cpu_request,
            "cpu_limit": self.cpu_limit,
            "memory_request": self.memory_request,
            "memory_limit": self.memory_limit,
            "enable_autoscaling": self.enable_autoscaling,
            "min_replicas": self.min_replicas,
            "max_replicas": self.max_replicas,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DeploymentEvent:
    def __init__(self, **kwargs):
        self.id = str(kwargs.get("id") or kwargs.get("_id") or uuid.uuid4())
        self.model_id = str(kwargs.get("model_id")) if kwargs.get("model_id") else None
        self.event_type = kwargs.get("event_type")
        self.status = kwargs.get("status")
        self.message = kwargs.get("message")
        self.created_at = kwargs.get("created_at") or datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self.id,
            "model_id": self.model_id,
            "event_type": self.event_type,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at,
        }
