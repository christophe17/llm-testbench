# Identité de la CI de déploiement (guide 09, ADR 009) : GitHub Actions obtient des
# identifiants AWS temporaires par OIDC, sans aucune clé stockée côté GitHub.
#
# Ressources de compte, stables et gratuites : elles vivent ici, pas dans envs/dev qui
# est détruit chaque soir. Le rôle porte un nom fixe ; envs/dev lui ouvre l'accès au
# cluster par une access entry (eks.tf) en reconstruisant son ARN à partir de ce nom.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # Depuis 2023, AWS valide le certificat de GitHub par sa chaîne de confiance ; la liste
  # d'empreintes reste exigée par la ressource. Ce sont les deux valeurs publiées par GitHub.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

data "aws_iam_policy_document" "github_deploy_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Seul ce dépôt, sur sa branche main, peut assumer le rôle : ni un fork, ni une PR.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = var.github_deploy_role_name
  description          = "GitHub Actions (${var.github_repository}, main) : build, push ECR, helm upgrade sur le cluster dev"
  assume_role_policy   = data.aws_iam_policy_document.github_deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrLogin"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # l'API n'accepte pas de ressource plus fine pour cette action
  }

  statement {
    sid    = "EcrPushApiImage"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = ["arn:aws:ecr:${var.region}:${data.aws_caller_identity.current.account_id}:repository/${var.ecr_repository_name}"]
  }

  statement {
    sid       = "EksKubeconfig"
    effect    = "Allow"
    actions   = ["eks:DescribeCluster"]
    resources = ["arn:aws:eks:${var.region}:${data.aws_caller_identity.current.account_id}:cluster/${var.dev_environment_name}"]
  }

  # Le workflow lit l'adresse de la base et l'ARN de son secret géré, pour les passer au
  # chart (guide 05) : il ne touche pas à l'état Terraform.
  statement {
    sid       = "RdsEndpoint"
    effect    = "Allow"
    actions   = ["rds:DescribeDBInstances"]
    resources = ["arn:aws:rds:${var.region}:${data.aws_caller_identity.current.account_id}:db:${var.dev_environment_name}"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "deploy-dev"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
