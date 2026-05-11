"""
Smoke tests for the FastAPI app.

These do NOT require a live Postgres or LLM. They verify:
- the app imports without error
- non-DB endpoints respond
- the OpenAPI schema includes the routes we expect (governance, multi-persona)

Endpoints that touch Postgres are exercised under pytest -m integration.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from main import app
    return TestClient(app)


def test_app_imports_and_starts(client: TestClient):
    rsp = client.get("/health")
    assert rsp.status_code == 200
    assert rsp.json() == {"status": "healthy", "service": "pfa-decision-ai"}


def test_openapi_schema_exposes_governance_routes(client: TestClient):
    rsp = client.get("/openapi.json")
    assert rsp.status_code == 200
    paths = rsp.json()["paths"]
    assert "/api/v1/governance/audit" in paths
    assert "/api/v1/governance/review" in paths


def test_openapi_schema_exposes_persona_param_on_kpi_summary(client: TestClient):
    rsp = client.get("/openapi.json")
    spec = rsp.json()
    summary_op = spec["paths"]["/api/v1/kpi/summary"]["get"]
    param_names = {p["name"] for p in summary_op.get("parameters", [])}
    assert "persona" in param_names


def test_openapi_schema_exposes_date_range_params_on_kpi_endpoints(client: TestClient):
    """Day 1 contract: /kpi/summary and /kpi/daily accept start/end ISO dates."""
    rsp = client.get("/openapi.json")
    spec = rsp.json()
    for path in ("/api/v1/kpi/summary", "/api/v1/kpi/daily"):
        params = {p["name"] for p in spec["paths"][path]["get"].get("parameters", [])}
        assert "start" in params, f"{path} missing start"
        assert "end" in params, f"{path} missing end"


def test_kpi_summary_rejects_inverted_date_range(client: TestClient):
    """Defense in depth: inverted ranges 400 before we hit Postgres."""
    rsp = client.get("/api/v1/kpi/summary?start=2018-09-01&end=2017-01-01")
    assert rsp.status_code == 400
    assert "must be <=" in rsp.json()["detail"]


def test_kpi_daily_rejects_inverted_date_range(client: TestClient):
    rsp = client.get("/api/v1/kpi/daily?start=2018-09-01&end=2017-01-01")
    assert rsp.status_code == 400


def test_openapi_schema_exposes_persona_param_on_narrative(client: TestClient):
    rsp = client.get("/openapi.json")
    spec = rsp.json()
    narrative_op = spec["paths"]["/api/v1/insights/narrative"]["get"]
    param_names = {p["name"] for p in narrative_op.get("parameters", [])}
    assert "persona" in param_names


def test_ask_returns_clean_error_without_llm_key(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    rsp = client.post("/api/v1/ask", json={"question": "how many orders?"})
    assert rsp.status_code == 200
    body = rsp.json()
    assert body["error"]
    assert "No LLM provider" in body["error"]
