output "tfstate_bucket" {
  description = "Bucket S3 à utiliser comme backend par les environnements (phase 1+)"
  value       = aws_s3_bucket.tfstate.bucket
}

output "backend_example" {
  description = "Bloc backend à copier dans les modules d'environnement"
  value       = <<-EOT
    backend "s3" {
      bucket       = "${aws_s3_bucket.tfstate.bucket}"
      key          = "envs/dev/terraform.tfstate"
      region       = "${var.region}"
      use_lockfile = true
    }
  EOT
}
