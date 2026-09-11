# --- OIDC para GitHub Actions (deploy sin llaves estáticas) ---
# Permite que los workflows del repo asuman un rol en AWS vía token OIDC.

variable "github_repo" {
  description = "owner/repo autorizado a asumir el rol de deploy."
  type        = string
  default     = "arheanja-ops/DIAN-bot"
}

variable "github_org" {
  description = "Organización de GitHub (para el patrón de sub con IDs)."
  type        = string
  default     = "arheanja-ops"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # El `sub` de este repo incluye IDs numéricos de org y repo
    # (repo:arheanja-ops@<id>/DIAN-bot@<id>:...), así que usamos comodines que
    # restringen al org y repo concretos sin ser "scoped to all".
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_org}*/DIAN-bot*:*"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${var.project}-github-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_assume.json
}

# Permisos de deploy: push a ECR y actualizar la Lambda. (El CI de infra usa
# permisos más amplios vía un rol aparte o el mismo, según se decida; aquí
# damos lo necesario para el pipeline de la app.)
resource "aws_iam_role_policy" "github_deploy" {
  name = "${var.project}-github-deploy"
  role = aws_iam_role.github_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "EcrAuth"
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Sid    = "EcrPush"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
        ]
        Resource = aws_ecr_repository.scraper.arn
      },
      {
        Sid      = "LambdaDeploy"
        Effect   = "Allow"
        Action   = ["lambda:UpdateFunctionCode", "lambda:GetFunction"]
        Resource = aws_lambda_function.scraper.arn
      },
      {
        Sid    = "TerraformState"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::dianbot-tfstate-${local.account_id}",
          "arn:aws:s3:::dianbot-tfstate-${local.account_id}/*",
        ]
      },
      {
        Sid      = "TerraformLock"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/dianbot-tflock"
      },
    ]
  })
}

output "github_deploy_role_arn" {
  description = "ARN del rol que asumen los GitHub Actions vía OIDC."
  value       = aws_iam_role.github_deploy.arn
}
