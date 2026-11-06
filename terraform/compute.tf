# Latest Amazon Linux 2023 (x86_64) AMI published by Amazon.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Blueprint for each app instance: AMI, size, network, and the boot script that
# builds and starts the Docker image (see user_data.sh.tftpl).
resource "aws_launch_template" "app" {
  name_prefix   = "store-app-"
  image_id      = data.aws_ami.al2023.id
  instance_type = var.instance_type
  key_name      = var.key_name != "" ? var.key_name : null

  network_interfaces {
    associate_public_ip_address = true # public subnet + no NAT: needed for outbound
    security_groups             = [aws_security_group.ec2.id]
  }

  # IMDSv2 only.
  metadata_options {
    http_tokens = "required"
  }

  user_data = base64encode(templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url               = var.repo_url
    app_port               = var.app_port
    alb_dns_name           = aws_lb.main.dns_name
    django_secret_key      = var.django_secret_key
    database_url           = "postgres://${var.db_username}:${urlencode(var.db_password)}@${aws_db_instance.main.address}:5432/${var.db_name}"
    stripe_publishable_key = var.stripe_publishable_key
    stripe_secret_key      = var.stripe_secret_key
    r2_access_key_id       = var.r2_access_key_id
    r2_secret_access_key   = var.r2_secret_access_key
    r2_bucket_name         = var.r2_bucket_name
    r2_endpoint_url        = var.r2_endpoint_url
    r2_public_url          = var.r2_public_url
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "store-app" }
  }
}

# Keeps 1 healthy app instance (up to 2) behind the ALB, replacing any that fail
# the ALB health check.
resource "aws_autoscaling_group" "app" {
  name                = "store-app-asg"
  min_size            = 1
  desired_capacity    = 1
  max_size            = 2
  vpc_zone_identifier = aws_subnet.public[*].id
  target_group_arns   = [aws_lb_target_group.app.arn]

  health_check_type = "ELB"
  # First boot installs Docker and builds the image before the app answers; 600s
  # leaves headroom on a t3.small so a slow build isn't killed mid-boot.
  health_check_grace_period = 600

  launch_template {
    id      = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }

  # Changing the launch template (e.g. user-data) rolls instances automatically.
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 0 # lab with 1 instance: allow replace-in-place
    }
  }

  tag {
    key                 = "Name"
    value               = "store-app"
    propagate_at_launch = true
  }
}
