import json
import runpy
import sys
from pathlib import Path

import pytest

from mlops.validation.quality_gate import ModelValidator


def write_metadata(run_dir: Path, metadata: dict) -> None:
    with (run_dir / "metadata.json").open("w", encoding="utf-8") as f:
        json.dump(metadata, f)


def make_run_dir(tmp_path: Path, name: str = "run", with_saved_model: bool = True) -> Path:
    run_dir = tmp_path / name
    run_dir.mkdir()
    if with_saved_model:
        (run_dir / "saved_model").mkdir()
    return run_dir


def test_model_approved_with_train_metadata_contract(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "train_contract_run")

    metadata = {
        "run_id": "nmt_test",
        "status": "approved",
        "threshold": 0.30,
        "metric_name": "val_token_accuracy",
        "metric_value": 0.45,
        "metrics_path": "artifacts/nmt_test/metrics.json",
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is True
    assert reason == "Aprovado"


def test_model_approved_with_legacy_metrics_object(tmp_path: Path):
    run_dir = tmp_path / "valid_run"
    run_dir.mkdir()

    (run_dir / "saved_model").mkdir()

    metadata = {
        "status": "approved",
        "threshold": 0.30,
        "metrics": {
            "val_token_accuracy": 0.45
        }
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is True
    assert reason == "Aprovado"


def test_model_rejected_below_threshold(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "rejected_run")

    metadata = {
        "status": "rejected",
        "threshold": 0.30,
        "metric_name": "val_token_accuracy",
        "metric_value": 0.15,
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "abaixo do threshold" in reason


def test_model_rejected_when_status_is_not_approved_even_above_threshold(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "bad_status_run")

    metadata = {
        "status": "rejected",
        "threshold": 0.30,
        "metric_name": "val_token_accuracy",
        "metric_value": 0.45,
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "Status no metadata" in reason


def test_model_rejected_missing_metric(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "missing_metric_run")

    metadata = {
        "status": "approved",
        "threshold": 0.30,
        "metric_name": "val_token_accuracy",
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "Metrica alvo" in reason


def test_model_rejected_invalid_metric_value(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "invalid_metric_run")

    metadata = {
        "status": "approved",
        "threshold": 0.30,
        "metric_name": "val_token_accuracy",
        "metric_value": "not-a-number",
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "invalido" in reason


def test_model_approved_with_legacy_top_level_metric(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "legacy_top_level_metric_run")

    metadata = {
        "status": "approved",
        "threshold": 0.30,
        "val_token_accuracy": 0.45,
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is True
    assert reason == "Aprovado"


def test_model_rejected_invalid_threshold(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "invalid_threshold_run")

    metadata = {
        "status": "approved",
        "threshold": "not-a-number",
        "metric_name": "val_token_accuracy",
        "metric_value": 0.45,
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "threshold invalido" in reason


def test_model_rejected_missing_saved_model(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "no_model_run", with_saved_model=False)

    metadata = {
        "status": "approved",
        "threshold": 0.30,
        "metric_name": "val_token_accuracy",
        "metric_value": 0.45,
    }

    write_metadata(run_dir, metadata)

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "Diretorio saved_model" in reason


def test_model_rejected_missing_metadata(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "no_metadata_run")

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "Arquivo metadata.json" in reason


def test_model_rejected_invalid_json(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "invalid_json_run")

    with (run_dir / "metadata.json").open("w", encoding="utf-8") as f:
        f.write("{invalid json}")

    validator = ModelValidator(run_dir)
    is_approved, reason = validator.validate()
    assert is_approved is False
    assert "invalido" in reason


@pytest.mark.filterwarnings("ignore:'mlops.validation.quality_gate' found in sys.modules:RuntimeWarning")
def test_quality_gate_cli_exits_zero_for_approved_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    run_dir = make_run_dir(tmp_path, "cli_approved_run")
    write_metadata(
        run_dir,
        {
            "status": "approved",
            "threshold": 0.30,
            "metric_name": "val_token_accuracy",
            "metric_value": 0.45,
        },
    )
    monkeypatch.setattr(sys, "argv", ["quality_gate", "--run_dir", str(run_dir)])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("mlops.validation.quality_gate", run_name="__main__")

    assert exc.value.code == 0
    assert "APPROVED: Aprovado" in capsys.readouterr().out


@pytest.mark.filterwarnings("ignore:'mlops.validation.quality_gate' found in sys.modules:RuntimeWarning")
def test_quality_gate_cli_exits_one_for_rejected_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    run_dir = make_run_dir(tmp_path, "cli_rejected_run", with_saved_model=False)
    monkeypatch.setattr(sys, "argv", ["quality_gate", "--run_dir", str(run_dir)])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("mlops.validation.quality_gate", run_name="__main__")

    assert exc.value.code == 1
    assert "REJECTED: Diretorio saved_model nao encontrado." in capsys.readouterr().out
