// AI-DEPLOY MongoDB Initialization Script
// Run with: mongosh <connection-string> scripts/init_db.js
// Or via Docker: docker exec -i ai-deploy-mongodb mongosh aideploy scripts/init_db.js

db = db.getSiblingDB('aideploy');

// ─────────────────────────────────────────
// Create collections with schema validation
// ─────────────────────────────────────────

db.createCollection('users', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['_id', 'email', 'username', 'hashed_password', 'role', 'is_active'],
      properties: {
        email:           { bsonType: 'string' },
        username:        { bsonType: 'string' },
        hashed_password: { bsonType: 'string' },
        role:            { bsonType: 'string', enum: ['admin', 'developer', 'viewer'] },
        is_active:       { bsonType: 'bool' },
      }
    }
  }
});

db.createCollection('models', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['_id', 'name', 'framework', 'status', 'owner_id'],
      properties: {
        framework: {
          bsonType: 'string',
          enum: ['sklearn', 'xgboost', 'pytorch', 'tensorflow']
        },
        status: {
          bsonType: 'string',
          enum: ['UPLOADING', 'UPLOADED', 'QUEUED', 'BUILDING', 'DEPLOYING',
                 'DEPLOYED', 'UNDEPLOYING', 'UNDEPLOYED', 'FAILED']
        }
      }
    }
  }
});

db.createCollection('deployment_events');

// ─────────────────────────────────────────
// Indexes: users
// ─────────────────────────────────────────

// Unique email + username for registration uniqueness checks
db.users.createIndex({ "email": 1 },    { unique: true, name: "idx_users_email_unique" });
db.users.createIndex({ "username": 1 }, { unique: true, name: "idx_users_username_unique" });

// Active user filter (soft-delete pattern)
db.users.createIndex({ "is_active": 1 }, { name: "idx_users_is_active" });

// ─────────────────────────────────────────
// Indexes: models
// ─────────────────────────────────────────

// Owner lookup — "list my models" endpoint
db.models.createIndex({ "owner_id": 1 }, { name: "idx_models_owner_id" });

// Status filter — "list all DEPLOYED models" queries
db.models.createIndex({ "status": 1 }, { name: "idx_models_status" });

// Compound: owner + status — dashboard queries
db.models.createIndex({ "owner_id": 1, "status": 1 }, { name: "idx_models_owner_status" });

// Framework filter for admin analytics
db.models.createIndex({ "framework": 1 }, { name: "idx_models_framework" });

// ─────────────────────────────────────────
// Indexes: deployment_events
// ─────────────────────────────────────────

// Primary lookup: all events for a given model
db.deployment_events.createIndex({ "model_id": 1 }, { name: "idx_events_model_id" });

// Time-series queries: events sorted by creation time
db.deployment_events.createIndex({ "created_at": -1 }, { name: "idx_events_created_at" });

// Compound: model + time (paginated event log)
db.deployment_events.createIndex(
  { "model_id": 1, "created_at": -1 },
  { name: "idx_events_model_time" }
);

// ─────────────────────────────────────────
// Summary
// ─────────────────────────────────────────

print("✅ MongoDB initialized:");
print("   Collections: users, models, deployment_events");
print("   Indexes: " + [
  "users: email (unique), username (unique), is_active",
  "models: owner_id, status, owner+status, framework",
  "deployment_events: model_id, created_at, model+time"
].join(" | "));
