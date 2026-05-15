# AWS API Gateway

Este componente expõe a Inference API por uma URL pública e aplica API key, rate limiting, access logs e alarmes. A integração com o backend é privada via VPC Link para o NLB interno criado em `infra/aws/ecs`.

## Como Executar

```bash
cd infra/aws/api-gateway
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

Preencha no `terraform.tfvars`:

- `backend_base_url`: output `backend_base_url` do stack ECS.
- `vpc_link_target_arn`: output `backend_nlb_arn` do stack ECS.
- `client_api_key_value`: chave real usada pelos clientes/n8n.
- limites de rate/burst, se desejar.

## O Que E Criado

- REST API regional no API Gateway.
- VPC Link para o NLB interno.
- Recursos:
  - `GET /health`
  - `GET /model`
  - `GET /metrics`
  - `POST /predict`
  - `POST /reload`
- API key de cliente.
- Usage plan com rate limit.
- Access logs em CloudWatch.
- Métricas, method logging e alarmes CloudWatch.

## Chamadas De Teste

Depois do `apply`, use o output `api_gateway_base_url`.

```bash
curl -i "$API_GATEWAY_BASE_URL/health" \
  -H "x-api-key: $CLIENT_API_KEY"
```

```bash
curl -i "$API_GATEWAY_BASE_URL/predict" \
  -H "content-type: application/json" \
  -H "x-api-key: $CLIENT_API_KEY" \
  -d '{"text":"hello"}'
```

```bash
curl -i "$API_GATEWAY_BASE_URL/reload" \
  -H "content-type: application/json" \
  -H "x-api-key: $CLIENT_API_KEY" \
  -d '{"run_id":"nmt_20260508T120000Z_abc123"}'
```

## Criterios De Aceite

| Criterio | Validacao |
|---|---|
| API protegida | Chamadas sem `x-api-key` retornam `403` |
| Todos os endpoints passam pelo Gateway | `/health`, `/model`, `/metrics`, `/predict` e `/reload` respondem pela URL do API Gateway |
| Backend privado | O backend fica atras de NLB interno e VPC Link, sem URL pública direta |
| Rate limit ativo | Uso acima do limite retorna `429` |
| Logging ativo | Access logs aparecem em `/aws/apigateway/<api>-<stage>` |

## Observacoes

O API Gateway REST API exige que API keys sejam associadas a usage plans. O valor da chave nao e salvo neste repositorio; consulte ou rotacione a chave de forma segura pela AWS CLI/Console, Secrets Manager ou pipeline de provisionamento.
