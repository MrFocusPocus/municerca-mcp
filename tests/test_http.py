"""HTTP transport: nothing but /health is reachable without the bearer token."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from municerca_mcp.http_app import build_app, serve

TOKEN = "t" * 40
INIT = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


def test_requests_without_token_are_rejected() -> None:
    client = TestClient(build_app(TOKEN))
    assert client.post("/mcp", json=INIT).status_code == 401
    assert client.get("/mcp").status_code == 401


def test_wrong_token_is_rejected() -> None:
    client = TestClient(build_app(TOKEN))
    response = client.post("/mcp", json=INIT, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert response.json() == {"error": "UNAUTHORIZED"}


def test_health_is_public_and_leaks_nothing() -> None:
    response = TestClient(build_app(TOKEN)).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_http_refuses_to_start_without_a_strong_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUNICERCA_AUTH_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="MUNICERCA_AUTH_TOKEN"):
        serve()
    with pytest.raises(ValueError, match="at least 32"):
        build_app("short")
