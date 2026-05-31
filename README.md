# 🌌 AI-DEPLOY: Production MLOps Serving Platform

AI-DEPLOY is a secure, cloud-native, microservices-based platform designed to enable ML engineers and data scientists to deploy, serve, and monitor trained models (TensorFlow, PyTorch, Scikit-learn, XGBoost) dynamically as auto-scaling REST APIs in a Kubernetes environment.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                         │
│          Dashboard UI  /  REST API Consumers                │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────┐
│                        K8s INGRESS                          │
│          Routing · Service Map · SSL Termination            │
└──────┬──────────────┬───────────────┬───────────────────────┘
       │              │               │
┌──────▼──────┐ ┌─────▼──────┐ ┌─────▼──────────────┐
│  Auth Svc   │ │ Model Svc  │ │  Inference Svc     │
│  (FastAPI)  │ │ (FastAPI)  │ │  (FastAPI)         │
│  JWT + RBAC │ │ Upload/Mgmt│ │  Real-time serving │
└─────────────┘ └─────┬──────┘ └────────────────────┘
                      │
          ┌───────────▼──────────┐
          │   RabbitMQ (Queue)   │  ← async build jobs
          └───────────┬──────────┘
                      │
          ┌───────────▼──────────┐
          │  Worker / Build Svc  │  ← Docker image builder
          └───────────┬──────────┘
                      │
        ┌─────────────┴──────────────┐
        │                            │
   ┌────▼────┐                ┌──────▼──────┐
   │   ECR   │                │  EKS / K8s  │  ← deploys model pods
   │ (images)│                │  (serving)  │
   └─────────┘                └─────────────┘

Shared Infrastructure:
  MongoDB (metadata) · Redis (cache + sessions) · S3 (model storage)
  Prometheus + Grafana (observability)
```

### Core Services
1. **Auth Service (`port: 8001`)**: Secure microservice using FastAPI, MongoDB, and Redis to handle registration, JWT token generation, token refresh, token blacklisting, and Role-Based Access Control (RBAC).
2. **Model Service (`port: 8002`)**: Handles model uploads, framework validation, persistent storage on AWS S3, metadata management in MongoDB, and produces async Docker build jobs via RabbitMQ.
3. **Worker Service**: Consumes RabbitMQ jobs, fetches artifacts, injects them into specialized framework Docker templates (TensorFlow, PyTorch, sklearn, XGBoost), builds images, pushes to AWS ECR, and applies K8s Deployments, Services, and HPAs dynamically.
4. **Inference Service (`port: 8003`)**: High-performance router that handles incoming user prediction payloads, queries database endpoints, forwards requests to internal model serving pods, and caches predictions in Redis with configurable TTL.

---

## ⚡ Quickstart – Local Development

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- curl

### 2. Launch Local Environment
To spin up all databases, cache nodes, queues, microservices, and monitoring stacks locally:
```bash
docker-compose up --build -d
```

### 3. Verify Local Services Status
```bash
docker-compose ps
```

---

## 🔑 Core API Examples

### 1. Authenticate (Register & Login)
**Register a user:**
```bash
curl -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "engineer@ai-deploy.io", "password": "SuperSecurePassword123", "role": "developer"}'
```

**Get a JWT access token:**
```bash
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=engineer@ai-deploy.io&password=SuperSecurePassword123"
```
*Note the returned `"access_token"` to use in subsequent requests.*

---

### 2. Upload Model Artifacts
Upload a model artifact (e.g. Scikit-learn picklestore) to the Model Service:
```bash
curl -X POST http://localhost:8002/models/ \
  -H "Authorization: Bearer <YOUR_JWT_ACCESS_TOKEN>" \
  -F "name=fraud-detector" \
  -F "framework=sklearn" \
  -F "version=1.0.0" \
  -F "file=@/path/to/model.pkl"
```

---

### 3. Trigger Deployment
Deploy the uploaded model as an active auto-scaling service in Kubernetes:
```bash
curl -X POST http://localhost:8002/models/<MODEL_UUID>/deploy \
  -H "Authorization: Bearer <YOUR_JWT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"replicas": 2, "cpu_request": "100m", "memory_request": "128Mi", "enable_autoscaling": true, "min_replicas": 1, "max_replicas": 5}'
```

---

### 4. Serve Prediction Requests
Route low-latency predictions through the Inference Service gateway (which caches responses in Redis):
```bash
curl -X POST http://localhost:8003/inference/<MODEL_UUID>/predict \
  -H "Authorization: Bearer <YOUR_JWT_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"inputs": [[1.2, 0.4, 3.1, 0.9, -0.4, 2.3, 0.1, 1.1]]}'
```

---

## 📈 Monitoring & Dashboards

- **Prometheus**: Accessible locally at `http://localhost:9090`. Monitors scrape rates, queue depth, database connections, and model-specific inference latencies.
- **Grafana**: Accessible locally at `http://localhost:3000` (Default credentials: `admin` / `admin`). Pre-provisioned with the **AI-DEPLOY Platform Overview** dashboard, tracking:
  - Microservice request volumes & error rates (RED method)
  - 99th percentile HTTP latencies
  - Inference requests per model ID
  - Model server latency charts

---

## 🌐 Production Cloud Deployment

### 1. Infrastructure via Terraform
Ensure AWS CLI is configured, navigate to terraform directory, and apply:
```bash
cd infrastructure/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```
This sets up a dedicated VPC, highly available subnets, an ECR container registry, an EKS Kubernetes cluster with managed CPU/GPU worker nodes, and an Amazon DocumentDB (MongoDB-compatible) cluster.

### 2. Deploy to Kubernetes
Use Kustomize to deploy configurations to staging or production overlays:
```bash
# Staging deployment
kubectl apply -k k8s/overlays/staging/

# Production deployment
kubectl apply -k k8s/overlays/production/
```
