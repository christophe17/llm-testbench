# RDS PostgreSQL 16 avec pgvector (disponible nativement : `CREATE EXTENSION vector`,
# exécuté par l'application au démarrage). Plus petite instance, mono-AZ, sans snapshot
# final : c'est un environnement de dev détruit et recréé, pas une base de production.

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 7.2"

  identifier = var.name

  engine               = "postgres"
  engine_version       = "16"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = var.db_instance_class

  allocated_storage     = var.db_allocated_storage_gb
  max_allocated_storage = var.db_allocated_storage_gb * 2
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = "testbench"
  username = "testbench"
  port     = 5432

  # Mot de passe géré par RDS dans Secrets Manager (jamais dans le code ni les variables).
  manage_master_user_password = true

  multi_az               = false
  db_subnet_group_name   = module.vpc.database_subnet_group_name
  create_db_subnet_group = false
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false
  apply_immediately       = true

  performance_insights_enabled = false
  monitoring_interval          = 0

  parameters = [
    { name = "log_min_duration_statement", value = "1000" }, # requêtes > 1 s dans les logs
  ]

  tags = {
    Module = "rds"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds"
  description = "Postgres depuis les noeuds EKS uniquement"
  vpc_id      = module.vpc.vpc_id

  tags = {
    Module = "rds"
  }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_nodes" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = module.eks.node_security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "EKS nodes -> Postgres"
}
