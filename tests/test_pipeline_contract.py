import json
import os
import sys
import types
from pathlib import Path

import pytest

from mlops.deployment import publish_artifacts
from mlops.deployment.artifact_store import read_run_id
from mlops.deployment.artifact_store import publish_run_to_s3
from mlops.deployment.publish_artifacts import configure_localstack_fallback
from mlops.validation.quality_gate import ModelValidator


class FakeS3Client:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, str]] = []
        self.head_bucket_calls: list[str] = []
        self.created_buckets: list[dict] = []

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.uploads.append((filename, bucket, key))

    def head_bucket(self, Bucket: str) -> None:
        self.head_bucket_calls.append(Bucket)

    def create_bucket(self, **kwargs) -> None:
        self.created_buckets.append(kwargs)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_run_dir(tmp_path: Path, *, status: str, metric_value: float, threshold: float = 0.30) -> Path:
    run_id = f"nmt_{status}"
    run_dir = tmp_path / run_id
    saved_model_dir = run_dir / "saved_model"
    saved_model_dir.mkdir(parents=True)
    (saved_model_dir / "saved_model.pb").write_bytes(b"fake saved model")

    write_json(
        run_dir / "metadata.json",
        {
            "run_id": run_id,
            "status": status,
            "threshold": threshold,
            "metric_name": "val_token_accuracy",
            "metric_value": metric_value,
            "git_sha": "test-sha",
        },
    )
    write_json(run_dir / "metrics.json", {"val_token_accuracy": metric_value})
    write_json(run_dir / "hyperparameters.json", {"epochs": 1, "batch_size": 8})
    return run_dir


def load_n8n_workflow() -> dict:
    with Path("n8n.json").open(encoding="utf-8") as fp:
        return json.load(fp)


def connection_targets(workflow: dict, node_name: str, output_index: int = 0) -> list[str]:
    outputs = workflow["connections"][node_name]["main"]
    if output_index >= len(outputs):
        return []
    return [edge["node"] for edge in outputs[output_index]]


def node_by_name(workflow: dict, name: str) -> dict:
    return next(node for node in workflow["nodes"] if node["name"] == name)


def test_approved_run_passes_gate_and_publishes_expected_s3_keys(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, status="approved", metric_value=0.45)
    approved, reason = ModelValidator(run_dir).validate()
    assert approved is True, reason

    s3 = FakeS3Client()
    result = publish_run_to_s3(run_dir, bucket="mlops-artifacts", prefix="models", s3_client=s3)

    assert result["run_id"] == "nmt_approved"
    assert result["bucket"] == "mlops-artifacts"
    assert result["prefix"] == "models"
    assert result["s3_uri"] == "s3://mlops-artifacts/models/nmt_approved"
    assert result["uploaded_files"] == 4
    assert result["storage_backend"] == "s3"
    assert result["endpoint_url"] == ""
    assert result["local_only"] is False
    uploaded_keys = {key for _, _, key in s3.uploads}
    assert uploaded_keys == {
        "models/nmt_approved/saved_model/saved_model.pb",
        "models/nmt_approved/metadata.json",
        "models/nmt_approved/metrics.json",
        "models/nmt_approved/hyperparameters.json",
    }


def test_rejected_run_is_blocked_before_publication(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, status="rejected", metric_value=0.10)
    approved, reason = ModelValidator(run_dir).validate()

    assert approved is False
    assert "abaixo do threshold" in reason

    s3 = FakeS3Client()
    if approved:
        publish_run_to_s3(run_dir, bucket="mlops-artifacts", s3_client=s3)

    assert s3.uploads == []


def test_publish_requires_saved_model_directory(tmp_path: Path):
    run_dir = tmp_path / "nmt_missing_model"
    run_dir.mkdir()
    write_json(run_dir / "metadata.json", {"run_id": "nmt_missing_model"})

    with pytest.raises(FileNotFoundError, match="SavedModel nao encontrado"):
        publish_run_to_s3(run_dir, bucket="mlops-artifacts", s3_client=FakeS3Client())


def test_publish_requires_existing_run_directory(tmp_path: Path):
    missing_run_dir = tmp_path / "missing_run"

    with pytest.raises(FileNotFoundError, match="Diretorio de run nao encontrado"):
        publish_run_to_s3(missing_run_dir, bucket="mlops-artifacts", s3_client=FakeS3Client())


