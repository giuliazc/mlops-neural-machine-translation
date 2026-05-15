import os
import json
import pytest
from pathlib import Path
from ml.common import (
    utc_now_iso,
    ensure_dir,
    write_json,
    read_json,
    generate_run_id,
    get_env,
    sha256_file
)

def test_utc_now_iso():
    iso_date = utc_now_iso()
    assert isinstance(iso_date, str)
    assert "T" in iso_date
    assert "+00:00" in iso_date

def test_ensure_dir(tmp_path: Path):
    target = tmp_path / "new_folder"
    assert not target.exists()
    ensured = ensure_dir(target)
    assert ensured.exists()
    assert ensured.is_dir()

def test_write_and_read_json(tmp_path: Path):
    file_path = tmp_path / "data.json"
    data = {"key": "value", "number": 42}
    write_json(file_path, data)
    
    assert file_path.exists()
    loaded_data = read_json(file_path)
    assert loaded_data == data

def test_generate_run_id():
    run_id = generate_run_id("test")
    assert run_id.startswith("test_")
    assert len(run_id) > 10

def test_get_env(monkeypatch):
    monkeypatch.setenv("DUMMY_VAR", "123")
    assert get_env("DUMMY_VAR") == "123"
    assert get_env("NON_EXISTENT", "default") == "default"
    
    monkeypatch.setenv("EMPTY_VAR", "")
    assert get_env("EMPTY_VAR", "default") == "default"

def test_sha256_file(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")
    
    expected_sha = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9" # sha256 of "hello world"
    assert sha256_file(file_path) == expected_sha
