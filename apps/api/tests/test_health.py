"""Smoke test cho health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}


def test_root() -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["service"] == "vrg-caosu-api"
