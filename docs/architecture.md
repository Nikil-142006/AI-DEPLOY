# AI-DEPLOY: Full Platform Architecture

> A complete technical reference covering system design, microservice breakdown, data flows, database schemas, networking, security, CI/CD, and cloud infrastructure for the AI-DEPLOY MLOps serving platform.

---

## 1. 📐 High-Level System Architecture

```
                         ┌──────────────────────────────────────┐
                         │           CLIENT LAYER               │
                         │    SDK / REST Consumers / Dashboard  │
                         └──────────────────┬───────────────────┘
                                            │ HTTPS
                         ┌──────────────────▼───────────────────┐
                         │         NGINX INGRESS CONTROLLER      │
                         │    SSL Termination · Path Routing     │
                         │    /auth/* · /models/* · /inference/* │
                         └───┬──────────────┬───────────────┬───┘
                             │              │               │
               ┌─────────────▼──┐  ┌────────▼────────┐  ┌──▼──────────────┐
               │  AUTH SERVICE  │  │  MODEL SERVICE  │  │INFERENCE SERVICE│
               │   Port 8001    │  │   Port 8002     │  │   Port 8003     │
               │  FastAPI+Motor │  │  FastAPI+Motor  │  │  FastAPI+Motor  │
               │  JWT · RBAC   │  │  Upload · S3    │  │  Route · Cache  │
               └───────┬────────┘  └────────┬────────┘  └──────┬──────────┘
                       │                    │                   │
                       │                    ▼                   │
                       │            ┌───────────────┐           │
                       │            │   RABBITMQ    │           │
                       │            │  model.build  │           │
                       │            │  model.undeploy│          │
                       │            └───────┬───────┘           │
                       │                    │                   │
                       │                    ▼                   │
                       │           ┌────────────────┐           │
                       │           │  WORKER SERVICE│           │
                       │           │  (Py Consumer) │           │
                       │           └───┬────────┬───┘           │
                       │               │        │               │
                       │            ┌──▼──┐  ┌──▼──────────┐   │
                       │            │ ECR │  │  KUBERNETES  │   │
                       │            │(img)│  │  EKS Cluster │   │
                       │            └──┬──┘  └──────┬───────┘   │
                       │               │             │           │
                       │               │    ┌────────▼────────┐  │
                       │               │    │  MODEL SERVING  │  │
                       │               └───►│  PODS (Dynamic) │◄─┘
                       │                    │  Port 8080      │
                       │                    └─────────────────┘
                       │
              ┌─────────────────────────────────────────────────┐
              │                SHARED DATA LAYER                 │
              │                                                  │
              │  ┌──────────────────┐   ┌─────────────────────┐ │
              │  │    MongoDB       │   │       Redis          │ │
              │  │  (Motor Driver)  │   │  (Predictions Cache  │ │
              │  │  users           │   │   JWT Blacklists     │ │
              │  │  models          │   │   Refresh Tokens)    │ │
              │  │  deploy_events   │   └─────────────────────┘ │
              │  └──────────────────┘                           │
              │                                                  │
              │  ┌──────────────────┐   ┌─────────────────────┐ │
              │  │     AWS S3       │   │     AWS ECR          │ │
              │  │  Model Artifacts │   │  Docker Registries   │ │
              │  │  (Binary blobs)  │   │  (Serving Images)    │ │
              │  └──────────────────┘   └─────────────────────┘ │
              └─────────────────────────────────────────────────┘
```

---

## 2. 📁 Complete Repository File Structure

