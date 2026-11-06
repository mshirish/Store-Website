# Internet-facing Application Load Balancer spread over both public subnets.
resource "aws_lb" "main" {
  name               = "store-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = { Name = "store-alb" }
}

# Target group the ASG registers instances into, on the app port.
resource "aws_lb_target_group" "app" {
  name                 = "store-app-tg"
  port                 = var.app_port
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  target_type          = "instance"
  deregistration_delay = 30 # lab: drain quickly on scale-in / replacement

  # The app answers exactly "/healthz/" (trailing slash) before host validation and
  # without touching the DB; "/healthz" would 400 on the instance's private IP.
  health_check {
    path                = "/healthz/"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "store-app-tg" }
}

# HTTP listener on port 80 forwarding everything to the app.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
