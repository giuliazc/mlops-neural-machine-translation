variable "aws_region" {
  description = "Regiao AWS onde o API Gateway regional sera criado."
  type        = string
  default     = "us-east-1"
}

variable "api_name" {
  description = "Nome do REST API no API Gateway (identifica o gateway publico)."
  type        = string
  default     = "mlops-inference-api"
}

variable "stage_name" {
  description = "Stage publicado no API Gateway (ex: dev, prod)."
  type        = string
  default     = "dev"
}

variable "backend_base_url" {
  description = "URL privada do NLB interno que sera exposta pelo Gateway via VPC Link."
  type        = string
}

variable "vpc_link_target_arn" {
  description = "ARN do Network Load Balancer interno usado pelo API Gateway VPC Link."
  type        = string
}

variable "client_api_key_name" {
  description = "Nome da API key usada para autenticacao no Gateway."
  type        = string
  default     = "mlops-client-key"
}

variable "client_api_key_value" {
  description = "Valor real da API key (nao versionar em Git; use secrets)."
  type        = string
  sensitive   = true
}

variable "client_rate_limit" {
  description = "Rate limit sustentado (req/s) aplicado ao Gateway via usage plan."
  type        = number
  default     = 20
}

variable "client_burst_limit" {
  description = "Burst de requisicoes permitido pelo usage plan do Gateway."
  type        = number
  default     = 40
}

variable "log_retention_days" {
  description = "Retencao (dias) dos access logs do API Gateway no CloudWatch."
  type        = number
  default     = 14
}

variable "alarm_actions" {
  description = "Lista de ARNs SNS ou actions para alarmes CloudWatch. Vazio cria alarmes sem notificacao."
  type        = list(string)
  default     = []
}

variable "gateway_5xx_alarm_threshold" {
  description = "Quantidade de erros 5xx no API Gateway em 5 minutos para disparar alarme."
  type        = number
  default     = 5
}

variable "gateway_latency_alarm_threshold_ms" {
  description = "Latencia media em ms do API Gateway em 5 minutos para disparar alarme."
  type        = number
  default     = 3000
}
