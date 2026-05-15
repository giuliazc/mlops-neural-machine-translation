# ========================================
# IAM Role para CloudWatch Logs
# ========================================
resource "aws_iam_role" "api_gateway_logs" {
  name = "api-gateway-cloudwatch-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "apigateway.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "api_gateway_logs" {
  role       = aws_iam_role.api_gateway_logs.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_logs.arn

  depends_on = [aws_iam_role_policy_attachment.api_gateway_logs]
}

locals {
  openapi_body = templatefile("${path.module}/openapi.yaml.tftpl", {
    api_name         = var.api_name
    backend_base_url = var.backend_base_url
    vpc_link_id      = aws_api_gateway_vpc_link.backend.id
  })

  access_log_format = jsonencode({
    requestId          = "$context.requestId"
    apiKeyId           = "$context.identity.apiKeyId"
    sourceIp           = "$context.identity.sourceIp"
    requestTime        = "$context.requestTime"
    httpMethod         = "$context.httpMethod"
    resourcePath       = "$context.resourcePath"
    status             = "$context.status"
    protocol           = "$context.protocol"
    responseLength     = "$context.responseLength"
    integrationLatency = "$context.integrationLatency"
  })
}

resource "aws_api_gateway_vpc_link" "backend" {
  name        = "${var.api_name}-${var.stage_name}-vpc-link"
  description = "VPC Link para o NLB interno da Inference API"
  target_arns = [var.vpc_link_target_arn]
}

resource "aws_api_gateway_rest_api" "inference" {
  name        = var.api_name
  description = "API Gateway publico para expor a Inference API com API key e rate limiting"
  body        = local.openapi_body

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}



resource "aws_cloudwatch_log_group" "access_logs" {
  name              = "/aws/apigateway/${var.api_name}-${var.stage_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_api_gateway_deployment" "inference" {
  rest_api_id = aws_api_gateway_rest_api.inference.id

  triggers = {
    redeployment = sha1(local.openapi_body)
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_rest_api.inference,
    aws_api_gateway_vpc_link.backend,
  ]
}

resource "aws_api_gateway_stage" "inference" {
  rest_api_id   = aws_api_gateway_rest_api.inference.id
  deployment_id = aws_api_gateway_deployment.inference.id
  stage_name    = var.stage_name

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access_logs.arn
    format          = local.access_log_format
  }

  depends_on = [aws_api_gateway_account.main]
}

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.inference.id
  stage_name  = aws_api_gateway_stage.inference.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = false
  }
}

resource "aws_api_gateway_api_key" "client" {
  name        = var.client_api_key_name
  description = "API key para clientes consumirem a Inference API via Gateway"
  enabled     = true
  value       = var.client_api_key_value
}


resource "aws_api_gateway_usage_plan" "client" {
  name        = "${var.api_name}-client-plan"
  description = "Usage plan com rate limiting para clientes da Inference API"

  api_stages {
    api_id = aws_api_gateway_rest_api.inference.id
    stage  = aws_api_gateway_stage.inference.stage_name
  }

  throttle_settings {
    rate_limit  = var.client_rate_limit
    burst_limit = var.client_burst_limit
  }
}


resource "aws_api_gateway_usage_plan_key" "client" {
  key_id        = aws_api_gateway_api_key.client.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.client.id
}

# ========================================
# CloudWatch Alarms
# ========================================
resource "aws_cloudwatch_metric_alarm" "gateway_5xx" {
  alarm_name          = "${var.api_name}-${var.stage_name}-5xx"
  alarm_description   = "Erros 5xx retornados pelo API Gateway."
  namespace           = "AWS/ApiGateway"
  metric_name         = "5XXError"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.gateway_5xx_alarm_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    ApiName = var.api_name
    Stage   = aws_api_gateway_stage.inference.stage_name
  }
}

resource "aws_cloudwatch_metric_alarm" "gateway_latency" {
  alarm_name          = "${var.api_name}-${var.stage_name}-latency"
  alarm_description   = "Latencia media alta no API Gateway."
  namespace           = "AWS/ApiGateway"
  metric_name         = "Latency"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.gateway_latency_alarm_threshold_ms
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    ApiName = var.api_name
    Stage   = aws_api_gateway_stage.inference.stage_name
  }
}
