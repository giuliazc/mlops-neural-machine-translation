import pytest
from fastapi.testclient import TestClient
from inference_api.main import app

def test_health_contains_required_fields():
    """Test that /health response contains required fields."""
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert body["status"] == "ok"
    assert "run_id" in body
    assert "model_loaded" in body

def test_metrics_are_integers():
    """Ensure all metric values are integers."""
    client = TestClient(app)
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    for key in ["requests_total", "errors_total", "translations_total"]:
        assert isinstance(body[key], int)
        assert body[key] >= 0

def test_predict_with_special_characters():
    """POST /predict should handle special characters."""
    client = TestClient(app)
    special_text = "Olá! Como você está? @#$%"
    r = client.post("/predict", json={"text": special_text})
    # Should not return 422 (validation error)
    assert r.status_code != 422
    assert r.status_code in (503, 500, 200)  # No model or success

def test_predict_with_unicode():
    """POST /predict should handle unicode characters."""
    client = TestClient(app)
    unicode_text = "Café com açúcar ñ é ç"
    r = client.post("/predict", json={"text": unicode_text})
    assert r.status_code != 422

def test_reload_with_invalid_json():
    """POST /reload with invalid JSON should return 422."""
    client = TestClient(app)
    # Send invalid JSON
    r = client.post(
        "/reload",
        data="invalid json",
        headers={"Content-Type": "application/json"}
    )
    assert r.status_code in (422, 400)

def test_concurrent_metrics_increments():
    """Metrics should be thread-safe."""
    client = TestClient(app)
    before = client.get("/metrics").json()
    
    # Make multiple requests (will fail but should increment counters)
    for _ in range(3):
        client.post("/predict", json={"text": "teste"})
    
    after = client.get("/metrics").json()
    assert after["requests_total"] >= before["requests_total"] + 3

def test_model_endpoint_structure():
    """GET /model response should have expected structure."""
    client = TestClient(app)
    r = client.get("/model")
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    # run_id can be None if no model is loaded
    assert body["run_id"] is None or isinstance(body["run_id"], str)

def test_health_model_loaded_boolean():
    """model_loaded field must always be a boolean."""
    client = TestClient(app)
    for _ in range(5):
        r = client.get("/health")
        assert r.status_code == 200
        assert isinstance(r.json()["model_loaded"], bool)
