data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  ecr_repo   = "${var.project}-scraper"
  image_uri  = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${local.ecr_repo}:${var.image_tag}"
}

# --- ECR: repositorio de la imagen del scraper ---
resource "aws_ecr_repository" "scraper" {
  name                 = local.ecr_repo
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Política de ciclo de vida: conservar solo las últimas 5 imágenes (ahorra ECR).
resource "aws_ecr_lifecycle_policy" "scraper" {
  repository = aws_ecr_repository.scraper.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las últimas 5 imágenes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# --- Secrets en SSM Parameter Store (SecureString, gratis) ---
# El valor real se sube fuera de Terraform (no se commitea). Aquí se declara
# el parámetro con ignore_changes para que Terraform no lo sobrescriba.
resource "aws_ssm_parameter" "telegram_token" {
  name  = "/${var.project}/telegram_bot_token"
  type  = "SecureString"
  value = "PLACEHOLDER" # se actualiza con `aws ssm put-parameter` (ver README infra)

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "telegram_chat_id" {
  name  = "/${var.project}/telegram_chat_id"
  type  = "SecureString"
  value = "PLACEHOLDER"

  lifecycle {
    ignore_changes = [value]
  }
}
