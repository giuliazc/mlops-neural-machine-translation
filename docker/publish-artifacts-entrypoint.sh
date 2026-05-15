#!/bin/sh
set -eu

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] && [ -z "${AWS_PROFILE:-}" ] && [ -z "${AWS_WEB_IDENTITY_TOKEN_FILE:-}" ]; then
  echo "[publish-artifacts] Credenciais AWS nao encontradas; usando LocalStack para S3"
  export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
  export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION:-us-east-1}}"
  export AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
  export AWS_ENDPOINT_URL_S3="${AWS_ENDPOINT_URL_S3:-http://localstack:4566}"
  export ARTIFACT_BUCKET="${ARTIFACT_BUCKET:-mlops-local-artifacts}"
  export MLOPS_CREATE_ARTIFACT_BUCKET="${MLOPS_CREATE_ARTIFACT_BUCKET:-true}"
else
  echo "[publish-artifacts] Credenciais AWS encontradas; usando S3 configurado"
fi

exec "$@"
