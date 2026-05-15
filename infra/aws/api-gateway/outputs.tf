output "api_gateway_base_url" {
  description = "URL base publica do API Gateway para consumir /health, /metrics, /predict e /reload."
  value       = "https://${aws_api_gateway_rest_api.inference.id}.execute-api.${var.aws_region}.amazonaws.com/${var.stage_name}"
}

output "rest_api_id" {
  description = "ID do REST API do API Gateway."
  value       = aws_api_gateway_rest_api.inference.id
}

output "stage_name" {
  description = "Stage publicado do API Gateway."
  value       = aws_api_gateway_stage.inference.stage_name
}

output "client_api_key_id" {
  description = "ID da API key usada para autenticacao; o valor secreto deve ser consultado/rotacionado com cuidado."
  value       = aws_api_gateway_api_key.client.id
}

output "access_log_group_name" {
  description = "Log group dos access logs do API Gateway (CloudWatch)."
  value       = aws_cloudwatch_log_group.access_logs.name
}

output "vpc_link_id" {
  description = "ID do VPC Link usado pelo API Gateway para acessar o NLB interno."
  value       = aws_api_gateway_vpc_link.backend.id
}

output "gateway_5xx_alarm_name" {
  description = "Alarme CloudWatch para erros 5xx no API Gateway."
  value       = aws_cloudwatch_metric_alarm.gateway_5xx.alarm_name
}

output "gateway_latency_alarm_name" {
  description = "Alarme CloudWatch para latencia no API Gateway."
  value       = aws_cloudwatch_metric_alarm.gateway_latency.alarm_name
}
