# Bucket de travail : caches de jeux de données et artefacts d'évaluation (phase 2+).
# Expiration à 30 jours : rien ici n'est une source de vérité, tout se régénère.

resource "aws_s3_bucket" "data" {
  bucket        = "${var.name}-data-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Module = "s3"
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "expire-30d"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}
