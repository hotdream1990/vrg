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


@router.post("/test-email")
def test_email(body: dict[str, str], username: str = Depends(require_admin)) -> dict:
    """Gửi thử một email tới địa chỉ chỉ định — để admin xác nhận khai SMTP đúng trước khi dùng thật.

    Gọi `mailer.send` ĐỒNG BỘ (không phải `send_async`) để trả về đúng lý do lỗi cho admin đọc.
    """
    from app.services import mailer

    to = mailer.normalize(body.get("to"))
    if not to:
        return {"ok": False, "detail": "Nhập địa chỉ email hợp lệ để gửi thử."}
    ok, err = mailer.send(
        [to], "[VRG] Thư kiểm tra cấu hình email",
        "Đây là thư kiểm tra từ Hệ thống Dự báo & Quản trị Giá Cao su (VRG).\n"
        "Nhận được thư này nghĩa là cấu hình SMTP đã hoạt động.",
    )
    return {"ok": ok, "detail": "Đã gửi — kiểm tra hộp thư." if ok else err}
