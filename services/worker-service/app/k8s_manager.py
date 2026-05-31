import yaml
import structlog
from kubernetes import client as k8s_client, config as k8s_config
from app.config import get_settings

settings = get_settings()
log = structlog.get_logger()


def load_k8s_config():
    try:
        k8s_config.load_incluster_config()
        log.info("k8s_config_loaded", source="in-cluster")
    except Exception:
        k8s_config.load_kube_config(config_file=settings.KUBECONFIG)
        log.info("k8s_config_loaded", source="kubeconfig")


def _deployment_name(model_id: str) -> str:
    return f"model-{model_id[:8]}"


def deploy_model_to_k8s(
    model_id: str,
    ecr_image_uri: str,
    config: dict,
) -> tuple[str, str]:
    """Create or update Kubernetes Deployment and Service for a model pod."""
    load_k8s_config()
    apps_v1 = k8s_client.AppsV1Api()
    core_v1 = k8s_client.CoreV1Api()
    namespace = settings.K8S_NAMESPACE
    dep_name = _deployment_name(model_id)
    svc_name = f"{dep_name}-svc"

    # ── Deployment ────────────────────────────────────────────────────────────
    deployment = k8s_client.V1Deployment(
        metadata=k8s_client.V1ObjectMeta(
            name=dep_name,
            namespace=namespace,
            labels={"app": dep_name, "managed-by": "ai-deploy"},
        ),
        spec=k8s_client.V1DeploymentSpec(
            replicas=config.get("replicas", 1),
            selector=k8s_client.V1LabelSelector(match_labels={"app": dep_name}),
            strategy=k8s_client.V1DeploymentStrategy(
                type="RollingUpdate",
                rolling_update=k8s_client.V1RollingUpdateDeployment(
                    max_surge=1, max_unavailable=0
                ),
            ),
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(labels={"app": dep_name}),
                spec=k8s_client.V1PodSpec(
                    containers=[
                        k8s_client.V1Container(
                            name="model-server",
                            image=ecr_image_uri,
                            ports=[k8s_client.V1ContainerPort(container_port=8080)],
                            resources=k8s_client.V1ResourceRequirements(
                                requests={
                                    "cpu": config.get("cpu_request", "250m"),
                                    "memory": config.get("memory_request", "256Mi"),
                                },
                                limits={
                                    "cpu": config.get("cpu_limit", "500m"),
                                    "memory": config.get("memory_limit", "512Mi"),
                                },
                            ),
                            liveness_probe=k8s_client.V1Probe(
                                http_get=k8s_client.V1HTTPGetAction(path="/health", port=8080),
                                initial_delay_seconds=30,
                                period_seconds=10,
                                failure_threshold=3,
                            ),
                            readiness_probe=k8s_client.V1Probe(
                                http_get=k8s_client.V1HTTPGetAction(path="/health", port=8080),
                                initial_delay_seconds=10,
                                period_seconds=5,
                            ),
                        )
                    ],
                    security_context=k8s_client.V1PodSecurityContext(
                        run_as_non_root=True,
                        run_as_user=1000,
                    ),
                ),
            ),
        ),
    )

    try:
        apps_v1.create_namespaced_deployment(namespace=namespace, body=deployment)
        log.info("k8s_deployment_created", name=dep_name)
    except k8s_client.ApiException as e:
        if e.status == 409:
            apps_v1.patch_namespaced_deployment(name=dep_name, namespace=namespace, body=deployment)
            log.info("k8s_deployment_patched", name=dep_name)
        else:
            raise

    # ── Service ───────────────────────────────────────────────────────────────
    service = k8s_client.V1Service(
        metadata=k8s_client.V1ObjectMeta(name=svc_name, namespace=namespace),
        spec=k8s_client.V1ServiceSpec(
            selector={"app": dep_name},
            ports=[k8s_client.V1ServicePort(port=80, target_port=8080)],
            type="ClusterIP",
        ),
    )

    try:
        core_v1.create_namespaced_service(namespace=namespace, body=service)
        log.info("k8s_service_created", name=svc_name)
    except k8s_client.ApiException as e:
        if e.status != 409:
            raise

    # ── HPA (if autoscaling enabled) ──────────────────────────────────────────
    if config.get("enable_autoscaling"):
        _create_hpa(dep_name, namespace, config)

    return dep_name, svc_name


def _create_hpa(dep_name: str, namespace: str, config: dict):
    autoscaling_v2 = k8s_client.AutoscalingV2Api()
    hpa = k8s_client.V2HorizontalPodAutoscaler(
        metadata=k8s_client.V1ObjectMeta(name=f"{dep_name}-hpa", namespace=namespace),
        spec=k8s_client.V2HorizontalPodAutoscalerSpec(
            scale_target_ref=k8s_client.V2CrossVersionObjectReference(
                api_version="apps/v1", kind="Deployment", name=dep_name
            ),
            min_replicas=config.get("min_replicas", 1),
            max_replicas=config.get("max_replicas", 10),
            metrics=[
                k8s_client.V2MetricSpec(
                    type="Resource",
                    resource=k8s_client.V2ResourceMetricSource(
                        name="cpu",
                        target=k8s_client.V2MetricTarget(
                            type="Utilization", average_utilization=70
                        ),
                    ),
                )
            ],
        ),
    )
    try:
        autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(namespace=namespace, body=hpa)
        log.info("k8s_hpa_created", name=f"{dep_name}-hpa")
    except k8s_client.ApiException as e:
        if e.status != 409:
            raise


def undeploy_model_from_k8s(k8s_deployment_name: str, k8s_namespace: str):
    """Delete the Kubernetes Deployment, Service, and HPA for a model."""
    load_k8s_config()
    apps_v1 = k8s_client.AppsV1Api()
    core_v1 = k8s_client.CoreV1Api()

    svc_name = f"{k8s_deployment_name}-svc"
    hpa_name = f"{k8s_deployment_name}-hpa"

    for resource, fn in [
        (k8s_deployment_name, apps_v1.delete_namespaced_deployment),
        (svc_name, core_v1.delete_namespaced_service),
    ]:
        try:
            fn(name=resource, namespace=k8s_namespace)
            log.info("k8s_resource_deleted", name=resource)
        except k8s_client.ApiException as e:
            if e.status != 404:
                log.warning("k8s_delete_error", name=resource, error=str(e))

    try:
        k8s_client.AutoscalingV2Api().delete_namespaced_horizontal_pod_autoscaler(
            name=hpa_name, namespace=k8s_namespace
        )
    except k8s_client.ApiException:
        pass