def test_read_run_id_falls_back_to_directory_name(tmp_path: Path):
    run_dir = tmp_path / "nmt_without_metadata"
    run_dir.mkdir()

    assert read_run_id(run_dir) == "nmt_without_metadata"


def test_publish_without_prefix_uploads_keys_relative_to_run_dir(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, status="approved", metric_value=0.45)
    s3 = FakeS3Client()

    result = publish_run_to_s3(run_dir, bucket="mlops-artifacts", prefix="", s3_client=s3)

    assert result["s3_uri"] == "s3://mlops-artifacts/nmt_approved"
    uploaded_keys = {key for _, _, key in s3.uploads}
    assert "nmt_approved/metadata.json" in uploaded_keys
    assert "nmt_approved/saved_model/saved_model.pb" in uploaded_keys


def test_publish_uses_localstack_fallback_without_aws_credentials(monkeypatch: pytest.MonkeyPatch):
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_ENDPOINT_URL",
        "AWS_ENDPOINT_URL_S3",
        "ARTIFACT_BUCKET",
        "MLOPS_CREATE_ARTIFACT_BUCKET",
    ):
        monkeypatch.delenv(name, raising=False)

    configure_localstack_fallback()

    assert os.environ["AWS_ACCESS_KEY_ID"] == "test"
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == "test"
    assert os.environ["AWS_ENDPOINT_URL_S3"] == "http://localstack:4566"
    assert os.environ["ARTIFACT_BUCKET"] == "mlops-local-artifacts"
    assert os.environ["MLOPS_CREATE_ARTIFACT_BUCKET"] == "true"


def test_localstack_fallback_is_skipped_when_credentials_exist(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "real-key")
    monkeypatch.delenv("AWS_ENDPOINT_URL_S3", raising=False)

    configure_localstack_fallback()

    assert os.getenv("AWS_ENDPOINT_URL_S3") is None
    assert os.environ["AWS_ACCESS_KEY_ID"] == "real-key"


def test_publish_creates_bucket_with_injected_boto3_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeClientError(Exception):
        pass

    class FakeBoto3:
        def __init__(self, client: FakeS3Client) -> None:
            self.client_instance = client
            self.calls: list[tuple[str, str]] = []

        def client(self, service_name: str, endpoint_url: str = "") -> FakeS3Client:
            self.calls.append((service_name, endpoint_url))
            return self.client_instance

    class MissingBucketS3(FakeS3Client):
        def head_bucket(self, Bucket: str) -> None:
            super().head_bucket(Bucket)
            raise FakeClientError("missing bucket")

    s3 = MissingBucketS3()
    fake_boto3 = FakeBoto3(s3)
    fake_botocore_exceptions = types.SimpleNamespace(ClientError=FakeClientError)
    fake_botocore = types.SimpleNamespace(exceptions=fake_botocore_exceptions)
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore_exceptions)
    monkeypatch.setenv("MLOPS_CREATE_ARTIFACT_BUCKET", "true")
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "http://localstack:4566")
    monkeypatch.setenv("AWS_REGION", "sa-east-1")
    run_dir = make_run_dir(tmp_path, status="approved", metric_value=0.45)

    result = publish_run_to_s3(run_dir, bucket="mlops-local-artifacts", prefix="models")

    assert fake_boto3.calls == [("s3", "http://localstack:4566")]
    assert s3.head_bucket_calls == ["mlops-local-artifacts"]
    assert s3.created_buckets == [
        {
            "Bucket": "mlops-local-artifacts",
            "CreateBucketConfiguration": {"LocationConstraint": "sa-east-1"},
        }
    ]
    assert result["uploaded_files"] == 4


def test_publish_artifacts_main_prints_publication_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    run_dir = make_run_dir(tmp_path, status="approved", metric_value=0.45)

    def fake_publish(run_dir_arg: str, bucket: str, prefix: str) -> dict:
        return {
            "run_id": Path(run_dir_arg).name,
            "bucket": bucket,
            "prefix": prefix,
        }

    monkeypatch.setattr(publish_artifacts, "configure_localstack_fallback", lambda: None)
    monkeypatch.setattr(publish_artifacts, "publish_run_to_s3", fake_publish)
    monkeypatch.setattr(
        sys,
        "argv",
        ["publish_artifacts", "--run_dir", str(run_dir), "--bucket", "mlops-artifacts", "--prefix", "prod"],
    )

    publish_artifacts.main()

    assert json.loads(capsys.readouterr().out) == {
        "run_id": "nmt_approved",
        "bucket": "mlops-artifacts",
        "prefix": "prod",
    }


