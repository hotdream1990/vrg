"""Registry THAO TÁC của «Đề nghị sửa số liệu quá khứ» + khung chuẩn bị một đề nghị.

Mỗi thao tác (op) khai ĐÚNG MỘT chỗ (`edit_request_ops_daily` · `edit_request_ops_contract` ·
`edit_request_ops_demand` · `edit_request_ops_plan`):
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
from app.core.entry_types import (
    CONTRACT, DAILY_KIND_ENTRY_TYPE, PURCHASE, assert_entry_type, has_entry_type, plan_field_type,
)
from app.services.unit_daily_fields import CONSUMPTION_SALES_KEYS

REASON_MIN, REASON_MAX = 5, 2000
Guard = Callable[[], None]
#: Loại nhập liệu mà thao tác đòi (chốt 01/10/2026) — đề nghị sửa đi đúng phần việc của màn gốc.
#: Biểu ngày theo `kind` của payload; op mới thêm mà quên khai ở đây thì `prepare` ném KeyError
#: (đóng chặt, không lọt) và test `test_member_entry_types` báo ngay.
_OP_TYPE = {"contract_save": CONTRACT, "contract_delete": CONTRACT, "contract_delivery_type": CONTRACT,
            "demand_save": CONTRACT, "demand_delete": CONTRACT}


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
    # Ô thuộc NHIỀU loại nhập liệu (Kế hoạch năm): bỏ ô ngoài loại của tài khoản thay cho kiểm 1 loại.
    restrict: Callable[[dict, dict], dict] | None = None
    # Mốc trên của đợt chốt bị gỡ khi duyệt (None = mọi đợt từ ngày sửa sớm nhất trở đi).
    unlock_until: Callable[[dict], str] | None = None


def _registry() -> dict[str, Op]:
    # Import trong hàm: các module con import lại helper của module này.
    from app.services import edit_request_ops_contract as contract, edit_request_ops_daily as daily
    from app.services import edit_request_ops_demand as demand, edit_request_ops_plan as plan

    return {**daily.OPS, **contract.OPS, **demand.OPS, **plan.OPS}


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


def entry_type_of(op_key: str, clean: dict) -> str:
    """Loại nhập liệu của một đề nghị (payload đã chuẩn hoá)."""
    if op_key in ("daily_report", "daily_move"):
        return DAILY_KIND_ENTRY_TYPE[clean["kind"]]
    if op_key == "year_plan":   # chỉ có ô kế hoạch THU MUA → Thu mua; còn lại Hợp đồng & tiêu thụ
        fields = [k for k in clean if k not in ("year", "company", "kind")]
        return PURCHASE if fields and all(plan_field_type(k) == PURCHASE for k in fields) else CONTRACT
    return _OP_TYPE[op_key]


def sales_locked(user: dict, kind: str) -> bool:
    """Biểu Tồn kho (`consumption`) còn giữ ô TIÊU THỤ CŨ (`CONSUMPTION_SALES_KEYS`) — tài khoản
    đơn vị KHÔNG có loại Hợp đồng & tiêu thụ thì không được đổi các ô đó."""
    return kind == "consumption" and not has_entry_type(user, CONTRACT)


def keep_stored_sales(fields: dict, stored: dict | None) -> dict:
    """Thay ô tiêu thụ cũ trong `fields` bằng đúng giá trị ĐANG LƯU (`stored`); chưa lưu thì bỏ.

    KHÔNG 403: form Tồn kho gửi lại nguyên mảng/ô tiêu thụ cũ đã lưu, chặn cứng là CV Tồn kho không
    lưu nổi phần của mình (cùng ý với `_plan_allowed` của Kế hoạch năm).
    """
    out = {k: v for k, v in (fields or {}).items() if k not in CONSUMPTION_SALES_KEYS}
    return {**out, **{k: v for k, v in (stored or {}).items() if k in CONSUMPTION_SALES_KEYS}}


def member_daily_fields(user: dict, kind: str, as_of: str, company: str, fields: dict) -> dict:
    """`fields` của biểu ngày mà tài khoản này được phép ghi (ghi thẳng `PUT /api/member/daily-report`)."""
    if not sales_locked(user, kind):
        return fields
    from app.services.edit_request_ops_daily import _day_fields   # import vòng: module con dùng helper ở đây

    return keep_stored_sales(fields, _day_fields(kind, as_of, company))


def prepare(op_key: str, payload: Any, user: dict) -> dict[str, Any]:
    """Dựng đề nghị từ payload thô: chuẩn hoá → loại nhập liệu → ảnh chụp → quyền đơn vị → luật
    nghiệp vụ → câu chặn. Loại nhập liệu chỉ kiểm LÚC GỬI — Ban duyệt không bị ảnh hưởng."""
    op = get_op(op_key)
    clean = op.validate(payload)
    if op.restrict:
        clean = op.restrict(user, clean)
    else:
        assert_entry_type(user, entry_type_of(op_key, clean))
    before = op.snapshot(clean)
    if op_key == "daily_report" and sales_locked(user, clean["kind"]):
        # Nội dung lưu chờ duyệt cũng mang ô tiêu thụ ĐANG LƯU, không phải số tài khoản gửi lên.
        clean = {**clean, "fields": keep_stored_sales(clean["fields"], (before or {}).get("fields"))}
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
