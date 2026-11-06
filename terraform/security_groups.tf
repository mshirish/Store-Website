# Segmentation: internet → ALB (80) → EC2 (app_port) → RDS (5432).
# Each tier only accepts traffic from the security group in front of it.

# ALB: the only thing open to the world, on plain HTTP.
resource "aws_security_group" "alb" {
  name        = "store-alb-sg"
  description = "Public HTTP to the load balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound (to targets)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "store-alb-sg" }
}

# EC2: app port reachable only from the ALB; SSH only from your IP (if given).
# Egress is open so instances can install packages, clone the repo and reach Stripe/R2.
resource "aws_security_group" "ec2" {
  name        = "store-ec2-sg"
  description = "App traffic from the ALB, SSH from my IP"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "App port from the ALB only"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  dynamic "ingress" {
    for_each = var.my_ip_cidr != "" ? [var.my_ip_cidr] : []
    content {
      description = "SSH from my IP"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "store-ec2-sg" }
}

# RDS: Postgres reachable only from the app instances — never from the internet.
resource "aws_security_group" "rds" {
  name        = "store-rds-sg"
  description = "Postgres from the app instances only"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from EC2 only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "store-rds-sg" }
}
