import uuid
from datetime import datetime

class Model:
    def __init__(self, **kwargs):
        self.id = str(kwargs.get("id") or kwargs.get("_id") or uuid.uuid4())
        self.name = kwargs.get("name")
        self.framework = kwargs.get("framework")
        self.status = kwargs.get("status", "UPLOADED")
        self.s3_path = kwargs.get("s3_path")
        self.ecr_image_uri = kwargs.get("ecr_image_uri")
        self.k8s_deployment_name = kwargs.get("k8s_deployment_name")
        self.k8s_service_name = kwargs.get("k8s_service_name")
        self.k8s_namespace = kwargs.get("k8s_namespace", "model-serving")
        self.owner_id = str(kwargs.get("owner_id")) if kwargs.get("owner_id") else None
        self.updated_at = kwargs.get("updated_at") or datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self.id,
            "name": self.name,
            "framework": self.framework,
            "status": self.status,
            "s3_path": self.s3_path,
            "ecr_image_uri": self.ecr_image_uri,
            "k8s_deployment_name": self.k8s_deployment_name,
            "k8s_service_name": self.k8s_service_name,
            "k8s_namespace": self.k8s_namespace,
            "owner_id": self.owner_id,
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