```
c:\Backend\AI-DEPLOY\
│
├── docker-compose.yml              ← Full local environment definition
├── .env.example                    ← Environment variable template
├── README.md                       ← Platform overview and quickstart
│
├── services/
│   │
│   ├── auth-service/               ← JWT authentication microservice
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← FastAPI app + Prometheus middleware
│   │       ├── config.py           ← Settings (MONGO_URI, JWT, Redis)
│   │       ├── database.py         ← Motor MongoDB client + get_db()
│   │       ├── models.py           ← User document class
│   │       ├── schemas.py          ← Pydantic request/response schemas
│   │       ├── security.py         ← JWT encode/decode, bcrypt hashing
│   │       ├── dependencies.py     ← get_current_user() FastAPI dependency
│   │       ├── router.py           ← /auth/* endpoints
│   │       └── redis_client.py     ← Redis async session client
│   │
│   ├── model-service/              ← Model management microservice
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← FastAPI app + Prometheus middleware
│   │       ├── config.py           ← Settings (MONGO_URI, S3, RabbitMQ)
│   │       ├── database.py         ← Motor MongoDB client + get_db()
│   │       ├── models.py           ← Model + DeploymentEvent classes
│   │       ├── schemas.py          ← Pydantic upload/deploy schemas
│   │       ├── dependencies.py     ← JWT validation dependency
│   │       ├── router.py           ← /models/* endpoints
│   │       ├── storage.py          ← AWS S3 upload/download helpers
│   │       └── queue.py            ← RabbitMQ producer (aio-pika)
│   │
│   ├── inference-service/          ← Prediction routing microservice
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py             ← FastAPI app + Prometheus middleware
│   │       ├── config.py           ← Settings (MONGO_URI, Redis, TTL)
│   │       ├── database.py         ← Motor MongoDB client + get_db()
│   │       ├── models.py           ← Minimal Model document class
│   │       ├── dependencies.py     ← JWT validation dependency
│   │       ├── router.py           ← /inference/{model_id}/predict + /health
│   │       └── redis_client.py     ← Redis async prediction cache client
│   │
│   ├── worker-service/             ← Async build + deploy worker
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── worker.py           ← RabbitMQ consumer + orchestrator
│   │       ├── config.py           ← Settings (MONGO_URI, AWS, K8s)
│   │       ├── models.py           ← Model + DeploymentEvent classes
│   │       ├── builder.py          ← S3 download + Docker build + ECR push
│   │       └── k8s_manager.py      ← K8s Deployment, Service, HPA creator
│   │
│   └── shared/
│       └── requirements.txt        ← Shared pip dependencies reference
│
├── scripts/
│   └── init_db.js                  ← MongoDB init: collections + indexes
│
├── docker/
│   └── model-templates/            ← Framework-specific serving containers
│       ├── tensorflow/
│       │   ├── Dockerfile.template ← FROM tensorflow/tensorflow:2.13.0
│       │   └── server.py           ← FastAPI server loading .h5 / SavedModel
│       ├── pytorch/
│       │   ├── Dockerfile.template ← FROM pytorch/pytorch:2.1.0-cuda11.8
│       │   └── server.py           ← FastAPI server (TorchScript + pickle)
│       ├── sklearn/
│       │   ├── Dockerfile.template ← FROM python:3.11-slim
│       │   └── server.py           ← FastAPI server (joblib + pickle)
│       └── xgboost/
│           ├── Dockerfile.template ← FROM python:3.11-slim
│           └── server.py           ← FastAPI server (Booster + sklearn API)
│
├── k8s/
│   ├── base/                       ← Core Kubernetes manifests
│   │   ├── kustomization.yaml      ← Kustomize resource list
│   │   ├── namespace.yaml          ← ai-deploy + model-serving namespaces
│   │   ├── rbac.yaml               ← ServiceAccount + Role + RoleBinding
│   │   ├── configmap.yaml          ← Shared non-secret env values
│   │   ├── secrets.yaml            ← Base64 encoded credentials
│   │   ├── auth-service.yaml       ← Deployment + ClusterIP Service
│   │   ├── model-service.yaml      ← Deployment + ClusterIP Service
│   │   ├── inference-service.yaml  ← Deployment + ClusterIP Service
│   │   ├── worker-service.yaml     ← Deployment + ServiceAccount
│   │   ├── ingress.yaml            ← NGINX Ingress routing rules
│   │   └── hpa.yaml                ← HorizontalPodAutoscalers (CPU 70%)
│   └── overlays/
│       ├── staging/
│       │   └── kustomization.yaml  ← Patch: reduce replicas to 1
│       └── production/
│           └── kustomization.yaml  ← Patch: inject CI commit SHA image tags
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml          ← Scrape configs (all 3 services)
│   │   └── alerts.yml              ← Alert rules (latency + crashloop)
│   └── grafana/
│       ├── provisioning/
│       │   ├── datasources/
│       │   │   └── datasource.yml  ← Auto-register Prometheus
│       │   └── dashboards/
│       │       └── dashboard.yml   ← Auto-load dashboard JSON files
│       └── dashboards/
│           └── platform_overview.json ← 4-panel dark dashboard
│
├── .github/
│   └── workflows/
│       ├── ci.yml                  ← Lint (Ruff) + Security (Bandit) + Test
│       └── deploy.yml              ← ECR push + EKS rolling deploy
│
└── infrastructure/
    └── terraform/
        ├── providers.tf            ← AWS + Kubernetes providers
        ├── variables.tf            ← Input variable declarations
        ├── vpc.tf                  ← VPC + subnets + NAT + route tables
        ├── eks.tf                  ← EKS cluster + node groups + IAM
        ├── documentdb.tf           ← Amazon DocumentDB (MongoDB compatible)
        ├── s3.tf                   ← S3 bucket + encryption + access block
        ├── ecr.tf                  ← ECR registries + lifecycle cleanup
        └── outputs.tf              ← Print endpoints + registry URLs
```

