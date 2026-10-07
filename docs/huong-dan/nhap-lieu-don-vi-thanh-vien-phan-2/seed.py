#!/usr/bin/env python3
"""Dữ liệu mẫu cho bộ ảnh sổ tay "Nhập liệu đơn vị thành viên — Phần 2" — tạo trước khi chụp, xoá sau.

Chạy từ `apps/api`, `DATABASE_URL` phải trỏ ĐÚNG DB mà API đang dùng (để lấy tài khoản admin ký
token); `VRG_API` là địa chỉ API (mặc định http://127.0.0.1:8390):

    cd apps/api && uv run python ../../docs/huong-dan/nhap-lieu-don-vi-thanh-vien-phan-2/seed.py          # tạo
    cd apps/api && uv run python ../../docs/huong-dan/nhap-lieu-don-vi-thanh-vien-phan-2/seed.py cleanup  # xoá

⛔ Chạy trên BẢN SAO PROD thì phải tắt job / SMTP / VAPID trước (memory clone-prod-db-to-local).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, timedelta

API = os.environ.get("VRG_API", "http://127.0.0.1:8390")
UNIT = "Cao su Minh Hoạ (demo)"
USER, PASSWORD = "nhaplieu.minhhoa", "minhhoa123"
#: Người tạo đợt chốt mẫu — `cleanup` xoá đúng các đợt mang dấu này (đợt chốt áp cho MỌI đơn vị).
ROUND_BY = "huong-dan-demo"


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


def _upload(token: str, name: str) -> dict:
    """Tải một file PDF mẫu lên kho chứng từ hợp đồng → {file, filename}."""
    b = "----vrgdemo"
    raw = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
           "Content-Type: application/pdf\r\n\r\n").encode() + b"%PDF-1.4 demo\r\n" + f"--{b}--\r\n".encode()
    req = urllib.request.Request(f"{API}/api/sales-contracts/file", method="POST", data=raw,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
    return {"file": d["file"], "filename": d["filename"]}


def member_token() -> str:
    req = urllib.request.Request(f"{API}/api/auth/login", method="POST",
                                 data=json.dumps({"username": USER, "password": PASSWORD}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]


def seed() -> None:
    tok = _admin_token()
    day = lambda n: (date.today() + timedelta(days=n)).isoformat()  # noqa: E731
    _call("POST", "/api/member-units", tok, {"name": UNIT})
    ka = _call("PUT", "/api/customers", tok, {"company": UNIT, "name": "Khách hàng A"})["id"]
    kb = _call("PUT", "/api/customers", tok, {"company": UNIT, "name": "Khách hàng B"})["id"]
    _call("POST", "/api/users", tok, {"username": USER, "password": PASSWORD, "role": "member",
                                      "member_units": [UNIT]})
    base = {"company": UNIT, "contract_type": "spot", "delivery_type": "single"}

    def save(body: dict) -> dict:
        return _call("PUT", "/api/sales-contracts", tok, {**base, **body})["contract"]

    # Hợp đồng đã bán chờ giao, ĐỦ chứng từ: scan HĐ + 2 đợt cọc + chỉ thị giao hàng.
    save({"code": "HD-MH-21", "customer_id": ka, "sign_date": day(-12),
          "lines": [{"grade": "SVR 10 / CSR 10", "qty": 100, "price": 45, "ccy": "VND"}],
          "files": [_upload(tok, "HD-MH-21 ban scan.pdf")],
          "deposits": [
              {"amount": 500, "ccy": "VND", "date": day(-10), "docs": [_upload(tok, "UNC coc dot 1.pdf")]},
              {"amount": 400, "ccy": "VND", "date": day(-3), "docs": [_upload(tok, "UNC coc dot 2.pdf")]}],
          "instruction_date": day(12), "instruction_place": "Cảng Cát Lái, TP. Hồ Chí Minh",
          "instruction_docs": [_upload(tok, "Chi thi giao hang HD-MH-21.pdf")]})
    # Hợp đồng còn THIẾU chứng từ cọc + chỉ thị — dùng cho ảnh cột Chứng từ.
    save({"code": "HD-MH-22", "customer_id": kb, "sign_date": day(-4),
          "lines": [{"grade": "SVR 3L", "qty": 60, "price": 47, "ccy": "VND"}],
          "files": [_upload(tok, "HD-MH-22 ban scan.pdf")]})
    # Kế hoạch năm của đơn vị mẫu + một ĐỢT CHỐT SỐ LIỆU (đến hết hôm qua) chưa xác nhận.
    from app.services import data_lock_repo, unit_daily_repo

    unit_daily_repo.save_year_plan(date.today().year, UNIT, {
        "plan_exploit_tonnes": 3400, "plan_tonnes": 350, "plan_goods_tonnes": 1150,
        "plan_sales_spot_tonnes": 2000, "signed_lt_tonnes": 1500, "carry_lt_tonnes": 0,
        "carry_spot_tonnes": 0, "plan_revenue_ty": 241.36}, "admin")
    data_lock_repo.save_round(day(-1), "Đề nghị đơn vị rà số liệu và kế hoạch năm trước khi chốt.",
                              ROUND_BY)
    print(f"Đã tạo dữ liệu mẫu cho «{UNIT}», tài khoản {USER}.")


def cleanup() -> None:
    from sqlalchemy import text

    from app.core.db import session_scope

    with session_scope() as db:
        for sql in ("DELETE FROM unit_data_lock WHERE company = :u OR round_id IN "
                    "(SELECT id FROM data_lock_round WHERE created_by = :r)",
                    "DELETE FROM data_lock_round WHERE created_by = :r",
                    "DELETE FROM unit_purchase_plan WHERE company = :u",
                    "DELETE FROM sales_contract WHERE company = :u",
                    "DELETE FROM unit_customer WHERE company = :u",
                    "DELETE FROM audit_log WHERE company = :u OR actor = :n",
                    "DELETE FROM access_log WHERE username = :n",
                    "DELETE FROM app_user WHERE username = :n",
                    "DELETE FROM member_unit WHERE name = :u"):
            db.execute(text(sql), {"u": UNIT, "n": USER, "r": ROUND_BY})
    print(f"Đã xoá dữ liệu mẫu của «{UNIT}».")


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    cleanup() if sys.argv[1:] == ["cleanup"] else seed()
