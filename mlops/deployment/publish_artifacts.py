from __future__ import annotations

import argparse
import json
import os

from mlops.deployment.artifact_store import publish_run_to_s3


def configure_localstack_fallback() -> None:
    has_aws_credentials = any(
        os.getenv(name)
        for name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_PROFILE",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        )
    )
    has_custom_endpoint = bool(os.getenv("AWS_ENDPOINT_URL_S3") or os.getenv("AWS_ENDPOINT_URL"))

    if has_aws_credentials or has_custom_endpoint:
        return

    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
    os.environ.setdefault("AWS_DEFAULT_REGION", os.getenv("AWS_REGION", "us-east-1"))
    os.environ.setdefault("AWS_ENDPOINT_URL_S3", "http://localstack:4566")
    os.environ.setdefault("ARTIFACT_BUCKET", "mlops-local-artifacts")
    os.environ.setdefault("MLOPS_CREATE_ARTIFACT_BUCKET", "true")


def main() -> None:
    configure_localstack_fallback()

    parser = argparse.ArgumentParser(description="Publica artefatos de um run aprovado no S3.")
    parser.add_argument("--run_dir", required=True, help="Diretorio artifacts/<run_id>.")
    parser.add_argument(
        "--bucket",
        default=os.getenv("ARTIFACT_BUCKET", ""),
        help="Bucket S3 de artefatos. Tambem pode vir de ARTIFACT_BUCKET.",
    )
    parser.add_argument(
        "--prefix",
        default=os.getenv("ARTIFACT_PREFIX", "models"),
        help="Prefixo S3 dos modelos publicados.",
    )
    args = parser.parse_args()

    if not args.bucket:
        raise ValueError("Informe --bucket ou defina ARTIFACT_BUCKET.")

    result = publish_run_to_s3(args.run_dir, args.bucket, args.prefix)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
