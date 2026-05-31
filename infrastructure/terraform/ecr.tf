resource "aws_ecr_repository" "auth_service" {
  name                 = "ai-deploy/auth-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "model_service" {
  name                 = "ai-deploy/model-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "inference_service" {
  name                 = "ai-deploy/inference-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "worker_service" {
  name                 = "ai-deploy/worker-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Unified ECR repo for serving models (matches builder.py tag path)
resource "aws_ecr_repository" "models" {
  name                 = "ai-deploy/models"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Simple lifecycle policy to keep last 100 images and clean up older untagged ones
resource "aws_ecr_lifecycle_policy" "cleanup_policy" {
  for_each = toset([
    aws_ecr_repository.auth_service.name,
    aws_ecr_repository.model_service.name,
    aws_ecr_repository.inference_service.name,
    aws_ecr_repository.worker_service.name,
    aws_ecr_repository.models.name
  ])

  repository = each.value

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 14 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 100 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 100
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