def test_publish_artifacts_main_requires_bucket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_dir = make_run_dir(tmp_path, status="approved", metric_value=0.45)
    monkeypatch.setattr(publish_artifacts, "configure_localstack_fallback", lambda: None)
    monkeypatch.setattr(sys, "argv", ["publish_artifacts", "--run_dir", str(run_dir)])
    monkeypatch.delenv("ARTIFACT_BUCKET", raising=False)

    with pytest.raises(ValueError, match="Informe --bucket"):
        publish_artifacts.main()


def test_publish_marks_localstack_publication_as_local_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", "http://localstack:4566")
    run_dir = make_run_dir(tmp_path, status="approved", metric_value=0.45)

    result = publish_run_to_s3(run_dir, bucket="mlops-local-artifacts", prefix="models", s3_client=FakeS3Client())

    assert result["storage_backend"] == "localstack"
    assert result["endpoint_url"] == "http://localstack:4566"
    assert result["local_only"] is True


def test_n8n_approved_path_publishes_to_s3_before_reload():
    workflow = load_n8n_workflow()
    compose_file = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert connection_targets(workflow, "Validar Threshold de Qualidade", 0) == ["Publicar Artefatos - Container"]
    assert connection_targets(workflow, "Publicar Artefatos - Container") == ["Consolidar Publicacao"]
    assert connection_targets(workflow, "Consolidar Publicacao") == ["Verificar Backend de Artefatos"]
    assert connection_targets(workflow, "Verificar Backend de Artefatos", 0) == ["Resposta - Publicacao Local"]
    assert connection_targets(workflow, "Verificar Backend de Artefatos", 1) == ["Recarregar Modelo Publicado"]
    assert connection_targets(workflow, "Recarregar Modelo Publicado") == ["Resposta - Sucesso"]

    publish_command = node_by_name(workflow, "Publicar Artefatos - Container")["parameters"]["command"]
    assert "docker compose --profile publish run" in publish_command
    assert " publish_artifacts" in publish_command
    assert " train " not in publish_command
    assert "ARTIFACT_BUCKET" in publish_command
    assert "AWS_ENDPOINT_URL_S3" in publish_command
    assert "MLOPS_CREATE_ARTIFACT_BUCKET" in publish_command
    assert "publish_artifacts:" in compose_file
    assert "python -m mlops.deployment.publish_artifacts" in compose_file
    assert "localstack:" in compose_file

    backend_node = node_by_name(workflow, "Verificar Backend de Artefatos")
    assert "local_only" in json.dumps(backend_node)
    local_response = node_by_name(workflow, "Resposta - Publicacao Local")
    assert "published_local_only" in local_response["parameters"]["jsCode"]
    assert "reload_skipped" in local_response["parameters"]["jsCode"]

    reload_node = node_by_name(workflow, "Recarregar Modelo Publicado")
    reload_body = reload_node["parameters"]["jsonBody"]
    assert "artifact_bucket" in reload_body
    assert "artifact_prefix" in reload_body
    assert reload_node["parameters"]["headerParameters"]["parameters"][0]["name"] == "x-api-key"
    assert "api_gateway_api_key" in reload_node["parameters"]["headerParameters"]["parameters"][0]["value"]
    assert "$env" not in json.dumps(workflow)


def test_n8n_rejected_path_does_not_publish_or_reload():
    workflow = load_n8n_workflow()

    assert connection_targets(workflow, "Validar Threshold de Qualidade", 1) == ["Resposta - Modelo Rejeitado"]
    assert connection_targets(workflow, "Error Trigger - Capturar Falhas") == ["Registrar Incidente"]
    assert all(node["name"] != "Notificar Incidente - Discord" for node in workflow["nodes"])
    assert "Publicar Artefatos - Container" not in connection_targets(
        workflow,
        "Validar Threshold de Qualidade",
        1,
    )
    assert "Recarregar Modelo Publicado" not in connection_targets(
        workflow,
        "Validar Threshold de Qualidade",
        1,
    )
