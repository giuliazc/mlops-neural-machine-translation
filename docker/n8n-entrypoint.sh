#!/bin/sh
set -eu

WORKFLOW_FILE="${N8N_AUTO_IMPORT_WORKFLOW:-/workspace/n8n.json}"
WORKFLOW_ID="${N8N_AUTO_IMPORT_WORKFLOW_ID:-mlops-nmt-pipeline}"
N8N_HOME="${N8N_USER_FOLDER:-/home/node}/.n8n"
CHECKSUM_FILE="${N8N_HOME}/.mlops-workflow.sha256"

mkdir -p "${N8N_HOME}"

if [ -f "${WORKFLOW_FILE}" ]; then
  WORKFLOW_CHECKSUM="$(sha256sum "${WORKFLOW_FILE}" | awk '{print $1}')"
  PREVIOUS_CHECKSUM="$(cat "${CHECKSUM_FILE}" 2>/dev/null || true)"

  if [ "${WORKFLOW_CHECKSUM}" != "${PREVIOUS_CHECKSUM}" ]; then
    echo "[n8n-bootstrap] Importando workflow ${WORKFLOW_FILE}"
    n8n import:workflow --input="${WORKFLOW_FILE}"

    echo "[n8n-bootstrap] Publicando workflow ${WORKFLOW_ID}"
    if ! n8n publish:workflow --id="${WORKFLOW_ID}"; then
      echo "[n8n-bootstrap] publish:workflow indisponivel, usando update:workflow legado"
      n8n update:workflow --id="${WORKFLOW_ID}" --active=true
    fi

    echo "${WORKFLOW_CHECKSUM}" > "${CHECKSUM_FILE}"
    echo "[n8n-bootstrap] Workflow importado e publicado"
  else
    echo "[n8n-bootstrap] Workflow ja esta sincronizado"
  fi
else
  echo "[n8n-bootstrap] Workflow ${WORKFLOW_FILE} nao encontrado; iniciando n8n sem importacao automatica"
fi

if [ "$#" -eq 0 ]; then
  exec n8n start
fi

exec "$@"
