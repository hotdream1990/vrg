"""Registry THAO TÁC của «Đề nghị sửa số liệu quá khứ» + khung chuẩn bị một đề nghị.

Mỗi thao tác (op) khai ĐÚNG MỘT chỗ (`edit_request_ops_daily` · `edit_request_ops_contract` ·
`edit_request_ops_demand`):
chuẩn hoá payload, ảnh chụp bản ghi, đơn vị + phạm vi quyền, khoá chống trùng, tiêu đề, ngày bị ảnh
hưởng, câu báo chặn và cách GHI THẬT khi Ban duyệt.

Hai nguyên tắc cứng:
- `blocked` GỌI CHÍNH các hàng rào hiện có rồi bắt 403 mang header `X-Edit-Blocked` — không viết lại
  luật, nên luật cửa sổ sửa/chốt số liệu đổi ở đâu thì luồng đề nghị tự đổi theo.
- `apply` bỏ qua HAI hàng rào thời gian nhưng KHÔNG BAO GIỜ bỏ quyền theo đơn vị (`check_scope` chạy
  lại lúc duyệt) và luật nghiệp vụ của repo.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.core.edit_window import BLOCK_HEADER

REASON_MIN, REASON_MAX = 5, 2000
Guard = Callable[[], None]


@dataclass(frozen=True)
class Op:
    label: Callable[[dict], str]                           # nhãn loại thao tác ("Biểu Thu mua"…)
    validate: Callable[[Any], dict]                        # payload thô → dict đã chuẩn hoá (400)
    snapshot: Callable[[dict], dict | None]                # bản ghi hiện tại (None = chưa có)
    company: Callable[[dict, dict | None], str]            # đơn vị của đề nghị (404 nếu mất bản ghi)
    check_scope: Callable[[dict, str, dict], None]         # tài khoản có quyền với đơn vị không (403)
    target_key: Callable[[dict], str]
    title: Callable[[dict, dict | None], str]
    dates: Callable[[dict, dict | None], list[str]]
    blocked: Callable[[str, dict, dict | None], list[str]]
    apply: Callable[[dict, str, str], dict]                # (payload, người gửi, đơn vị) → kết quả
    precheck: Callable[[dict, dict | None], None] | None = None   # luật nghiệp vụ SAU khi đã kiểm quyền
    # Nhãn hiển thị cho giá trị thô trong bảng so sánh: (payload, trước, hiện tại) → {ô: {giá trị: nhãn}}.
    labels: Callable[[list[dict | None]], dict[str, dict[str, str]]] | None = None
    # Số liệu có nằm trong CHỐT SỐ LIỆU không — False (nhu cầu thị trường) ⇒ duyệt không gỡ chốt.
    lockable: bool = True


def _registry() -> dict[str, Op]:
    # Import trong hàm: các module con import lại helper của module này.
    from app.services import edit_request_ops_contract as contract, edit_request_ops_daily as daily
    from app.services import edit_request_ops_demand as demand

    return {**daily.OPS, **contract.OPS, **demand.OPS}


def get_op(key: str) -> Op:
    op = _registry().get(key or "")
    if op is None:
        raise HTTPException(400, "Loại đề nghị sửa không hợp lệ.")
    return op


def op_label(key: str, payload: dict) -> str:
    op = _registry().get(key)
    try:
        return op.label(payload) if op else key
    except (KeyError, TypeError):
        return key


# ── Helper dùng chung cho các op ─────────────────────────────────────────────
def parse(model: type[BaseModel], payload: Any) -> BaseModel:
    """Payload → schema gốc; sai kiểu ⇒ 400 kèm ô bị sai (không để FastAPI trả 422 khó hiểu)."""
    try:
        return model.model_validate(payload if isinstance(payload, dict) else {})
    except ValidationError as exc:
        err = exc.errors()[0]
        where = ".".join(str(x) for x in err.get("loc", ())) or "payload"
        raise HTTPException(400, f"Nội dung đề nghị không hợp lệ ({where}: {err.get('msg')}).") from exc


def iso_date(value: str, label: str = "Ngày") -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def dmy(iso: str | None) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else ""


def uniq_dates(*values: Any) -> list[str]:
    return sorted({str(v)[:10] for v in values if v})


def collect_blocked(*guards: Guard) -> list[str]:
    """Chạy lần lượt các hàng rào; gom câu báo của 403 mang header chặn. Lỗi khác (400…) ném lại."""
    out: list[str] = []
    for guard in guards:
        try:
            guard()
        except HTTPException as exc:
            if exc.status_code != 403 or not (exc.headers or {}).get(BLOCK_HEADER):
                raise
            if exc.detail not in out:
                out.append(str(exc.detail))
    return out


def assert_assigned(user: dict, company: str) -> None:
    if company not in (user.get("member_units") or []):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def canon(value: Any) -> Any:
    """Chuẩn hoá để so ảnh chụp: 5 và 5.0 là một, khoá dict về chuỗi, tuple → list."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        return {str(k): canon(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canon(v) for v in value]
    return str(value)


def changed_since(current: Any, before: Any) -> bool:
    """Bản ghi đã đổi kể từ lúc gửi? Dùng CHUNG cho màn chi tiết lẫn lúc duyệt thật."""
    return canon(current) != canon(before)


def clean_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if len(text) < REASON_MIN:
        raise HTTPException(400, f"Nhập lý do chỉnh sửa (ít nhất {REASON_MIN} ký tự).")
    if len(text) > REASON_MAX:
        raise HTTPException(400, f"Lý do chỉnh sửa tối đa {REASON_MAX} ký tự.")
    return text


def prepare(op_key: str, payload: Any, user: dict) -> dict[str, Any]:
    """Dựng đề nghị từ payload thô: chuẩn hoá → ảnh chụp → quyền đơn vị → luật nghiệp vụ → câu chặn."""
    op = get_op(op_key)
    clean = op.validate(payload)
    before = op.snapshot(clean)
    company = op.company(clean, before)
    op.check_scope(user, company, clean)
    if op.precheck:
        op.precheck(clean, before)
    # `create_only` (nút Thêm) chỉ có nghĩa LÚC GỬI: lưu lại thì lúc duyệt precheck chặn cả khi Ban
    # đã xác nhận ghi đè bản ghi mới xuất hiện.
    clean = {k: v for k, v in clean.items() if k != "create_only"}
    return {"op": op_key, "company": company, "payload": clean, "before": before,
            "target_key": op.target_key(clean), "title": op.title(clean, before),
            "dates": op.dates(clean, before),
            "blocked": op.blocked(str(user.get("username") or ""), clean, before)}
