"""Router cấu hình hệ thống (app_config) — chỉ admin (gắn require_admin ở main)."""
from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.services import config_repo

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def get_config() -> dict:
    """Cấu hình đã mask (secret không lộ) + danh sách nhóm (mỗi nhóm = 1 tab)."""
    return {"groups": config_repo.CONFIG_GROUPS, "config": config_repo.list_config()}


@router.get("/llm-models")
def get_llm_models() -> dict:
    """Danh sách model cho dropdown (OpenAI lấy thật từ tài khoản nếu đã đặt key)."""
    return {"openai": config_repo.list_openai_models()}


@router.put("")
def put_config(body: dict[str, str], username: str = Depends(require_admin)) -> dict:
    """Cập nhật cấu hình (ô để trống = giữ nguyên giá trị cũ)."""
    n = config_repo.set_config(body, by=username)
    return {"updated": n, "groups": config_repo.CONFIG_GROUPS, "config": config_repo.list_config()}


@router.post("/marketscreener/test")
def test_marketscreener() -> dict:
    """Chạy thử đăng nhập marketscreener bằng tài khoản đang lưu → {ok, stage, message}."""
    from app.services import scan_service

    return scan_service.test_marketscreener()
