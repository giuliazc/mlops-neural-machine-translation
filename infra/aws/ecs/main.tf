provider "aws" {
  region = var.aws_region
}

# ========================================
# VPC & Networking (Usando VPC e Subnets Padrões)
# ========================================
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_caller_identity" "current" {}

locals {
  artifact_bucket_name = var.artifact_bucket_name != "" ? var.artifact_bucket_name : "${var.project_name}-artifacts-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}

# ========================================
# S3 Bucket para artefatos aprovados
# ========================================
resource "aws_s3_bucket" "artifacts" {
  bucket        = local.artifact_bucket_name
  force_destroy = var.artifact_bucket_force_destroy
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ========================================
# Security Groups
# ========================================
resource "aws_security_group" "ecs_tasks_sg" {
  name        = "${var.project_name}-ecs-tasks-sg"
  description = "Permitir entrada privada via NLB interno para as tasks do ECS"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = var.container_port
    to_port     = var.container_port
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ========================================
# Internal Network Load Balancer
# ========================================
resource "aws_lb" "api_nlb" {
  name               = "${var.project_name}-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = data.aws_subnets.default.ids
}

resource "aws_lb_target_group" "api_tg" {
  name        = "${var.project_name}-tg"
  port        = var.container_port
  protocol    = "TCP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api_nlb.arn
  port              = 80
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api_tg.arn
  }
}

# ========================================
# IAM Roles para o ECS
# ========================================
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "artifact_read" {
  name        = "${var.project_name}-artifact-read"
  description = "Permite que a API carregue artefatos publicados no S3."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.artifacts.arn
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "${var.artifact_prefix}/*"
            ]
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.artifacts.arn}/${var.artifact_prefix}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_artifact_read" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = aws_iam_policy.artifact_read.arn
}

# ========================================
# ECS Cluster
# ========================================
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"
}

# CloudWatch Logs Group
resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = var.ecs_log_retention_days
}

# ========================================
# ECS Task Definition & Service
# ========================================
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name      = "inference-api"
    image     = var.container_image
    essential = true
    command   = ["bash", "-lc", "uvicorn inference_api.main:app --host 0.0.0.0 --port ${var.container_port}"]
    portMappings = [{
      containerPort = var.container_port
      hostPort      = var.container_port
    }]
    environment = [
      { name = "ARTIFACTS_DIR", value = "/workspace/artifacts" },
      { name = "ARTIFACT_BUCKET", value = aws_s3_bucket.artifacts.bucket },
      { name = "ARTIFACT_PREFIX", value = var.artifact_prefix },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "DEFAULT_RUN_ID", value = "" },
      { name = "TF_CPP_MIN_LOG_LEVEL", value = "2" },
      { name = "SENTRY_DSN", value = var.sentry_dsn },
      { name = "SENTRY_ENVIRONMENT", value = var.sentry_environment },
      { name = "SENTRY_RELEASE", value = var.container_image },
      { name = "SENTRY_TRACES_SAMPLE_RATE", value = tostring(var.sentry_traces_sample_rate) }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name                  = "${var.project_name}-service"
  cluster               = aws_ecs_cluster.main.id
  task_definition       = aws_ecs_task_definition.api.arn
  desired_count         = 1
  launch_type           = "FARGATE"
  wait_for_steady_state = true

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_tasks_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api_tg.arn
    container_name   = "inference-api"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]
}

# ========================================
# CloudWatch Alarms
# ========================================
resource "aws_cloudwatch_metric_alarm" "nlb_target_resets" {
  alarm_name          = "${var.project_name}-nlb-target-resets"
  alarm_description   = "Conexoes resetadas pelos targets atras do NLB interno."
  namespace           = "AWS/NetworkELB"
  metric_name         = "TCP_Target_Reset_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.nlb_target_resets_alarm_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    LoadBalancer = aws_lb.api_nlb.arn_suffix
    TargetGroup  = aws_lb_target_group.api_tg.arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "nlb_unhealthy_hosts" {
  alarm_name          = "${var.project_name}-nlb-unhealthy-hosts"
  alarm_description   = "Targets unhealthy no target group da API."
  namespace           = "AWS/NetworkELB"
  metric_name         = "UnHealthyHostCount"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = var.nlb_unhealthy_hosts_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions

  dimensions = {
    LoadBalancer = aws_lb.api_nlb.arn_suffix
    TargetGroup  = aws_lb_target_group.api_tg.arn_suffix
  }
}
