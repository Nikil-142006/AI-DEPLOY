import os
import re
import boto3
import docker
import structlog
from pathlib import Path
from app.config import get_settings

settings = get_settings()
log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _sanitize_name(name: str) -> str:
    """Make a valid Kubernetes/Docker resource name."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9\-]", "-", name)
    return name[:50]


def _get_s3_key(s3_path: str) -> str:
    return s3_path.replace(f"s3://{settings.AWS_S3_BUCKET}/", "")


def download_model_from_s3(s3_path: str, local_path: str) -> None:
    """Download model artifact from S3 to a local path."""
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    key = _get_s3_key(s3_path)
    filename = key.split("/")[-1]
    dest = os.path.join(local_path, filename)
    s3.download_file(settings.AWS_S3_BUCKET, key, dest)
    log.info("model_downloaded_from_s3", s3_path=s3_path, dest=dest)
    return dest, filename


def build_and_push_image(
    model_id: str,
    framework: str,
    model_local_path: str,
    model_filename: str,
    build_dir: str,
) -> str:
    """Build Docker image using the appropriate framework template and push to ECR."""
    template_path = TEMPLATES_DIR / framework / "Dockerfile.template"
    if not template_path.exists():
        raise FileNotFoundError(f"No template for framework: {framework}")

    # Read template and substitute model filename
    with open(template_path) as f:
        dockerfile_content = f.read()
    dockerfile_content = dockerfile_content.replace("{{MODEL_FILE}}", model_filename)

    # Write Dockerfile to build dir
    dockerfile_path = os.path.join(build_dir, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    # Copy model file to build dir
    import shutil
    shutil.copy2(model_local_path, os.path.join(build_dir, model_filename))

    # Also copy the server.py template
    server_template = TEMPLATES_DIR / framework / "server.py"
    if server_template.exists():
        shutil.copy2(str(server_template), os.path.join(build_dir, "server.py"))

    # Build image
    tag = f"model-{model_id[:8]}"
    ecr_image_uri = f"{settings.ECR_REGISTRY}/ai-deploy/models:{tag}"

    client = docker.from_env()
    log.info("docker_build_start", model_id=model_id, tag=ecr_image_uri)
    image, build_logs = client.images.build(path=build_dir, tag=ecr_image_uri, rm=True)
    for line in build_logs:
        if "stream" in line:
            log.debug("docker_build", output=line["stream"].strip())

    # Authenticate and push to ECR
    ecr_client = boto3.client(
        "ecr",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )
    token = ecr_client.get_authorization_token()
    auth_data = token["authorizationData"][0]
    import base64
    username, password = base64.b64decode(auth_data["authorizationToken"]).decode().split(":")
    registry = auth_data["proxyEndpoint"]

    client.login(username=username, password=password, registry=registry)
    for line in client.images.push(ecr_image_uri, stream=True, decode=True):
        if "status" in line:
            log.debug("docker_push", status=line["status"])

    log.info("docker_image_pushed", ecr_image_uri=ecr_image_uri)
    return ecr_image_uri
