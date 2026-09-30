"""Phần dùng chung của các router Nhà máy thông minh (chỉ số theo ngày · sơ đồ vận hành): lấy nhà máy
đang bật + đọc SCADA qua khoá/cache của `scada_read_guard` với quy lỗi HTTP thống nhất.

Vì sao gom một chỗ: hai màn cùng đọc một SCADA — cùng khoá theo nhà máy (bận → 429), cùng luật che
lý do lỗi (502: admin thấy chi tiết, người khác câu ngắn — lý do có host/tài khoản/linked server của
hạ tầng OT, không đưa cho mọi người có quyền xem); chi tiết luôn ghi log.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from app.services import scada_client, scada_factory_repo as repo, user_repo
from app.services import scada_read_guard as guard

logger = logging.getLogger("vrg.scada")


def enabled_factory(factory_id: int) -> dict:
    """Nhà máy đang bật; không có / đang tắt → 404."""
    factory = repo.get_factory(factory_id)
    if not factory or not factory["enabled"]:
        raise HTTPException(404, "Không tìm thấy nhà máy (hoặc nhà máy đang tắt).")
    return factory


def _is_admin(username: str) -> bool:
    return (user_repo.get_user(username) or {}).get("role") == "admin"


def guarded_read(factory: dict, username: str, *args: Any, **kw: Any) -> Any:
    """`guard.read` + quy lỗi: bận → 429; SCADA lỗi → 502 (admin thấy chi tiết, người khác câu ngắn)."""
    try:
        return guard.read(factory, *args, **kw)
    except guard.ScadaBusyError as exc:
        raise HTTPException(429, str(exc)) from exc
    except scada_client.ScadaError as exc:
        # Thông điệp đã bỏ phần chi tiết nếu lặp mật khẩu (scada_errors.friendly_error).
        logger.warning("[scada] Đọc số liệu nhà máy «%s» lỗi: %s", factory["name"], exc)
        detail = str(exc) if _is_admin(username) else (
            f"Chưa đọc được số liệu SCADA của nhà máy «{factory['name']}» — đã ghi nhận, "
            "vui lòng báo quản trị viên.")
        raise HTTPException(502, detail) from exc
