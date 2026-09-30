"""Cấu hình kết nối SCADA của từng nhà máy (bảng `scada_factory`) — CRUD + kiểm hợp lệ + nhật ký.

Mật khẩu SQL Server lưu cùng mức với secret của `app_config`; API KHÔNG BAO GIỜ trả mật khẩu
(chỉ `password_set`), nhật ký chỉ ghi `password_changed: true/false`.
Kiểm hợp lệ form (tag / linked server đi thẳng vào chuỗi OPENQUERY) ở `scada_factory_validation`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core import request_ctx
from app.core.db import ensure_schema, session_scope
from app.services import audit_repo
from app.services.scada_daily_meters import VN_TZ
from app.services.scada_factory_validation import clean

ENTITY = "scada_factory"
_COLS = ("id, name, host, port, username, password, database_name, linked_server, energy_tags, "
         "water_tag, bales_tag, enabled, layout_key, updated_at, updated_by")
#: Trường đưa vào nhật ký (bỏ mật khẩu + dấu vết lưu — hai thứ này đổi mỗi lần lưu).
_AUDIT_FIELDS = ("name", "host", "port", "username", "database_name", "linked_server",
                 "energy_tags", "water_tag", "bales_tag", "enabled", "layout_key")


class DuplicateNameError(ValueError):
    """Trùng tên nhà máy → router trả 409."""


def _row(m: Any) -> dict[str, Any]:
    d = dict(m)
    d["energy_tags"] = list(d.get("energy_tags") or [])
    return d


def list_factories(enabled_only: bool = False) -> list[dict[str, Any]]:
    """Mọi nhà máy (KÈM mật khẩu — chỉ dùng nội bộ, ra API phải qua `public_view`)."""
    ensure_schema()
    where = "WHERE enabled" if enabled_only else ""
    with session_scope() as db:
        rows = db.execute(text(f"SELECT {_COLS} FROM scada_factory {where} ORDER BY name"))
        return [_row(m) for m in rows.mappings().all()]


def get_factory(factory_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        m = db.execute(text(f"SELECT {_COLS} FROM scada_factory WHERE id = :i"),
                       {"i": factory_id}).mappings().first()
        return _row(m) if m else None


def public_view(f: dict[str, Any]) -> dict[str, Any]:
    """Dạng trả ra API quản trị — KHÔNG có mật khẩu."""
    at = f.get("updated_at")
    if at is not None and at.tzinfo is not None:
        at = at.astimezone(VN_TZ).replace(tzinfo=None)
    return {
        "id": f["id"], "name": f["name"], "host": f["host"], "port": f["port"],
        "username": f["username"], "password_set": bool(f.get("password")),
        "database": f["database_name"], "linked_server": f["linked_server"],
        "energy_tags": list(f["energy_tags"]), "water_tag": f["water_tag"],
        "bales_tag": f["bales_tag"], "enabled": f["enabled"], "layout_key": f.get("layout_key"),
        "updated_at": at.isoformat(timespec="seconds") if at else None,
        "updated_by": f.get("updated_by"),
    }


def _endpoint(f: dict[str, Any]) -> tuple[str, int, str]:
    return str(f["host"]).strip().lower(), int(f["port"]), str(f["username"]).strip().lower()


def _snap(f: dict[str, Any]) -> dict[str, Any]:
    return {k: f.get(k) for k in _AUDIT_FIELDS}


def _save(sql: str, params: dict[str, Any]) -> int | None:
    try:
        with session_scope() as db:
            return db.execute(text(sql), params).scalar()
    except IntegrityError as exc:
        raise DuplicateNameError(f"Đã có nhà máy tên «{params['name']}».") from exc


def create_factory(data: dict[str, Any]) -> dict[str, Any]:
    ensure_schema()
    row = clean(data, creating=True)
    new_id = _save(
        "INSERT INTO scada_factory (name, host, port, username, password, database_name, "
        "linked_server, energy_tags, water_tag, bales_tag, enabled, layout_key, updated_by) VALUES "
        "(:name, :host, :port, :username, :password, :database_name, :linked_server, "
        "CAST(:energy_tags AS text[]), :water_tag, :bales_tag, :enabled, :layout_key, :by) "
        "RETURNING id", {"layout_key": None, **row, "by": request_ctx.actor()})
    created = get_factory(int(new_id))
    audit_repo.log(ENTITY, "create", row["name"], after={**_snap(created), "password_changed": True})
    return created


def update_factory(factory_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    """Sửa nhà máy; None nếu không tồn tại. Bỏ trống mật khẩu = giữ mật khẩu cũ (chỉ khi GIỮ nguyên
    máy chủ · cổng · tài khoản)."""
    before = get_factory(factory_id)
    if not before:
        return None
    row = clean(data, creating=False)
    # Chặn "đổi host sang máy lạ + giữ mật khẩu cũ" → bấm Kiểm tra là mật khẩu SCADA bay tới máy lạ.
    if "password" not in row and _endpoint(row) != _endpoint(before):
        raise ValueError("Đổi máy chủ, cổng hoặc tài khoản thì phải nhập lại mật khẩu.")
    changed = "password" in row and row["password"] != before["password"]
    sets = ("name = :name, host = :host, port = :port, username = :username, "
            "database_name = :database_name, linked_server = :linked_server, "
            "energy_tags = CAST(:energy_tags AS text[]), water_tag = :water_tag, "
            "bales_tag = :bales_tag, enabled = :enabled, updated_at = now(), updated_by = :by")
    for col in ("password", "layout_key"):  # vắng mặt = giữ nguyên (xem `clean`)
        if col in row:
            sets += f", {col} = :{col}"
    _save(f"UPDATE scada_factory SET {sets} WHERE id = :id RETURNING id",
          {**row, "id": factory_id, "by": request_ctx.actor()})
    after = get_factory(factory_id)
    audit_repo.log(ENTITY, "update", after["name"],
                   before={**_snap(before), "password_changed": False},
                   after={**_snap(after), "password_changed": changed})
    return after


def delete_factory(factory_id: int) -> bool:
    before = get_factory(factory_id)
    if not before:
        return False
    with session_scope() as db:
        db.execute(text("DELETE FROM scada_factory WHERE id = :i"), {"i": factory_id})
    audit_repo.log(ENTITY, "delete", before["name"], before=_snap(before))
    return True
