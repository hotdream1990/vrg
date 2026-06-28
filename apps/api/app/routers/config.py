"""Router cấu hình hệ thống (app_config) — chỉ admin (gắn require_admin ở main)."""
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.services import config_repo

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def get_config() -> dict:
    """Danh sách cấu hình đã mask (secret không lộ giá trị thật)."""
    return {"config": config_repo.list_config()}


@router.put("")
def put_config(body: dict[str, str], username: str = Depends(require_admin)) -> dict:
    """Cập nhật cấu hình (ô để trống = giữ nguyên giá trị cũ)."""
    n = config_repo.set_config(body, by=username)
    return {"updated": n, "config": config_repo.list_config()}
