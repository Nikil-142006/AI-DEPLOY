variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS Region to deploy resources"
}

variable "project_name" {
  type        = string
  default     = "ai-deploy"
  description = "Name of the project used for resource naming"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment (e.g. staging, production)"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "Base CIDR range for the VPC"
}

variable "eks_cluster_name" {
  type        = string
  default     = "ai-deploy-cluster"
  description = "Name of the EKS cluster"
}

variable "db_username" {
  type        = string
  default     = "aideploy"
  description = "Database administrator username"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Database administrator password"
}

variable "s3_bucket_name" {
  type        = string
  default     = "ai-deploy142006-1st"
  description = "S3 bucket name for model artifacts"
}
