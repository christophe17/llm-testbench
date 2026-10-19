# Secrets Manager : les clés des providers, créées vides ici et posées à la main (guide 05).
#
# L'URL de la base n'est plus composée par Terraform : le mot de passe est généré par RDS
# dans un secret géré (`manage_master_user_password`, rds.tf) et External Secrets compose
# l'URL dans le cluster, à partir de ce secret et de l'adresse passée au chart
# (templates/externalsecret.yaml). Le mot de passe ne traverse ni l'état Terraform, ni un
# second secret (ADR 009).

resource "aws_secretsmanager_secret" "api_keys" {
  for_each = local.api_secrets

  name                    = "${local.secret_prefix}/${each.key}"
  description             = "Clé ${each.value} de l'API llm-testbench (${var.environment})"
  recovery_window_in_days = 0 # destruction immédiate avec l'environnement

  tags = {
    Module = "secrets"
  }
}

# Valeur initiale factice : à remplacer avec `aws secretsmanager put-secret-value`.
resource "aws_secretsmanager_secret_version" "api_keys_placeholder" {
  for_each = aws_secretsmanager_secret.api_keys

  secret_id     = each.value.id
  secret_string = "REPLACE_ME"

  lifecycle {
    ignore_changes = [secret_string] # la vraie valeur, posée à la main, n'est jamais écrasée
  }
}