---

## 3. 🔬 Microservice Deep Dive

### 3.1 Auth Service — `services/auth-service/`

**Responsibility**: Issues and validates JWT tokens. Manages user identity, sessions and RBAC.

| File | Role |
|------|------|
| `main.py` | FastAPI application factory. Registers CORS, Prometheus middleware. Calls `init_db()` at startup. |
| `config.py` | Reads `MONGO_URI`, `REDIS_URL`, `JWT_SECRET_KEY` from environment variables. |
| `database.py` | Initializes `AsyncIOMotorClient` from `motor`. Exposes `get_db()` FastAPI dependency yielding the MongoDB database handle. |
| `models.py` | Lightweight `User` Python class with `to_dict()` → MongoDB document serialization. |
| `schemas.py` | Pydantic models: `UserRegisterRequest`, `UserLoginRequest`, `TokenResponse`, `UserResponse`. |
| `security.py` | `hash_password()` via bcrypt, `verify_password()`, `create_token_pair()` (access 15m + refresh 7d), `decode_token()` via python-jose. |
| `dependencies.py` | `get_current_user()`: Checks Redis blacklist → decodes JWT → queries `db.users.find_one()` → returns `User`. |
| `router.py` | `/auth/register` · `/auth/login` · `/auth/refresh` · `/auth/logout` · `/auth/me` · `/auth/users` |
| `redis_client.py` | Manages the async Redis connection for session tokens and JWT blacklisting. |

**Key Flows**:
- **Register**: Checks email/username uniqueness in MongoDB → hashes password → `insert_one`.
- **Login**: Fetches user by email → verifies bcrypt hash → issues JWT pair → stores refresh token in Redis with TTL.
- **Token Refresh**: Validates refresh JWT → checks Redis for stored token match → issues new access token.
- **Logout**: Deletes refresh token key from Redis.

---

### 3.2 Model Service — `services/model-service/`

**Responsibility**: Accepts model uploads, stores artifacts in S3, persists metadata in MongoDB, triggers async build jobs via RabbitMQ.

| File | Role |
|------|------|
| `main.py` | FastAPI app with Prometheus metrics middleware. |
| `config.py` | Reads `MONGO_URI`, `REDIS_URL`, `RABBITMQ_URL`, `AWS_S3_BUCKET`, `JWT_SECRET_KEY`. |
| `database.py` | Motor MongoDB async client, `get_db()` dependency. |
| `models.py` | `Model` and `DeploymentEvent` document classes with `to_dict()` serializers. |
| `schemas.py` | `ModelResponse`, `ModelDetailResponse`, `DeployRequest`, `ModelUpdateRequest`. |
| `dependencies.py` | Stateless JWT decoder — extracts user ID, email, role from JWT without a DB call. |
| `storage.py` | Async `aioboto3` S3 client: `upload_model_to_s3()`, `delete_model_from_s3()`, `generate_presigned_url()`. |
| `queue.py` | `aio-pika` RabbitMQ producer: `publish_build_job()` → `model.build` queue, `publish_undeploy_job()` → `model.undeploy` queue. |
| `router.py` | `POST /upload`, `GET /`, `GET /{id}`, `PATCH /{id}`, `POST /{id}/deploy`, `POST /{id}/undeploy`, `GET /{id}/status`, `DELETE /{id}` |

