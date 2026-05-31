# Post-Migration Config & Secrets Setup Guide

This guide details all manual steps, environment file updates, and secret token configurations required to run and deploy the migrated **AI-DEPLOY** system locally and in production.

---

## 1. Local Environment Configuration (`.env`)

To run the application locally, you need to create a `.env` file in the root directory.

### Step-by-Step:
1. Duplicate the `.env.example` file and rename it to `.env` in the root folder `c:\Backend\AI-DEPLOY`.
2. Open the new `.env` file and populate the secrets and keys:

```properties
# ────── MongoDB Configuration ──────
MONGO_USER=aideploy
MONGO_PASSWORD=your_secure_local_mongo_password   # <-- Change this to your local secret
MONGO_DB=aideploy
MONGO_URI=mongodb://aideploy:your_secure_local_mongo_password@mongodb:27017/aideploy?authSource=admin

# ────── Infrastructure Secrets ──────
REDIS_PASSWORD=your_secure_redis_password         # <-- Change this
RABBITMQ_USER=aideploy
RABBITMQ_PASSWORD=your_secure_rabbitmq_password   # <-- Change this
JWT_SECRET_KEY=generate_a_long_random_hash_here  # <-- Run `openssl rand -hex 32` or type a secret

# ────── AWS S3 & ECR Credentials ──────
# Required by model-service and worker-service for model artifact push/pull
AWS_ACCESS_KEY_ID=your_aws_access_key_id         # <-- Paste your AWS Key ID
AWS_SECRET_ACCESS_KEY=your_aws_secret_key        # <-- Paste your AWS Secret Key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-model-bucket-name             # <-- Your target AWS S3 bucket name
ECR_REGISTRY=123456789012.dkr.ecr.us-east-1.amazonaws.com # <-- Paste your ECR URI
```

---

## 2. GitHub Actions Secrets (Production Deployments)

When you push code to GitHub, the workflows will run automatically. However, they will fail if the required security keys are missing on GitHub.

### Step-by-Step:
1. Go to your repository page on **GitHub**.
2. Click **Settings** (top navigation bar).
3. Under the left sidebar, click **Secrets and variables** > **Actions**.
4. Click the green button: **New repository secret**.
5. Create the following three secrets:

| Secret Name | Description / Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | Your AWS access key credentials. |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key credentials. |
| `ECR_REGISTRY` | The root ECR domain (e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com`). |

---

## 3. Kubernetes Secret Configuration (`secrets.yaml`)

For Kubernetes (EKS) deployment, environment variables are loaded securely from a base64 encoded Kubernetes secret manifest.

### Step-by-Step:
1. Convert your production MongoDB URI string into **Base64** format.
   * *On Windows PowerShell:*
     ```powershell
     [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes("mongodb://aideploy:prod_password@mongodb-service:27017/aideploy"))
     ```
   * *On Linux/macOS Terminal:*
     ```bash
     echo -n "mongodb://aideploy:prod_password@mongodb-service:27017/aideploy" | base64
     ```
2. Open the file `c:\Backend\AI-DEPLOY\k8s\base\secrets.yaml`.
3. Locate `mongo-uri` under `data:` and paste your generated base64 string:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ai-deploy-secrets
  namespace: ai-deploy
type: Opaque
data:
  # Paste your base64 string here:
  mongo-uri: bW9uZ29kYjovL2FpZGVwbG95OnByb2RfcGFzc3dvcmRAbW9uZ29kYi1zZXJ2aWNlOjI3MDE3L2FpZGVwbG95
  # Also update other base64 secrets if necessary:
  jwt-secret-key: bXktc3VwZXItc2VjcmV0LWtleQ==
```

---

## 4. Terraform Credentials (`terraform.tfvars`)

To provision production AWS DocumentDB clusters using Terraform without hardcoding passwords in git, use a local `.tfvars` file.

### Step-by-Step:
1. In the `infrastructure/terraform/` directory, create a new file named `terraform.tfvars`.
2. Add your DocumentDB administrative username and password credentials:

```hcl
db_username = "aideploy_admin"
db_password = "choose_a_highly_secure_prod_password"
```
*(Terraform automatically reads any file ending in `.tfvars` and injects these variables during `terraform apply` safely).*

---

## 5. Launching the Entire System Locally

Once the secrets are filled in, perform these steps to run locally:

1. **Launch Docker Desktop** on your computer.
2. In your terminal/PowerShell, run Docker Compose:
   ```bash
   docker compose up --build -d
   ```
3. **Initialize the Database:** Seed the initial database collections and production indexes into MongoDB:
   ```bash
   docker exec -i ai-deploy-mongodb mongosh aideploy /docker-entrypoint-initdb.d/init_db.js
   ```

You are all set! The backend API services will now be accessible locally:
* **Auth Service:** `http://localhost:8001`
* **Model Service:** `http://localhost:8002`
* **Inference Service:** `http://localhost:8003`
* **Worker Logs/Dashboard:** via Docker CLI/dashboard logs.
