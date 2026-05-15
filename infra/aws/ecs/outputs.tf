output "backend_base_url" {
  description = "URL base privada do NLB interno do ECS, usada pelo API Gateway via VPC Link."
  value       = "http://${aws_lb.api_nlb.dns_name}"
}

output "backend_nlb_arn" {
  description = "ARN do NLB interno usado pelo API Gateway VPC Link."
  value       = aws_lb.api_nlb.arn
}

output "backend_target_group_arn" {
  description = "ARN do target group do backend ECS."
  value       = aws_lb_target_group.api_tg.arn
}

output "artifact_bucket_name" {
  description = "Bucket S3 usado para armazenar artefatos aprovados por run_id."
  value       = aws_s3_bucket.artifacts.bucket
}

output "artifact_prefix" {
  description = "Prefixo S3 usado para modelos publicados."
  value       = var.artifact_prefix
}

output "ecs_log_group_name" {
  description = "Log group CloudWatch da API no ECS."
  value       = aws_cloudwatch_log_group.ecs_logs.name
}

output "nlb_target_resets_alarm_name" {
  description = "Alarme CloudWatch para resets de conexao no NLB target."
  value       = aws_cloudwatch_metric_alarm.nlb_target_resets.alarm_name
}

output "nlb_unhealthy_hosts_alarm_name" {
  description = "Alarme CloudWatch para targets unhealthy."
  value       = aws_cloudwatch_metric_alarm.nlb_unhealthy_hosts.alarm_name
}
