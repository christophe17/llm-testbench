output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "region" {
  value = var.region
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "rds_address" {
  value = module.rds.db_instance_address
}

output "rds_port" {
  value = module.rds.db_instance_port
}

output "rds_database" {
  value = "testbench"
}

output "rds_master_secret_arn" {
  description = "Secret géré par RDS ({username, password}) : External Secrets compose l'URL de la base à partir de lui"
  value       = module.rds.db_instance_master_user_secret_arn
}

output "api_role_arn" {
  value = aws_iam_role.api.arn
}

output "external_secrets_role_arn" {
  value = aws_iam_role.external_secrets.arn
}

output "data_bucket" {
  value = aws_s3_bucket.data.bucket
}

output "secret_names" {
  description = "Clés des providers à renseigner à la main avec `aws secretsmanager put-secret-value` (guide 05)"
  value       = [for s in aws_secretsmanager_secret.api_keys : s.name]
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}
