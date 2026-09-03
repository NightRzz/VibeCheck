"""Tests for FastAPI ML & drift observability endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_ml_stats_endpoint():
    response = client.get("/v1/ml/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_inferences" in data
    assert "cache_hit_rate" in data
    assert "latency_p95_ms" in data


def test_ml_drift_report_endpoint():
    response = client.get("/v1/ml/drift-report")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert len(response.text) > 50000  # Evidently dashboard is extensive


def test_ml_drift_metrics_endpoint():
    response = client.get("/v1/ml/drift-metrics")
    assert response.status_code == 200
    assert response.headers.get("content-type") == "application/json; charset=utf-8"


def test_ml_stats_from_worker_telemetry_file():
    from processor.worker import TELEMETRY_PATH, write_telemetry
    mock_metrics = {
        "total_inferences": 9999,
        "cache_capacity": 10000,
        "cache_size": 4200,
        "cache_hits": 8000,
        "cache_misses": 1999,
        "cache_hit_rate": 0.8001,
        "latency_p50_ms": 0.0012,
        "latency_p90_ms": 0.0020,
        "latency_p95_ms": 0.0028,
        "latency_p99_ms": 0.0040,
        "latency_mean_ms": 0.0015,
    }
    write_telemetry(mock_metrics)
    try:
        response = client.get("/v1/ml/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_inferences"] == 9999
        assert data["cache_hit_rate"] == 0.8001
        assert data["latency_p95_ms"] == 0.0028
    finally:
        if TELEMETRY_PATH.exists():
            TELEMETRY_PATH.unlink()


def test_ml_drift_endpoints_with_refresh():
    response_html = client.get("/v1/ml/drift-report?refresh=false")
    assert response_html.status_code == 200
    assert "text/html" in response_html.headers.get("content-type", "")

    response_json = client.get("/v1/ml/drift-metrics?refresh=false")
    assert response_json.status_code == 200
