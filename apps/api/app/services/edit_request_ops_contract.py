"""Thao tác «Đề nghị sửa» cho HỢP ĐỒNG / ĐỢT GIAO: thêm-sửa (`contract_save`) · xoá (`contract_delete`).

Hàng rào = `sales_contract_lock.assert_delivery_fences` (đúng hàm router `/api/sales-contracts` dùng);
sửa an toàn (`is_safe_edit` — không dịch con số nào) thì không bị chặn nên không cần đề nghị.
Phạm vi đơn vị giống router hợp đồng (`cap_or_member_scope`): đơn vị được gán + đơn vị đã SÁP NHẬP
vào đó (hợp đồng dở dang của đơn vị cũ). Khi duyệt, repo vẫn kiểm hợp đồng thuộc đúng đơn vị.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.core.market_meta import CONTRACT_TYPES, DELIVERY_TYPES, SALE_CHANNELS
from app.schemas.edit_request import ContractDeleteRequest
from app.schemas.sales_contract import ContractIn
from app.services import (
    customer_repo, master_contract_repo, member_unit_merge, sales_contract_lock, sales_contract_repo,
)
from app.services.edit_request_ops import Op, collect_blocked, parse, uniq_dates

_NOT_FOUND = "Không tìm thấy hợp đồng trong phạm vi tài khoản."


def _scope(user: dict, company: str, _p: dict) -> None:
    units = list(user.get("member_units") or [])
    if company not in (member_unit_merge.expand(units) or units):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _kind(row: dict | None) -> str:
    return "đợt giao" if (row or {}).get("parent_id") else "hợp đồng"


def _assert_open(contract: dict | None, what: str) -> None:
    """Hợp đồng đã HOÀN THÀNH ⇒ 400 đúng câu của repo — báo ngay lúc gửi, không đợi Ban duyệt mới lỗi."""
    try:
        if contract:
            sales_contract_repo.assert_open(contract, what)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _parent(parent_id: int | None) -> dict | None:
    return sales_contract_repo.get(parent_id) if parent_id else None


def _labels(rows: list[dict | None]) -> dict[str, dict[str, str]]:
    """Giá trị thô → chữ người đọc được cho bảng so sánh (khách hàng, số HĐ cha/mẹ, loại…)."""
    def ids(field: str) -> list[int]:
        return sorted({int(r[field]) for r in rows if r and r.get(field)})

    customers, parents = ids("customer_id"), {i: (_parent(i) or {}).get("code") for i in ids("parent_id")}
    out = {"customer_id": customer_repo.names_by_id(None, ids=customers) if customers else {},
           "parent_id": {i: c for i, c in parents.items() if c},
           "master_id": master_contract_repo.codes_by_id(None, ids=ids("master_id")),
           "delivery_type": DELIVERY_TYPES, "contract_type": CONTRACT_TYPES, "channel": SALE_CHANNELS}
    return {field: {str(k): str(v) for k, v in m.items()} for field, m in out.items() if m}


# ── Thêm / sửa ───────────────────────────────────────────────────────────────
def _save_validate(payload: Any) -> dict:
    row = parse(ContractIn, payload).model_dump()
    row["code"] = str(row.get("code") or "").strip()
    return row


def _save_snapshot(p: dict) -> dict | None:
    return sales_contract_repo.get(p["id"]) if p.get("id") else None


def _save_company(p: dict, before: dict | None) -> str:
    if p.get("id") and before is None:
        raise HTTPException(404, _NOT_FOUND)
    if before and before["company"] != p["company"]:
        raise HTTPException(403, "Hợp đồng thuộc đơn vị khác.")
    return p["company"]


def _save_precheck(p: dict, _before: dict | None) -> None:
    """ĐÚNG bộ luật lưu thật (`sales_contract_repo.validate`, chỉ không ghi): khách hàng, loại, ngày,
    dòng chi tiết, trùng số hợp đồng/đợt giao, hợp đồng cha, hạn mức sản lượng, hợp đồng đã hoàn
    thành… Sai thì báo ngay lúc gửi; lúc duyệt chạy lại để bắt thay đổi xảy ra sau khi gửi."""
    try:
        sales_contract_repo.validate(p, p["company"])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _delete_precheck(_p: dict, before: dict | None) -> None:
    _assert_open(before, "xoá")
    _assert_open(_parent((before or {}).get("parent_id")), "xoá đợt giao")


def _save_blocked(username: str, p: dict, before: dict | None) -> list[str]:
    if sales_contract_lock.is_safe_edit(before, p):
        return []
    return collect_blocked(lambda: sales_contract_lock.assert_delivery_fences(
        username, p.get("id"), p.get("delivered_at"), p["company"], old=before))


def _save_apply(p: dict, requester: str, company: str) -> dict:
    try:
        return {"contract": sales_contract_repo.save(p, company, requester)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _save_key(p: dict) -> str:
    return f"contract:{p['id']}" if p.get("id") else f"contract:new:{p.get('parent_id') or 0}:{p['code'].lower()}"


# ── Xoá ──────────────────────────────────────────────────────────────────────
def _delete_company(_p: dict, before: dict | None) -> str:
    if before is None:
        raise HTTPException(404, _NOT_FOUND)
    return before["company"]


def _delete_apply(p: dict, _requester: str, company: str) -> dict:
    try:
        ok = sales_contract_repo.delete(p["id"], [company])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not ok:
        raise HTTPException(404, _NOT_FOUND)
    return {"ok": True}


OPS: dict[str, Op] = {
    "contract_save": Op(
        label=lambda _p: "Hợp đồng",
        validate=_save_validate, snapshot=_save_snapshot, company=_save_company,
        check_scope=_scope, precheck=_save_precheck, target_key=_save_key, labels=_labels,
        title=lambda p, _b: f"{_kind(p).capitalize()} {p['code']}",
        dates=lambda p, b: uniq_dates((b or {}).get("delivered_at"), p.get("delivered_at")),
        blocked=_save_blocked, apply=_save_apply),
    "contract_delete": Op(
        label=lambda _p: "Xoá hợp đồng",
        validate=lambda payload: {"id": parse(ContractDeleteRequest, payload).id},
        snapshot=lambda p: sales_contract_repo.get(p["id"]),
        company=_delete_company, check_scope=_scope, precheck=_delete_precheck, labels=_labels,
        target_key=lambda p: f"contract:{p['id']}",
        title=lambda p, b: f"Xoá {_kind(b)} {(b or {}).get('code') or '#' + str(p['id'])}",
        dates=lambda _p, b: uniq_dates((b or {}).get("delivered_at")),
        blocked=lambda u, p, b: collect_blocked(
            lambda: sales_contract_lock.assert_delivery_fences(u, p["id"], None, old=b)),
        apply=_delete_apply),
}
