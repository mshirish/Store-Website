output "alb_dns_name" {
  description = "Open this in a browser (HTTP)."
  value       = "http://${aws_lb.main.dns_name}"
}

output "rds_endpoint" {
  description = "RDS endpoint (host:port), reachable only from the app instances."
  value       = aws_db_instance.main.endpoint
}
