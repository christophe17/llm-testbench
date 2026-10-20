# Image registry. Scan on push is free; the lifecycle policy avoids piling up images
# ($0.10/GB/month).

resource "aws_ecr_repository" "api" {
  name                 = "llm-testbench-api"
  image_tag_mutability = "MUTABLE" # the tag = git SHA, but `latest`/`dev` remain useful
  force_delete         = true      # `make infra-down` deletes the images too

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Module = "ecr"
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}
