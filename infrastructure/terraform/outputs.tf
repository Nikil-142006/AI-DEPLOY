output "vpc_id" {
  value       = aws_vpc.main.id
  description = "The ID of the VPC"
}

output "eks_cluster_name" {
  value       = aws_eks_cluster.main.name
  description = "The EKS cluster name"
}

output "eks_cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "The EKS cluster endpoint URL"
}

output "docdb_mongodb_endpoint" {
  value       = aws_docdb_cluster.mongodb.endpoint
  description = "The Amazon DocumentDB MongoDB-compatible cluster endpoint"
}

output "s3_bucket_arn" {
  value       = aws_s3_bucket.model_bucket.arn
  description = "The ARN of the S3 model bucket"
}

output "ecr_registry_url" {
  value       = split("/", aws_ecr_repository.auth_service.repository_url)[0]
  description = "The URL of the private ECR registry"
}
