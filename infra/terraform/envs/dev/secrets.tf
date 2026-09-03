# Secrets Manager : les clés des providers (valeurs posées à la main, guide 05) et l'URL
# de la base, composée ici à partir du secret géré par RDS.
#
# Compromis assumé : lire le secret RDS depuis Terraform met le mot de passe dans l'état
# (chiffré, versionné, accès restreint — guide 00). La réponse de production serait un
# template External Secrets qui compose l'URL dans le cluster, ou l'authentification IAM
# à la base. Documenté plutôt que masqué.

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

data "aws_secretsmanager_secret_version" "rds_master" {
  secret_id = module.rds.db_instance_master_user_secret_arn
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.secret_prefix}/database-url"
  description             = "URL Postgres complète pour l'API"
  recovery_window_in_days = 0

  tags = {
    Module = "secrets"
  }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql://%s:%s@%s:%s/%s",
    module.rds.db_instance_username,
    urlencode(jsondecode(data.aws_secretsmanager_secret_version.rds_master.secret_string)["password"]),
    module.rds.db_instance_address,
    module.rds.db_instance_port,
    "testbench",
  )
}
