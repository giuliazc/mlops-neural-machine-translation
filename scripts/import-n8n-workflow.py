#!/usr/bin/env python3
"""
Script para importar automaticamente o workflow do n8n.

Uso:
    python scripts/import-n8n-workflow.py \
        --n8n-url http://localhost:5678 \
        --workflow-file n8n.json
"""

import argparse
import json
import time
import sys
import requests
from pathlib import Path


def wait_for_n8n(base_url: str, timeout: int = 60) -> bool:
    """Aguarda o n8n ficar disponível."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{base_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                print(f"[SUCCESS] n8n está disponível em {base_url}")
                return True
        except requests.RequestException:
            pass
        
        time.sleep(2)
        elapsed = int(time.time() - start)
        print(f"  Aguardando n8n... ({elapsed}s)")
    
    print(f"[ERROR] n8n não respondeu após {timeout}s")
    return False


def import_workflow(base_url: str, workflow_file: str) -> bool:
    """Importa o workflow do arquivo n8n.json."""
    
    workflow_path = Path(workflow_file)
    if not workflow_path.exists():
        print(f"[ERROR] Arquivo não encontrado: {workflow_file}")
        return False
    
    try:
        with open(workflow_path, 'r') as f:
            workflow_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Erro ao ler JSON: {e}")
        return False
    
    api_url = f"{base_url}/api/v1/workflows"
    
    try:
        payload = {
            "name": workflow_data.get("name", "MLOps NMT Pipeline"),
            "nodes": workflow_data.get("nodes", []),
            "connections": workflow_data.get("connections", {}),
            "active": True,
            "settings": workflow_data.get("settings", {}),
        }
        
        # Se já existe um workflow com esse ID, atualizar
        workflow_id = workflow_data.get("id")
        if workflow_id:
            payload["id"] = workflow_id
        
        print(f"Importando workflow: {payload.get('name')}")
        
        response = requests.post(
            api_url,
            json=payload,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            imported_id = result.get("id")
            print(f"[SUCCESS] Workflow importado com sucesso! ID: {imported_id}")
            
            activate_url = f"{base_url}/api/v1/workflows/{imported_id}/activate"
            activate_response = requests.patch(activate_url, timeout=30)
            
            if activate_response.status_code == 200:
                print(f"[SUCCESS] Workflow ativado!")
                return True
            else:
                print(f"[WARNING] Aviso: Workflow importado mas falhou ao ativar (status: {activate_response.status_code})")
                return True
        else:
            print(f"[ERROR] Erro ao importar workflow (status: {response.status_code})")
            print(f"  Resposta: {response.text}")
            return False
    
    except requests.RequestException as e:
        print(f"[ERROR] Erro de conexão: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Importar automaticamente o workflow do n8n"
    )
    parser.add_argument(
        "--n8n-url",
        default="http://localhost:5678",
        help="URL base do n8n (padrão: http://localhost:5678)"
    )
    parser.add_argument(
        "--workflow-file",
        default="n8n.json",
        help="Caminho do arquivo do workflow (padrão: n8n.json)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Tempo máximo para aguardar n8n (padrão: 60s)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("n8n Workflow Auto-Importer")
    print("=" * 60)
    
    n8n_url = args.n8n_url.rstrip("/")
    
    print(f"\n[INFO] Aguardando n8n em: {n8n_url}")
    if not wait_for_n8n(n8n_url, args.timeout):
        sys.exit(1)
    
    print(f"\n[INFO] Importando workflow de: {args.workflow_file}")
    if not import_workflow(n8n_url, args.workflow_file):
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("[SUCCESS] Workflow importado e ativado com sucesso!")
    print(f"  Acesse: {n8n_url}")
    print("=" * 60)


if __name__ == "__main__":
    main()
