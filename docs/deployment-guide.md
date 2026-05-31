# AI-DEPLOY Production Deployment Guide

This guide walks through step-by-step instructions to deploy AI-DEPLOY onto AWS using Terraform, EKS, and Kustomize.

---

## 🛠️ Step 1: AWS Environment Setup

1. **AWS CLI & Credentials**:
   Install the AWS CLI and run authentication:
   ```bash
   aws configure
   ```

2. **Terraform CLI**:
   Ensure Terraform is installed (v1.5.0+):
   ```bash
   terraform --version
   ```

---

## 🌐 Step 2: Provision Cloud Infrastructure (IaC)

Navigate to the Terraform folder, configure the values, and execute the provision script:

```bash
cd infrastructure/terraform
```

1. **Variables Customization**:
   Create a `terraform.tfvars` file:
   ```hcl
   aws_region     = "us-east-1"
   project_name   = "ai-deploy"
   environment    = "production"
   s3_bucket_name = "your-unique-s3-bucket-name"
   db_password    = "SecureSuperDBPassword123!"
   ```

2. **Initialize and Apply**:
   ```bash
   terraform init
   ```
   ```bash
   terraform plan -out=tfplan
   ```
   ```bash
   terraform apply tfplan
   ```

Upon success, Terraform outputs EKS Endpoint, ECR Registry URL, and S3 Bucket ARN. Take note of the ECR Registry URL (e.g. `123456789.dkr.ecr.us-east-1.amazonaws.com`).

---

## 🏗️ Step 3: Kubernetes Initial Config

Update your local `kubeconfig` to connect securely to the newly launched AWS EKS cluster:

```bash
aws eks update-kubeconfig --region us-east-1 --name ai-deploy-cluster
```

Verify you can contact the cluster:
```bash
kubectl get nodes
```

---

## 🔑 Step 4: Inject Config & Secrets

Update base config/secrets in `k8s/base/secrets.yaml` and `k8s/base/configmap.yaml` with the values returned by Terraform.

1. **ConfigMap (`k8s/base/configmap.yaml`)**:
   ```yaml
   data:
     aws-s3-bucket: "your-unique-s3-bucket-name"
     aws-region: "us-east-1"
     ecr-registry: "123456789.dkr.ecr.us-east-1.amazonaws.com"
   ```

2. **Secret (`k8s/base/secrets.yaml`)**:
   Ensure you base64 encode all critical secrets (e.g. `echo -n "..." | base64`):
   ```yaml
   data:
     mongo-uri: <BASE64_MONGODB_CONNECTION_STRING>
     redis-url: <BASE64_REDIS_CONNECTION_STRING>
     rabbitmq-url: <BASE64_RABBITMQ_CONNECTION_STRING>
     jwt-secret-key: <BASE64_JWT_SECRET>
     aws-access-key-id: <BASE64_AWS_ACCESS_KEY>
     aws-secret-access-key: <BASE64_AWS_SECRET_KEY>
   ```

   > **MongoDB URI format** (DocumentDB on AWS):
   > `mongodb://username:password@your-docdb-cluster.cluster-xyz.us-east-1.docdb.amazonaws.com:27017/?tls=true&tlsCAFile=global-bundle.pem&replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false`

Apply the base configurations:
```bash
kubectl apply -k k8s/base/
```

---

## 🚀 Step 5: Build and Deploy Microservices

You can leverage the CI/CD pipeline or build and push images manually:

1. **Authenticate Docker with ECR**:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
   ```

2. **Build & Push images**:
   ```bash
   # Auth Service
   docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/auth-service:1.0.0 services/auth-service/
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/auth-service:1.0.0

   # Model Service
   docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/model-service:1.0.0 services/model-service/
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/model-service:1.0.0

   # Inference Service
   docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/inference-service:1.0.0 services/inference-service/
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/inference-service:1.0.0

   # Worker Service
   docker build -t 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/worker-service:1.0.0 services/worker-service/
   docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/worker-service:1.0.0
   ```

3. **Deploy via Kustomize Production Overlay**:
   Modify `k8s/overlays/production/kustomization.yaml` to specify `1.0.0` as the tag:
   ```yaml
   images:
     - name: 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/auth-service
       newTag: "1.0.0"
     - name: 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/model-service
       newTag: "1.0.0"
     - name: 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/inference-service
       newTag: "1.0.0"
     - name: 123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/worker-service
       newTag: "1.0.0"
   ```
   Apply:
   ```bash
   kubectl apply -k k8s/overlays/production/
   ```

4. **Verify Rollout Status**:
   ```bash
   kubectl get pods -n ai-deploy
   kubectl get services -n ai-deploy
   ```

---

## 📈 Step 6: Deploy Monitoring Stack

For Kubernetes, ensure your Prometheus and Grafana manifests are deployed:
```bash
kubectl apply -f k8s/monitoring/
```
*(Optionally use Helm to deploy Prometheus Operator / kube-prometheus-stack).*
