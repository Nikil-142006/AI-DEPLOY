import uuid

class Model:
    def __init__(self, **kwargs):
        self.id = str(kwargs.get("id") or kwargs.get("_id") or uuid.uuid4())
        self.name = kwargs.get("name")
        self.status = kwargs.get("status")
        self.framework = kwargs.get("framework", "sklearn")
        self.k8s_deployment_name = kwargs.get("k8s_deployment_name")
        self.k8s_service_name = kwargs.get("k8s_service_name")
        self.k8s_namespace = kwargs.get("k8s_namespace", "model-serving")

    def to_dict(self):
        return {
            "_id": self.id,
            "name": self.name,
            "status": self.status,
            "framework": self.framework,
            "k8s_deployment_name": self.k8s_deployment_name,
            "k8s_service_name": self.k8s_service_name,
            "k8s_namespace": self.k8s_namespace,
        }
