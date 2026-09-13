"""Tổng hợp TRẠNG THÁI TRUNG THỰC cho một lượt quét giá (hàm thuần — không DB, không mạng).

Trước đây lượt quét luôn ghi `ok` miễn là ghi DB được, nên nguồn lỗi/thiếu cặp tỷ giá nằm im trong
ghi chú JSON suốt 11 ngày. Nay: `error` (ghi DB hỏng) · `warning` (có nguồn không OK, ghi chú lỗi của
nguồn, hoặc tỷ giá quá cũ) · `ok` (sạch). Tóm tắt tiếng Việt lưu vào `meta_crawl_run.error`.
"""

from __future__ import annotations

import re
from typing import Any

from app.services import fx_freshness

#: Độ dài tối đa của tóm tắt ghi vào meta_crawl_run.error.
MAX_NOTE_CHARS = 400

#: Tên hiển thị thân thiện của mã nguồn crawler (khớp ScanNowButton ở web).
SOURCE_NAMES = {"fx": "Tỷ giá", "sgx": "SGX", "shfe": "SHFE", "tocom": "OSE", "lgm": "MRB"}

_STATUS_LABEL = {"empty": "không có dữ liệu", "blocked": "bị chặn", "error": "lỗi"}

#: Ghi chú THÔNG TIN của nguồn quét OK — không phải lỗi: sàn không giao dịch (No Trading), báo cáo
#: hôm nay chưa đăng nên lấy phiên trước (bình thường buổi sáng). Mọi ghi chú khác = cảnh báo, để
#: kiểu hỏng MỚI chưa ai lường trước vẫn lộ ra thay vì bị nuốt.
_INFO_NOTE = re.compile(r"No Trading|lấy phiên", re.IGNORECASE)


def source_name(code: str) -> str:
    return SOURCE_NAMES.get(code, code.upper())


def _error_fragments(note: str | None) -> list[str]:
    """Tách ghi chú gộp ('a; b') → giữ các mảnh KHÔNG thuộc loại thông tin."""
    parts = [p.strip() for p in (note or "").split(";")]
    return [p for p in parts if p and not _INFO_NOTE.search(p)]


def source_warning(src: dict[str, Any]) -> str | None:
    """1 dòng cảnh báo cho 1 nguồn, hoặc None nếu nguồn sạch."""
    status = str(src.get("status") or "")
    name = source_name(str(src.get("source") or "?"))
    if status == "ok":
        bad = _error_fragments(src.get("note"))
        return f"{name}: {'; '.join(bad)}" if bad else None
    label = _STATUS_LABEL.get(status, status or "không rõ trạng thái")
    note = (src.get("note") or "").strip()
    return f"{name}: {label}" + (f" — {note}" if note else "")


def run_warnings(sources: list[dict[str, Any]], stale: list[dict[str, Any]]) -> list[str]:
    out = [w for w in (source_warning(s) for s in sources) if w]
    if stale:
        out.append("Tỷ giá quá cũ: " + fx_freshness.describe(stale))
    return out


def run_status(db_note: str, warnings: list[str]) -> str:
    """`error` khi không ghi được DB (lỗi hoặc DB không sẵn sàng) · `warning` · `ok`."""
    if db_note != "ok":
        return "error"
    return "warning" if warnings else "ok"


def run_note(warnings: list[str]) -> str | None:
    """Tóm tắt ghi vào meta_crawl_run.error — cắt ≤ MAX_NOTE_CHARS ký tự."""
    if not warnings:
        return None
    note = " · ".join(warnings)
    return note if len(note) <= MAX_NOTE_CHARS else note[: MAX_NOTE_CHARS - 1] + "…"
