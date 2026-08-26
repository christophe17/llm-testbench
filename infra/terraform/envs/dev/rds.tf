# RDS Postgres avec pgvector (extension incluse dans RDS PG 15+ : `CREATE EXTENSION vector`
# est exécuté par la migration applicative, pas par Terraform).

resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "rds" {
  name   = "${var.name}-rds"
  vpc_id = module.vpc.vpc_id

  ingress {
    description     = "Postgres depuis les nœuds EKS uniquement"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_db_instance" "main" {
  identifier     = var.name
  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro" # arm64, ~13 $/mois, arrêtable 7 jours

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_encrypted     = true

  db_name  = "testbench"
  username = "testbench"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  backup_retention_period = 3
  skip_final_snapshot     = true # dev : l'environnement est jetable
  deletion_protection     = false
}
