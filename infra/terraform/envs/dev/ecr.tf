# Registre d'images. Le scan à la poussée est gratuit ; la politique de cycle de vie
# évite d'accumuler des images (0,10 $/Go/mois).

resource "aws_ecr_repository" "api" {
  name                 = "llm-testbench-api"
  image_tag_mutability = "MUTABLE" # le tag = SHA git, mais `latest`/`dev` restent utiles
  force_delete         = true      # `make infra-down` supprime aussi les images

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
        description  = "Garder les 10 dernières images"
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