**Model Status Machine**:
```
UPLOADING → UPLOADED → QUEUED → BUILDING → DEPLOYING → DEPLOYED
                                                      ↓
                                               UNDEPLOYING → UNDEPLOYED
                                                      ↓
                                                   FAILED
```

---

### 3.3 Worker Service — `services/worker-service/`

**Responsibility**: Consumes RabbitMQ jobs. Downloads from S3. Builds framework-specific Docker images. Pushes to ECR. Deploys to Kubernetes. Reports status back to MongoDB.

| File | Role |
|------|------|
| `worker.py` | Main event loop. Connects to RabbitMQ. Registers `handle_build_job()` and `handle_undeploy_job()` consumers. Runs forever with `asyncio.Future()`. |
| `config.py` | Reads `MONGO_URI`, `RABBITMQ_URL`, `AWS_*`, `ECR_REGISTRY`, `K8S_NAMESPACE`. |
| `models.py` | `Model` and `DeploymentEvent` document classes. |
| `builder.py` | `download_model_from_s3()` via boto3. `build_and_push_image()` — reads `Dockerfile.template`, substitutes `{{MODEL_FILE}}`, copies `server.py`, runs `docker.images.build()`, authenticates ECR, pushes. |
| `k8s_manager.py` | `deploy_model_to_k8s()` — creates K8s `Deployment`, `Service`, and (optionally) `HPA` objects via the Python `kubernetes` client. `undeploy_model_from_k8s()` — deletes all three resources. |

**Build Pipeline** (per job):
```
1. Consume message from model.build queue
2. Update MongoDB: status → BUILDING
3. Download model binary from S3 to /tmp
4. Read Dockerfile.template for the framework (tensorflow/pytorch/sklearn/xgboost)
5. Substitute {{MODEL_FILE}} with actual filename
6. Copy model binary + server.py to build context
7. docker.images.build() → tag ECR URI
8. Authenticate ECR via get_authorization_token()
9. docker.images.push() → ECR
10. Update MongoDB: status → DEPLOYING
11. k8s_manager.deploy_model_to_k8s() → create Deployment + Service + HPA
12. Update MongoDB: status → DEPLOYED (store k8s_deployment_name, k8s_service_name)
13. Insert DeploymentEvent log
```

---

### 3.4 Inference Service — `services/inference-service/`

**Responsibility**: Accepts prediction requests. Checks Redis cache first. On cache miss, routes to model serving pods via Kubernetes internal DNS. Caches result with TTL.

| File | Role |
|------|------|
| `main.py` | FastAPI app + Prometheus middleware. |
| `config.py` | Reads `MONGO_URI`, `REDIS_URL`, `JWT_SECRET_KEY`, `PREDICTION_CACHE_TTL` (default 300s). |
| `database.py` | Motor MongoDB client to query model metadata (status, k8s DNS name). |
| `models.py` | Minimal `Model` class for K8s routing info. |
| `dependencies.py` | Stateless JWT decoder dependency. |
| `redis_client.py` | Async Redis client for reading/writing prediction cache entries. |
| `router.py` | `POST /inference/{model_id}/predict`, `GET /inference/{model_id}/health` |

**Prediction Flow** (per request):
```
1. JWT validated → get model_id from path
2. db.models.find_one({"_id": model_id}) → check status == DEPLOYED
3. Hash inputs (SHA256) → generate Redis cache_key
4. redis.get(cache_key) → HIT: return instantly (cached: true, ~1ms)
5. MISS: httpx.AsyncClient.post(k8s_pod_url, json={"inputs": inputs})
   └─ URL: http://<svc-name>.<namespace>.svc.cluster.local/predict
6. redis.setex(cache_key, PREDICTION_CACHE_TTL, json(prediction))
7. Return: {prediction, confidence, latency_ms, cached: false}
```

---

## 4. 🗄️ MongoDB Document Schemas

