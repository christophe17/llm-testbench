# Identity of the deployment CI (guide 09, ADR 009): GitHub Actions obtains temporary
# AWS credentials through OIDC, with no key stored on the GitHub side.
#
# Account-level resources, stable and free: they live here, not in envs/dev, which is
# destroyed every evening. The role has a fixed name; envs/dev grants it access to the
# cluster through an access entry (eks.tf) by rebuilding its ARN from that name.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # Since 2023, AWS validates GitHub's certificate through its chain of trust; the thumbprint
  # list is still required by the resource. These are the two values published by GitHub.
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

    # Only this repository, on its main branch, can assume the role: neither a fork nor a PR.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = var.github_deploy_role_name
  description          = "GitHub Actions (${var.github_repository}, main): build, push ECR, helm upgrade on the dev cluster"
  assume_role_policy   = data.aws_iam_policy_document.github_deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrLogin"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # the API accepts no finer-grained resource for this action
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

  # The workflow reads the database address and the ARN of its managed secret, to pass them
  # to the chart (guide 05): it does not touch the Terraform state.
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
