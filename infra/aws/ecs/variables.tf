variable "aws_region" {
  description = "Região da AWS"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nome do projeto para prefixar os recursos"
  type        = string
  default     = "mlops-api"
}

variable "container_image" {
  description = "URL da imagem Docker para o container da API (ex: ghcr.io/seu-usuario/mlops-challenge:latest)"
  type        = string
  default     = "ghcr.io/seu-usuario/mlops-challenge:latest" # Mude para seu registry/imagem
}

variable "container_port" {
  description = "Porta interna do container da API"
  type        = number
  default     = 8000
}

variable "sentry_dsn" {
  type        = string
  description = "A chave DSN do Sentry para monitoramento de erros"
  default     = ""
  sensitive   = true
}

variable "sentry_environment" {
  description = "Ambiente reportado ao Sentry."
  type        = string
  default     = "production"
}

variable "sentry_traces_sample_rate" {
  description = "Taxa de amostragem de traces do Sentry."
  type        = number
  default     = 0.2
}

variable "artifact_bucket_name" {
  description = "Nome do bucket S3 para artefatos aprovados. Se vazio, um nome deterministico sera gerado."
  type        = string
  default     = ""
}

variable "artifact_prefix" {
  description = "Prefixo dentro do bucket S3 para modelos publicados."
  type        = string
  default     = "models"
}

variable "artifact_bucket_force_destroy" {
  description = "Permite destruir o bucket mesmo com objetos. Use apenas em ambientes descartaveis."
  type        = bool
  default     = false
}

variable "ecs_log_retention_days" {
  description = "Retencao dos logs da API no CloudWatch."
  type        = number
  default     = 14
}

variable "alarm_actions" {
  description = "Lista de ARNs SNS ou actions para alarmes CloudWatch. Vazio cria alarmes sem notificacao."
  type        = list(string)
  default     = []
}

variable "nlb_target_resets_alarm_threshold" {
  description = "Quantidade de resets de conexao do target em 5 minutos para disparar alarme."
  type        = number
  default     = 5
}

variable "nlb_unhealthy_hosts_threshold" {
  description = "Quantidade de targets unhealthy para disparar alarme."
  type        = number
  default     = 1
}
