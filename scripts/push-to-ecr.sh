#!/bin/bash
# Script para fazer build e push da imagem Docker para o AWS ECR

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

AWS_REGION=${AWS_REGION:-"us-east-1"}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID:-""}
ECR_REPO_NAME=${ECR_REPO_NAME:-"mlops-challenge"}
IMAGE_TAG=${IMAGE_TAG:-"latest"}

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}Erro: AWS_ACCOUNT_ID não foi definido.${NC}"
    echo "Execute: export AWS_ACCOUNT_ID=seu-id-da-conta"
    exit 1
fi

ECR_REPO_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo -e "${YELLOW}=== AWS ECR Push Script ===${NC}"
echo "Região: $AWS_REGION"
echo "Account ID: $AWS_ACCOUNT_ID"
echo "Repositório: $ECR_REPO_NAME"
echo "URI: $ECR_REPO_URI"
echo "Tag: $IMAGE_TAG"
echo ""

echo -e "${YELLOW}[1/5] Verificando/criando repositório no ECR...${NC}"
aws ecr describe-repositories \
    --repository-names "$ECR_REPO_NAME" \
    --region "$AWS_REGION" \
    2>/dev/null || {
    echo "Repositório não existe. Criando..."
    aws ecr create-repository \
        --repository-name "$ECR_REPO_NAME" \
        --region "$AWS_REGION"
}
echo -e "${GREEN}✓ Repositório pronto${NC}"
echo ""

echo -e "${YELLOW}[2/5] Fazendo login no ECR...${NC}"
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REPO_URI"
echo -e "${GREEN}✓ Login bem-sucedido${NC}"
echo ""

echo -e "${YELLOW}[3/5] Fazendo build da imagem Docker...${NC}"
docker build -t "${ECR_REPO_URI}:${IMAGE_TAG}" -f Dockerfile .
echo -e "${GREEN}✓ Build concluído${NC}"
echo ""

if [ "$IMAGE_TAG" != "latest" ]; then
    echo -e "${YELLOW}[4/5] Criando tag 'latest'...${NC}"
    docker tag "${ECR_REPO_URI}:${IMAGE_TAG}" "${ECR_REPO_URI}:latest"
    echo -e "${GREEN}✓ Tag criada${NC}"
    echo ""
fi

echo -e "${YELLOW}[5/5] Fazendo push para o ECR...${NC}"
docker push "${ECR_REPO_URI}:${IMAGE_TAG}"
if [ "$IMAGE_TAG" != "latest" ]; then
    docker push "${ECR_REPO_URI}:latest"
fi
echo -e "${GREEN}✓ Push concluído${NC}"
echo ""

echo -e "${GREEN}=== Sucesso! ===${NC}"
echo "Sua imagem está disponível em: ${ECR_REPO_URI}:${IMAGE_TAG}"
echo ""
echo "Agora, use essa URI no terraform.tfvars do ECS:"
echo "  container_image = \"${ECR_REPO_URI}:${IMAGE_TAG}\""
