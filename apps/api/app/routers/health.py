"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Kiểm tra trạng thái service (dùng cho readiness/liveness)."""
    return {"status": "healthy"}
