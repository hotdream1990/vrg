"""Health check endpoints."""

from fastapi import APIRouter

from app.core.db import db_healthy

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Kiểm tra trạng thái service (dùng cho readiness/liveness)."""
    return {"status": "healthy"}


@router.get("/health/db")
def health_db() -> dict[str, object]:
    """Kiểm tra kết nối DB (TimescaleDB)."""
    ok = db_healthy()
    return {"success": ok, "db": "ok" if ok else "unreachable"}
