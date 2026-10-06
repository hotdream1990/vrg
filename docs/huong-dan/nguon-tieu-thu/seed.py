#!/usr/bin/env python3
"""Dữ liệu mẫu cho bộ ảnh sổ tay "Nguồn tiêu thụ theo chủng loại" — tạo trước khi chụp, xoá sau.

Chạy từ `apps/api`, `DATABASE_URL` phải trỏ ĐÚNG DB mà API đang dùng (để lấy tài khoản admin ký
token); `VRG_API` là địa chỉ API (mặc định http://127.0.0.1:8390):

    cd apps/api && uv run python ../../docs/huong-dan/nguon-tieu-thu/seed.py          # tạo
    cd apps/api && uv run python ../../docs/huong-dan/nguon-tieu-thu/seed.py cleanup  # xoá

⛔ Chạy trên BẢN SAO PROD thì phải tắt job / SMTP / VAPID trước (memory clone-prod-db-to-local).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

API = os.environ.get("VRG_API", "http://127.0.0.1:8390")
UNIT = "Cao su Minh Hoạ (demo)"
USER, PASSWORD = "nhaplieu.minhhoa", "minhhoa123"


def _admin_token() -> str:
    from sqlalchemy import text

    from app.core.db import session_scope
    from app.core.security import create_access_token

    with session_scope() as db:
        admin = db.execute(text("SELECT username FROM app_user WHERE role = 'admin' AND is_active "
                                "ORDER BY username LIMIT 1")).scalar()
    return create_access_token(admin)


def _call(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def member_token() -> str:
    req = urllib.request.Request(f"{API}/api/auth/login", method="POST",
                                 data=json.dumps({"username": USER, "password": PASSWORD}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def _line(grade: str, qty: float, price: float, source: str | None = None, dry: float | None = None):
    d = {"grade": grade, "qty": qty, "price": price, "ccy": "VND"}
    if source:
        d["source"] = source
    if dry:
        d["qty_dry"] = dry
    return d


def seed() -> None:
    tok = _admin_token()
    _call("POST", "/api/member-units", tok, {"name": UNIT})
    ka = _call("PUT", "/api/customers", tok, {"company": UNIT, "name": "Khách hàng A"})["id"]
    kb = _call("PUT", "/api/customers", tok, {"company": UNIT, "name": "Khách hàng B"})["id"]
    _call("POST", "/api/users", tok, {"username": USER, "password": PASSWORD, "role": "member",
                                      "member_units": [UNIT]})
    base = {"company": UNIT, "contract_type": "spot", "sign_date": "2026-09-28", "source": None}

    def save(body: dict) -> dict:
        return _call("PUT", "/api/sales-contracts", tok, {**base, **body})["contract"]

    save({"code": "HD-MH-01", "customer_id": ka, "delivery_type": "single",
          "delivered_at": "2026-10-01", "channel": "domestic",
          "lines": [_line("SVR 10 / CSR 10", 30, 40, "exploit"), _line("SVR 3L", 10, 42, "purchase")]})
    save({"code": "HD-MH-02", "customer_id": kb, "delivery_type": "single",
          "delivered_at": "2026-10-02", "channel": "export",
          "lines": [_line("LATEX", 20, 30, "exploit", dry=12), _line("RSS 3", 8, 45, "goods")]})
    save({"code": "HD-MH-04", "customer_id": ka, "delivery_type": "single",
          "delivered_at": "2026-10-04", "channel": "domestic",
          "lines": [_line("SVR CV60", 20, 44, "exploit"), _line("SVR 3L", 6, 42, "purchase")]})
    # Hợp đồng giao 1 lần CHƯA giao — dùng cho ảnh màn Hoàn thành hợp đồng.
    save({"code": "HD-MH-05", "customer_id": kb, "delivery_type": "single",
          "lines": [_line("SVR 10 / CSR 10", 15, 40), _line("RSS 3", 5, 45)]})
    par = save({"code": "HD-MH-03", "customer_id": kb, "delivery_type": "multi",
                "lines": [_line("SVR 10 / CSR 10", 60, 40), _line("SVR 20 / CSR 20", 20, 38),
                          _line("SVR 3L", 20, 42)]})
    for code, day, channel, lines in (
            ("1", "2026-10-03", "domestic", [_line("SVR 10 / CSR 10", 25, 40, "purchase"),
                                             _line("SVR 20 / CSR 20", 15, 38, "exploit")]),
            ("2", "2026-10-05", "export", [_line("SVR 3L", 12, 42, "goods"),
                                           _line("SVR 10 / CSR 10", 18, 40, "exploit")])):
        _call("PUT", "/api/sales-contracts", tok,
              {"company": UNIT, "parent_id": par["id"], "code": code, "delivered_at": day,
               "channel": channel, "source": None, "lines": lines})
    print(f"Đã tạo dữ liệu mẫu cho «{UNIT}», tài khoản {USER}.")


def cleanup() -> None:
    from sqlalchemy import text

    from app.core.db import session_scope

    with session_scope() as db:
        for sql in ("DELETE FROM sales_contract WHERE company = :u",
                    "DELETE FROM unit_customer WHERE company = :u",
                    "DELETE FROM audit_log WHERE company = :u OR actor = :n",
                    "DELETE FROM access_log WHERE username = :n",
                    "DELETE FROM app_user WHERE username = :n",
                    "DELETE FROM member_unit WHERE name = :u"):
            db.execute(text(sql), {"u": UNIT, "n": USER})
    print(f"Đã xoá dữ liệu mẫu của «{UNIT}».")


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    cleanup() if sys.argv[1:] == ["cleanup"] else seed()
