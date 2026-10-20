# Pod identities (EKS Pod Identity): one role per workload, no shared key. The API gets
# the right to call Bedrock; External Secrets the right to read our secrets, and nothing
# else.

data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

# --- API: Bedrock ----------------------------------------------------------------

resource "aws_iam_role" "api" {
  name               = "${var.name}-api"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json

  tags = {
    Module = "iam"
  }
}

data "aws_iam_policy_document" "api_bedrock" {
  statement {
    sid    = "InvokeBedrockModels"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]
    # Foundation models of the region and EU inference profiles (eu. prefix)
    resources = [
      "arn:aws:bedrock:${var.region}::foundation-model/*",
      "arn:aws:bedrock:eu-*::foundation-model/*",
      "arn:aws:bedrock:${var.region}:${data.aws_caller_identity.current.account_id}:inference-profile/eu.*",
    ]
  }

  statement {
    sid       = "ListModels"
    effect    = "Allow"
    actions   = ["bedrock:ListFoundationModels", "bedrock:GetFoundationModel"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "api_bedrock" {
  name   = "bedrock-invoke"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api_bedrock.json
}

resource "aws_eks_pod_identity_association" "api" {
  cluster_name    = module.eks.cluster_name
  namespace       = var.api_namespace
  service_account = var.api_service_account
  role_arn        = aws_iam_role.api.arn
}

# --- External Secrets: read our secrets only ----------------------------------------

resource "aws_iam_role" "external_secrets" {
  name               = "${var.name}-external-secrets"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json

  tags = {
    Module = "iam"
  }
}

data "aws_iam_policy_document" "external_secrets" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
      "secretsmanager:ListSecretVersionIds",
    ]
    resources = [
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${local.secret_prefix}/*",
      # The RDS-managed secret ({username, password}): External Secrets composes the
      # database URL in the cluster from it (guide 05, ADR 009).
      module.rds.db_instance_master_user_secret_arn,
    ]
  }
}

resource "aws_iam_role_policy" "external_secrets" {
  name   = "read-llm-testbench-secrets"
  role   = aws_iam_role.external_secrets.id
  policy = data.aws_iam_policy_document.external_secrets.json
}

resource "aws_eks_pod_identity_association" "external_secrets" {
  cluster_name    = module.eks.cluster_name
  namespace       = var.external_secrets_namespace
  service_account = "external-secrets"
  role_arn        = aws_iam_role.external_secrets.arn
}