### Collection: `users`
```json
{
  "_id":             "uuid-string",
  "email":           "user@domain.com",
  "username":        "johndoe",
  "hashed_password": "$2b$12$...",
  "role":            "developer",
  "is_active":       true,
  "created_at":      "2026-05-25T17:00:00Z",
  "updated_at":      "2026-05-25T17:00:00Z"
}
```

### Collection: `models`
```json
{
  "_id":                  "uuid-string",
  "name":                 "fraud-detector",
  "version":              "1.2.0",
  "description":          "XGBoost churn predictor",
  "framework":            "xgboost",
  "status":               "DEPLOYED",
  "s3_path":              "s3://ai-deploy-models-prod/uuid/model.bin",
  "ecr_image_uri":        "123456789.dkr.ecr.us-east-1.amazonaws.com/ai-deploy/models:model-abc12345",
  "k8s_deployment_name":  "model-abc12345",
  "k8s_service_name":     "model-abc12345-svc",
  "k8s_namespace":        "model-serving",
  "replicas":             2,
  "cpu_request":          "250m",
  "cpu_limit":            "500m",
  "memory_request":       "256Mi",
  "memory_limit":         "512Mi",
  "enable_autoscaling":   true,
  "min_replicas":         1,
  "max_replicas":         10,
  "owner_id":             "uuid-string",
  "created_at":           "2026-05-25T17:00:00Z",
  "updated_at":           "2026-05-25T18:00:00Z"
}
```

### Collection: `deployment_events`
```json
{
  "_id":         "uuid-string",
  "model_id":    "model-uuid-string",
  "event_type":  "BUILD_COMPLETE",
  "status":      "SUCCESS",
  "message":     "Image pushed: 123456789.dkr.ecr.us-east-1.amazonaws.com/...",
  "created_at":  "2026-05-25T18:00:00Z"
}
```

**MongoDB Indexes** (created by `scripts/init_db.js`):
| Collection | Index | Type |
|---|---|---|
| `users` | `email` | Unique |
| `users` | `username` | Unique |
| `models` | `owner_id` | Standard |
| `deployment_events` | `model_id` | Standard |

---

## 5. 🔑 JWT Authentication & RBAC

```
Browser / Client
     │
     ├── POST /auth/login ──────────────────────────────────────────────►Auth Service
     │         (email + password)                                              │
     │◄── access_token (15 min) + refresh_token (7 days) ◄──────────────────┘
     │
     ├── POST /models/upload ─── Authorization: Bearer <access_token> ──►Model Service
     │                                                                         │
     │                                    [dependencies.py: get_current_user()]│
     │                                    1. Extract Bearer token             │
     │                                    2. Decode JWT (python-jose)         │
     │                                    3. Check Redis blacklist            │
     │                                    4. Return CurrentUser(id,email,role)│
     │◄── 201 Created ──────────────────────────────────────────────────────┘
```

**Roles**:
| Role | Permissions |
|---|---|
| `admin` | All endpoints, list all users + models |
| `developer` | Upload, deploy, undeploy own models, run inference |
| `viewer` | Read-only: list models, run inference |

---

## 6. 🚀 Docker Model Templates

Each deployed model runs inside a dynamically **baked Docker image** containing the model binary and a framework-specific FastAPI server:

| Framework | Base Image | Model Format | Loading Logic |
|---|---|---|---|
| `tensorflow` | `tensorflow/tensorflow:2.13.0` | `.h5` / SavedModel | `tf.keras.models.load_model()` |
| `pytorch` | `pytorch/pytorch:2.1.0-cuda11.8` | `.pt` / TorchScript | `torch.jit.load()` → fallback `torch.load()` |
| `sklearn` | `python:3.11-slim` | `.pkl` / `.joblib` | `joblib.load()` → fallback `pickle.load()` |
| `xgboost` | `python:3.11-slim` | `.bin` / `.json` / `.pkl` | `xgb.Booster.load_model()` → sklearn API fallback |

Each template exposes:
- `POST /predict` → accepts `{"inputs": [[...], ...]}` → returns `{"prediction": [...], "confidence": [...]}`
- `GET /health` → returns `{"status": "healthy"}` (used by K8s liveness/readiness probes)

---

## 7. ☸️ Kubernetes Architecture

