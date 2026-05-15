from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


def read_run_id(run_dir: Path) -> str:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        return run_dir.name

    with metadata_path.open("r", encoding="utf-8") as fp:
        metadata = json.load(fp)
    return str(metadata.get("run_id") or run_dir.name)


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def publish_run_to_s3(run_dir: str | Path, bucket: str, prefix: str = "models", s3_client=None) -> dict:
    run_path = Path(run_dir)
    if not run_path.exists() or not run_path.is_dir():
        raise FileNotFoundError(f"Diretorio de run nao encontrado: {run_path}")

    saved_model_dir = run_path / "saved_model"
    if not saved_model_dir.exists() or not saved_model_dir.is_dir():
        raise FileNotFoundError(f"SavedModel nao encontrado: {saved_model_dir}")

    run_id = read_run_id(run_path)
    clean_prefix = prefix.strip("/")
    key_prefix = "/".join(part for part in [clean_prefix, run_id] if part)
    endpoint_url = os.getenv("AWS_ENDPOINT_URL_S3") or os.getenv("AWS_ENDPOINT_URL")

    if s3_client is None:
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise RuntimeError(
                "boto3 não está instalado; instale as dependências atualizadas para publicar artefatos no S3."
            ) from exc

        s3_client = boto3.client("s3", endpoint_url=endpoint_url)

        if os.getenv("MLOPS_CREATE_ARTIFACT_BUCKET", "").lower() in {"1", "true", "yes"}:
            try:
                s3_client.head_bucket(Bucket=bucket)
            except ClientError:
                create_kwargs = {"Bucket": bucket}
                region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
                if region and region != "us-east-1":
                    create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
                s3_client.create_bucket(**create_kwargs)

    uploaded_files = []

    for file_path in iter_files(run_path):
        relative_path = file_path.relative_to(run_path).as_posix()
        key = f"{key_prefix}/{relative_path}" if key_prefix else relative_path
        s3_client.upload_file(str(file_path), bucket, key)
        uploaded_files.append(key)

    local_only = bool(endpoint_url and "localstack" in endpoint_url)

    return {
        "run_id": run_id,
        "bucket": bucket,
        "prefix": clean_prefix,
        "s3_uri": f"s3://{bucket}/{key_prefix}",
        "uploaded_files": len(uploaded_files),
        "storage_backend": "localstack" if local_only else "s3",
        "endpoint_url": endpoint_url or "",
        "local_only": local_only,
    }
