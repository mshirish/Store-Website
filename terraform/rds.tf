# Places RDS in the two private subnets (RDS requires subnets in 2+ AZs even for Single-AZ).
resource "aws_db_subnet_group" "main" {
  name       = "store-db-subnets"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "store-db-subnets" }
}

# Postgres 16, Single-AZ, private, and disposable (no final snapshot or deletion protection).
resource "aws_db_instance" "main" {
  identifier     = "store-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  multi_az               = false
  publicly_accessible    = false

  skip_final_snapshot = true
  deletion_protection = false
  apply_immediately   = true

  tags = { Name = "store-db" }
}
