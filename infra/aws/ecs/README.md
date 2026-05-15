# AWS ECS Fargate + Internal NLB

Este diretório provisiona o backend privado da Inference API.

## O Que E Criado

- VPC/subnets padrão da conta/região.
- Network Load Balancer interno.
- Target group privado apontando para tasks ECS Fargate.
- Security Group das tasks aceitando entrada apenas do CIDR da VPC.
- Bucket S3 versionado para artefatos aprovados.
- Permissões IAM para a API ler artefatos no S3.
- CloudWatch Logs e alarmes básicos do backend.

O backend não é a entrada pública da aplicação. A entrada pública é o AWS API Gateway criado em `infra/aws/api-gateway`, que acessa este NLB por VPC Link.

## Como Provisionar

```bash
cd infra/aws/ecs
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

Defina `container_image` no `terraform.tfvars` com a imagem publicada pelo CI/CD, por exemplo:

```hcl
container_image = "ghcr.io/seu-usuario/mlops-challenge:latest"
```

## Outputs Importantes

Após o `apply`, use estes outputs no stack do API Gateway:

- `backend_base_url`: URL privada do NLB interno.
- `backend_nlb_arn`: ARN do NLB interno para o VPC Link.
- `artifact_bucket_name`: bucket S3 usado para publicar modelos aprovados.
- `artifact_prefix`: prefixo S3 dos modelos.

## Próximo Passo

Provisione `infra/aws/api-gateway` usando `backend_base_url` e `backend_nlb_arn`.
