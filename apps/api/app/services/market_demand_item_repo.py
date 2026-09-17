"""Repository phiếu Nhu cầu thị trường (`market_demand_item`) — đọc/ghi/xoá + nhật ký hoạt động.

Repo KHÔNG kiểm quyền hay cửa sổ nhập liệu: việc đó của router / luồng đề nghị sửa (xem
`market_demand_item_policy`). Dữ liệu vào đây phải là phiếu đã qua `policy.clean`.
Nhật ký ghi ở đây (choke point) để mọi lối vào — màn đơn vị, màn chuyên viên, duyệt đề nghị — đều
để lại vết.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_demand_meta import DATA_FIELDS
from app.services import audit_repo

_ENTITY = "market_demand"
_COLS = ", ".join(DATA_FIELDS)
_SELECT = (f"SELECT id, {_COLS}, source_key, created_at, created_by, updated_at, updated_by "
           "FROM market_demand_item")
_DATE_COLS = ("as_of",)
_NUM_COLS = ("qty", "price")

# Ngày đi dạng chuỗi ISO → ép kiểu date ngay trong SQL (cùng cách các repo khác), khỏi lệ thuộc driver.
_VALUES = {f: (f"CAST(:{f} AS date)" if f in _DATE_COLS else f":{f}") for f in DATA_FIELDS}
_INSERT = text(
    f"INSERT INTO market_demand_item ({_COLS}, source_key, created_by, updated_by) "
    f"VALUES ({', '.join(_VALUES.values())}, :source_key, :by, :by) RETURNING id")
_UPDATE = text(
    f"UPDATE market_demand_item SET {', '.join(f'{f} = {v}' for f, v in _VALUES.items())}, "
    "updated_by = :by, updated_at = now() WHERE id = :id")


def _out(r: Any) -> dict[str, Any]:
    """Dòng DB → DemandItem (ngày ISO, số float, `legacy` = dòng chuyển từ bản chữ cũ)."""
    item: dict[str, Any] = {"id": int(r["id"])}
    for f in DATA_FIELDS:
        v = r[f]
        if f in _DATE_COLS:
            v = v.isoformat() if v else None
        elif f in _NUM_COLS:
            v = float(v) if v is not None else None
        item[f] = v
    item["legacy"] = r["source_key"] is not None
    for f in ("created_at", "updated_at"):
        item[f] = r[f].isoformat() if r[f] else None
    item["created_by"], item["updated_by"] = r["created_by"], r["updated_by"]
    return item


def _audit_view(item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Chỉ các ô dữ liệu — không kèm mốc thời gian, để lần lưu không đổi gì thì nhật ký tự bỏ qua."""
    return {f: item[f] for f in DATA_FIELDS} if item else None


def get(item_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(f"{_SELECT} WHERE id = :id"), {"id": item_id}).mappings().first()
    return _out(r) if r else None


def list_items(companies: list[str] | None, date_from: str, date_to: str, *,
               company: str | None = None, grade: str | None = None,
               q: str | None = None) -> list[dict[str, Any]]:
    """Phiếu trong khoảng ngày nhận, mới nhất trước. `companies=None` = mọi đơn vị (chuyên viên)."""
    ensure_schema()
    where = ["as_of BETWEEN CAST(:df AS date) AND CAST(:dt AS date)"]
    params: dict[str, Any] = {"df": date_from, "dt": date_to}
    if companies is not None:
        where.append("company = ANY(:units)")
        params["units"] = list(companies)
    for col, val in (("company", company), ("grade", grade)):
        if val:
            where.append(f"{col} = :{col}")
            params[col] = val
    if q and q.strip():
        # Ký tự đại diện của LIKE trong từ khoá được coi là chữ thường, không phải "khớp mọi thứ".
        needle = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(customer ILIKE :q OR result ILIKE :q OR note ILIKE :q)")
        params["q"] = f"%{needle}%"
    sql = f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY as_of DESC, id DESC"
    with session_scope() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [_out(r) for r in rows]


def save(item: dict[str, Any], username: str | None, *,
         source_key: str | None = None) -> dict[str, Any] | None:
    """Thêm (id rỗng) hoặc sửa 1 phiếu. None = id không còn tồn tại.

    `source_key` chỉ dùng khi THÊM phiếu chuyển từ bản chữ cũ — ghi cùng lệnh INSERT để không bao
    giờ có phiếu chuyển đổi nằm lại không mang khoá (chạy lại sẽ chèn trùng).
    """
    ensure_schema()
    params = {**{f: item.get(f) for f in DATA_FIELDS}, "by": username, "source_key": source_key}
    before = get(int(item["id"])) if item.get("id") else None
    if item.get("id") and before is None:
        return None
    with session_scope() as db:
        if before:
            db.execute(_UPDATE, {**params, "id": before["id"]})
            item_id = before["id"]
        else:
            item_id = int(db.execute(_INSERT, params).scalar_one())
    after = get(item_id)
    audit_repo.log(_ENTITY, "update" if before else "create", str(item_id),
                   before=_audit_view(before), after=_audit_view(after),
                   as_of=(after or {}).get("as_of"), company=(after or {}).get("company"))
    return after


def delete(item_id: int, companies: list[str] | None) -> bool:
    """Xoá 1 phiếu; `companies` giới hạn phạm vi (None = mọi đơn vị). False = không có trong phạm vi."""
    ensure_schema()
    before = get(item_id)
    if not before or (companies is not None and before["company"] not in companies):
        return False
    with session_scope() as db:
        db.execute(text("DELETE FROM market_demand_item WHERE id = :id"), {"id": item_id})
    audit_repo.log(_ENTITY, "delete", str(item_id), before=_audit_view(before),
                   as_of=before["as_of"], company=before["company"])
    return True
