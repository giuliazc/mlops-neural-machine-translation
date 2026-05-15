import pytest
from pathlib import Path
from inference_api.model_manager import ModelManager

def test_model_manager_initial_state():
    manager = ModelManager("tests_temp_dir")
    assert manager.is_loaded() is False
    assert manager.current_run_id() is None

def test_load_non_existent_model(tmp_path: Path):
    manager = ModelManager(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        manager.load("fake-run-id")
    assert manager.is_loaded() is False

def test_translate_without_model_raises_error():
    manager = ModelManager("fake_dir", default_run_id="")
    with pytest.raises(ValueError, match="Nenhum run_id disponível"):
        manager.translate("hello world")

def test_load_requires_run_id_or_default(tmp_path: Path):
    manager = ModelManager(str(tmp_path), default_run_id="")
    with pytest.raises(ValueError, match="Nenhum run_id disponível"):
        manager.load()
