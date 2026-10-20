output "tfstate_bucket" {
  description = "S3 bucket to be used as backend by the environments (phase 1+)"
  value       = aws_s3_bucket.tfstate.bucket
}

output "backend_example" {
  description = "Backend block to copy into the environment modules"
  value       = <<-EOT
    backend "s3" {
      bucket       = "${aws_s3_bucket.tfstate.bucket}"
      key          = "envs/dev/terraform.tfstate"
      region       = "${var.region}"
      use_lockfile = true
    }
  EOT
}

output "github_deploy_role_arn" {
  description = "To set in the GitHub repository: gh variable set AWS_DEPLOY_ROLE_ARN --body <value> (guide 09)"
  value       = aws_iam_role.github_deploy.arn
}