### Namespaces
| Namespace | Contents |
|---|---|
| `ai-deploy` | Core microservices: auth, model, inference, worker |
| `model-serving` | Dynamic model pods (created per deployed model) |

### Static Resources (`ai-deploy` namespace)
```
auth-service      → Deployment (2 replicas) + ClusterIP Service + HPA (max 10)
model-service     → Deployment (2 replicas) + ClusterIP Service + HPA (max 10)
inference-service → Deployment (2 replicas) + ClusterIP Service + HPA (max 20)
worker-service    → Deployment (1 replica) + ServiceAccount (worker-service-sa)
```

### Dynamic Resources (`model-serving` namespace)
For each deployed model, the Worker creates:
```
model-<id>        → Deployment  (user-defined replicas, rolling update)
model-<id>-svc    → ClusterIP Service (port 80 → 8080)
model-<id>-hpa    → HPA (CPU 70%, min 1, max N — if autoscaling enabled)
```

### Networking
```
External traffic  ──► Ingress (NGINX) ──► ClusterIP Services
                                                   │
Inference pod ──► Internal DNS ──► model-<id>-svc.model-serving.svc.cluster.local
                                                   │
                                          Model Serving Pods (port 8080)
```

### RBAC (worker-service-sa)
The worker ServiceAccount is granted a namespaced `Role` in `model-serving` with:
- `apps: [deployments]` → `create, get, patch, delete`
- `core: [services]` → `create, get, patch, delete`
- `autoscaling: [horizontalpodautoscalers]` → `create, get, patch, delete`

---

## 8. ☁️ AWS Cloud Infrastructure (Terraform)

```
AWS Account
│
├── VPC (10.0.0.0/16)
│   ├── Public Subnets  (10.0.0.x, 10.0.1.x)  ← ALB / NGINX Ingress
│   ├── Private Subnets (10.0.10.x, 10.0.11.x) ← EKS Worker Nodes
│   └── DB Subnets      (10.0.20.x, 10.0.21.x) ← DocumentDB
│
├── Internet Gateway + NAT Gateway
│
├── Amazon EKS Cluster
│   ├── Control Plane (managed by AWS)
│   └── Managed Node Group: cpu-workers (t3.medium, 2–5 nodes)
│       └── (GPU nodes commented out, ready to enable: g4dn.xlarge)
│
├── Amazon DocumentDB Cluster (MongoDB 5.0 compatible)
│   ├── 1x db.t3.medium instance
│   └── Security Group: port 27017 from EKS nodes only
│
├── Amazon S3 Bucket
│   ├── AES256 Server-Side Encryption
│   └── Block all public access
│
└── Amazon ECR Repositories
    ├── ai-deploy/auth-service      ← scan_on_push = true
    ├── ai-deploy/model-service     ← scan_on_push = true
    ├── ai-deploy/inference-service ← scan_on_push = true
    ├── ai-deploy/worker-service    ← scan_on_push = true
    └── ai-deploy/models            ← Dynamic serving images
        └── Lifecycle: expire untagged > 14 days, keep latest 100
```

---

## 9. ⚙️ CI/CD Pipeline (GitHub Actions)

### `ci.yml` — Triggered on: `push` to `main`/`develop`, PRs
```
1. Checkout code
2. Set up Python 3.11
3. pip install requirements + ruff + bandit + pytest
4. ruff check services/          ← Lint (style + type issues)
5. bandit -r services/ -ll       ← Security scan (low+ severity)
6. pytest services/ --cov        ← Unit + integration tests
```

### `deploy.yml` — Triggered on: `push` to `main`
```
Job 1: build-and-push
├── Configure AWS credentials
├── docker login → Amazon ECR
├── docker build + push auth-service    :$GITHUB_SHA
├── docker build + push model-service   :$GITHUB_SHA
├── docker build + push inference-service:$GITHUB_SHA
└── docker build + push worker-service  :$GITHUB_SHA

Job 2: deploy-to-eks (needs: build-and-push)
├── aws eks update-kubeconfig
├── sed s/IMAGE_TAG/$GITHUB_SHA/ k8s/overlays/production/kustomization.yaml
├── kubectl apply -k k8s/overlays/production/
└── kubectl rollout status deployment/* -n ai-deploy --timeout=300s
```

