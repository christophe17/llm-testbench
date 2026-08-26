output "cluster_name" {
  value = module.eks.cluster_name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "rds_endpoint" {
  value = aws_db_instance.main.endpoint
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}
