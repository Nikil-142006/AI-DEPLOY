# AI-DEPLOY API Reference Guide

This document details the exact HTTP routes, parameters, authorization requirements, and example request/response payloads for the AI-DEPLOY microservices.

---

## 🔐 1. Auth Service (`port: 8001`)

Base URL: `http://<gateway-ip>/auth` or `http://localhost:8001`

### 1.1 POST `/auth/register`
Creates a new platform user.
- **Auth required**: None
- **Request Body**:
  ```json
  {
    "email": "user@domain.com",
    "password": "strongpassword123",
    "role": "developer" 
  }
  ```
  *Note: Supported roles are `admin`, `developer`, and `viewer`.*
- **Response (201 Created)**:
  ```json
  {
    "id": "usr_7d8e9f...",
    "email": "user@domain.com",
    "role": "developer",
    "is_active": true,
    "created_at": "2026-05-25T17:00:00Z"
  }
  ```

### 1.2 POST `/auth/login`
Authenticates a user and issues JWT tokens.
- **Auth required**: None
- **Request Body (form-data)**:
  - `username`: `user@domain.com`
  - `password`: `strongpassword123`
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

### 1.3 POST `/auth/refresh`
Refreshes an expired access token using a valid refresh token.
- **Auth required**: None
- **Request Body**:
  ```json
  {
    "refresh_token": "eyJhbGciOi..."
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

---

## 📦 2. Model Service (`port: 8002`)

Base URL: `http://<gateway-ip>/models` or `http://localhost:8002`

### 2.1 GET `/models/`
Retrieves a list of uploaded models.
- **Auth required**: JWT Bearer Token (Any role)
- **Response (200 OK)**:
  ```json
  [
    {
      "id": "mdl_1a2b3c...",
      "name": "churn-predictor",
      "framework": "xgboost",
      "version": "1.2.0",
      "status": "UPLOADED",
      "s3_path": "s3://ai-deploy-models-prod/mdl_1a2b3c/model.bin",
      "owner_id": "usr_7d8e9f...",
      "created_at": "2026-05-25T17:05:00Z"
    }
  ]
  ```

### 2.2 POST `/models/`
Uploads a new model file.
- **Auth required**: JWT Bearer Token (Roles: `admin`, `developer`)
- **Request Body (multipart/form-data)**:
  - `name` (string): `churn-predictor`
  - `framework` (string): `xgboost` (Choices: `tensorflow`, `pytorch`, `sklearn`, `xgboost`)
  - `version` (string): `1.2.0`
  - `file` (binary file): `<model.bin>`
- **Response (201 Created)**:
  ```json
  {
    "id": "mdl_1a2b3c...",
    "name": "churn-predictor",
    "framework": "xgboost",
    "version": "1.2.0",
    "status": "UPLOADED",
    "s3_path": "s3://ai-deploy-models-prod/mdl_1a2b3c/model.bin",
    "created_at": "2026-05-25T17:05:00Z"
  }
  ```

### 2.3 POST `/models/{model_id}/deploy`
Triggers Kubernetes deployment sequence for a specific model.
- **Auth required**: JWT Bearer Token (Roles: `admin`, `developer`)
- **Request Body (JSON)**:
  ```json
  {
    "replicas": 2,
    "cpu_request": "250m",
    "memory_request": "256Mi",
    "cpu_limit": "500m",
    "memory_limit": "512Mi",
    "enable_autoscaling": true,
    "min_replicas": 1,
    "max_replicas": 10
  }
  ```
- **Response (202 Accepted)**:
  ```json
  {
    "model_id": "mdl_1a2b3c...",
    "status": "BUILDING",
    "message": "Model build job queued successfully"
  }
  ```

---

## ⚡ 3. Inference Service (`port: 8003`)

Base URL: `http://<gateway-ip>/inference` or `http://localhost:8003`

### 3.1 POST `/inference/{model_id}/predict`
Executes real-time predictions. Checks cache first, forwards requests to active K8s pods if missing, then populates Redis.
- **Auth required**: JWT Bearer Token (Any role)
- **Request Body**:
  ```json
  {
    "inputs": [
      [0.5, 1.2, 0.0, 3.4, 2.1, 0.9, -1.0, 0.4]
    ]
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "model_id": "mdl_1a2b3c...",
    "prediction": [1],
    "confidence": [0.94],
    "latency_ms": 14.2,
    "cached": false
  }
  ```

### 3.2 GET `/inference/{model_id}/health`
Checks internal readiness of backend model pods.
- **Auth required**: JWT Bearer Token (Any role)
- **Response (200 OK)**:
  ```json
  {
    "model_id": "mdl_1a2b3c...",
    "model_status": "DEPLOYED",
    "pod_healthy": true,
    "k8s_deployment": "model-mdl-1a2b3c",
    "k8s_namespace": "model-serving"
  }
  ```