---

## 10. 📊 Observability Stack

### Prometheus Metrics Collected
| Metric | Labels | Service |
|---|---|---|
| `http_requests_total` | method, endpoint, status_code, service | All 3 |
| `http_request_duration_seconds` | method, endpoint, service | All 3 |
| `model_inference_requests_total` | model_id, cached | Inference |
| `model_inference_duration_seconds` | model_id | Inference |

### Grafana Dashboard: "AI-DEPLOY Platform Overview"
- **Panel 1**: HTTP Request Rate by service (timeseries)
- **Panel 2**: HTTP Request Latency P99 by service (timeseries)
- **Panel 3**: Model Inference Requests by model_id + cached flag (timeseries)
- **Panel 4**: Model Inference Latency P99 by model_id (timeseries)

### Alert Rules
| Alert | Condition | Severity |
|---|---|---|
| `HighInferenceLatency` | P99 inference > 1s for 5+ min | warning |
| `ModelPodCrashLooping` | Container restart rate > 0.1/5m | critical |

---

## 11. 🔒 Security Design

| Layer | Control |
|---|---|
| **Network** | All services in private VPC subnets. Only NGINX Ingress exposed publicly. DocumentDB only reachable from EKS nodes. |
| **Authentication** | JWT (HS256), 15-min access tokens + 7-day refresh tokens stored in Redis |
| **Authorization** | RBAC: admin / developer / viewer roles enforced per endpoint |
| **Secrets** | Kubernetes Secrets (base64) in-cluster; AWS Secrets Manager for production |
| **Images** | ECR `scan_on_push = true`; CI Bandit security scan |
| **Containers** | Non-root user (UID 1000) in all Dockerfiles |
| **Data at rest** | S3 AES256 encryption; DocumentDB encrypted by default |
| **Data in transit** | TLS on all public endpoints via NGINX; SSL on DocumentDB |
| **Token blacklisting** | Redis `blacklist:<token>` key set at logout |

---

## 12. 🔄 End-to-End Request Lifecycle

### From Model Upload to Prediction in 12 Steps

```
Step 1:   Developer → POST /auth/login
          Auth Service validates credentials → returns JWT

Step 2:   Developer → POST /models/upload (JWT + model.pkl)
          Model Service validates framework + file extension + size

Step 3:   Model Service → AWS S3 upload model binary
          MongoDB: insert {status: UPLOADED, s3_path: ...}

Step 4:   Developer → POST /models/{id}/deploy
          MongoDB: update {status: QUEUED}
          RabbitMQ: publish to model.build queue

Step 5:   Worker Service consumes job from model.build
          MongoDB: update {status: BUILDING}

Step 6:   Worker downloads model from S3
          Selects framework Dockerfile.template (sklearn in this case)

Step 7:   Worker builds Docker image:
          docker build → tag ECR URI (model-<id>)
          docker push → Amazon ECR

Step 8:   MongoDB: update {status: DEPLOYING, ecr_image_uri: ...}
          Worker creates K8s Deployment + Service + HPA in model-serving namespace

Step 9:   EKS pulls image from ECR → model-<id> pod starts
          MongoDB: update {status: DEPLOYED, k8s_deployment_name: ..., k8s_service_name: ...}

Step 10:  User → POST /inference/{model_id}/predict (JWT + inputs)
          Inference Service: validates JWT → queries MongoDB for model status

Step 11:  Redis cache lookup:
          HIT  → return cached prediction (latency ~1ms, cached: true)
          MISS → httpx POST to model-<id>-svc.model-serving.svc.cluster.local/predict

Step 12:  Prediction returned → stored in Redis (TTL: 300s)
          Response: {prediction, confidence, latency_ms, cached: false}
```

---

## 13. ⚡ Performance Characteristics

| Metric | Expected Value |
|---|---|
| Auth token issuance latency | < 50ms |
| Model upload (100MB) | < 30s (S3 multipart) |
| Build + deploy pipeline (sklearn) | 3–5 minutes |
| Inference cached response | < 2ms |
| Inference uncached (pod call) | 20–100ms depending on model |
| HPA scale-up trigger | CPU > 70% for 60s |
| HPA scale-down | CPU < 70% for 5min |
