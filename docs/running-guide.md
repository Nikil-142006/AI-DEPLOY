# Step-by-Step Guide: Running and Testing AI-DEPLOY

This guide provides complete, step-by-step instructions to configure, run, and verify the MongoDB-based AI-DEPLOY platform on your local machine.

---

## 🛠️ Step 1: Environment Setup

1. **Clone/Navigate to the directory**:
   Ensure you are in the root directory: `c:\Backend\AI-DEPLOY`.

2. **Configure Environment Variables**:
   Copy `.env.example` to a new `.env` file:
   ```bash
   cp .env.example .env
   ```
   *(On Windows PowerShell, use: `copy .env.example .env`)*

   The default values in `.env` are pre-configured to work out of the box with `docker-compose.yml`.

---

## ⚡ Step 2: Spin Up the Infrastructure

We will launch the entire ecosystem (microservices + monitoring + databases) in Docker.

1. **Start the containers in detached mode**:
   ```bash
   docker-compose up --build -d
   ```

2. **Verify all services are running and healthy**:
   ```bash
   docker-compose ps
   ```
   You should see the following services listed as `Up (healthy)` or `Up`:
   *   `ai-deploy-mongodb` (Port `27017`)
   *   `ai-deploy-redis` (Port `6379`)
   *   `ai-deploy-rabbitmq` (Ports `5672`, `15672`)
   *   `ai-deploy-auth` (Port `8001`)
   *   `ai-deploy-model` (Port `8002`)
   *   `ai-deploy-worker` (No external port)
   *   `ai-deploy-inference` (Port `8003`)
   *   `ai-deploy-prometheus` (Port `9090`)
   *   `ai-deploy-grafana` (Port `3000`)

---

## 🧪 Step 3: Run the End-to-End Verification Pipeline

Let's walk through an end-to-end user journey: Registering, Authenticating, Uploading a Model, Simulating Deployment, and Running low-latency Inference.

### 3.1 Register and Obtain JWT Access Token
First, register a new developer account and fetch the JWT credentials.

1. **Register a User**:
   ```bash
   curl -X POST http://localhost:8001/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "developer@ai-deploy.io", "password": "SecurePassword123", "role": "developer"}'
   ```

2. **Login and Retrieve Access Token**:
   ```bash
   curl -X POST http://localhost:8001/auth/login \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=developer@ai-deploy.io&password=SecurePassword123"
   ```
   *Expected Response:*
   ```json
   {
     "access_token": "eyJhbGciOi...",
     "refresh_token": "eyJhbGciOi...",
     "token_type": "bearer"
   }
   ```
   **Copy the value of the `access_token`**. We will refer to it as `<JWT_TOKEN>` below.

---

### 3.2 Upload a Model
We will create a placeholder model file and upload it to the Model Service.

1. **Create a dummy model file**:
   ```bash
   echo "dummy_scikit_learn_binary_data" > dummy_model.pkl
   ```

2. **Upload the model**:
   ```bash
   curl -X POST http://localhost:8002/models/upload \
     -H "Authorization: Bearer <JWT_TOKEN>" \
     -F "name=churn-prediction-model" \
     -F "framework=sklearn" \
     -F "version=1.0.0" \
     -F "file=@dummy_model.pkl"
   ```
   *Expected Response:*
   ```json
   {
     "id": "mdl_uuid_here",
     "name": "churn-prediction-model",
     "framework": "sklearn",
     "version": "1.0.0",
     "status": "UPLOADED",
     "s3_path": "s3://ai-deploy-models-dev/mdl_uuid_here/dummy_model.pkl"
   }
   ```
   **Copy the `"id"` value** (e.g. `c8b9c403-...`). We will refer to this as `<MODEL_ID>`.

---

### 3.3 Deploy the Model
Trigger the build and deployment pipeline. The Model Service will publish a job to RabbitMQ, which the Worker Service consumes to build a custom Docker container.

1. **Trigger Deployment**:
   ```bash
   curl -X POST http://localhost:8002/models/<MODEL_ID>/deploy \
     -H "Authorization: Bearer <JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"replicas": 2, "cpu_request": "100m", "memory_request": "128Mi", "enable_autoscaling": false}'
   ```

2. **Observe Build Queue and Logs**:
   - Monitor the build sequence in real-time by checking the worker logs:
     ```bash
     docker logs -f ai-deploy-worker
     ```
   - You can also view the RabbitMQ Management UI by navigating to `http://localhost:15672` in your browser (Credentials: `aideploy` / `rabbitmq_secret`). You will see spike and consumption metrics on the `model.build` queue.

---

### 3.4 Serve Real-Time Predictions (with Redis Caching)
The Inference Service routes requests to internal model serving pods and caches frequent predictions in Redis.

1. **Send Inference Request**:
   ```bash
   curl -X POST http://localhost:8003/inference/<MODEL_ID>/predict \
     -H "Authorization: Bearer <JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"inputs": [[1.5, 0.2, 3.4, 0.8]]}'
   ```
   *Expected Response (First Call - Cache Miss):*
   ```json
   {
     "model_id": "<MODEL_ID>",
     "prediction": [...],
     "confidence": [...],
     "latency_ms": 45.2,
     "cached": false
   }
   ```

2. **Send Identical Inference Request**:
   Send the exact same request again:
   ```bash
   curl -X POST http://localhost:8003/inference/<MODEL_ID>/predict \
     -H "Authorization: Bearer <JWT_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"inputs": [[1.5, 0.2, 3.4, 0.8]]}'
   ```
   *Expected Response (Second Call - Cache Hit):*
   ```json
   {
     "model_id": "<MODEL_ID>",
     "prediction": [...],
     "confidence": [...],
     "latency_ms": 1.2,
     "cached": true
   }
   ```
   *Notice that the latency drops to ~1ms because the result is served directly from Redis.*

---

## 📈 Step 4: Observability & Monitoring

1. **Prometheus UI**:
   - Open your browser and navigate to `http://localhost:9090`.
   - Go to **Status** -> **Targets** to verify all services (`auth-service`, `model-service`, `inference-service`) are actively scraped.
   - Search for metrics like `http_requests_total` or `model_inference_duration_seconds` to view graphs.

2. **Grafana Dashboards**:
   - Open your browser and navigate to `http://localhost:3000`.
   - Log in using credentials: `admin` / `admin`.
   - Go to Dashboards, and click on **AI-DEPLOY Platform Overview**.
   - You will see dynamic, live graphs detailing your request rates, latency charts, and cache hits.
