"""Đổi tên đơn vị thành viên: MỌI thứ gắn theo tên đơn vị phải chuyển sang tên mới.

Tên đơn vị là khoá liên kết của giá mủ, báo cáo ngày, hợp đồng tồn kho, kế hoạch năm,
nhu cầu thị trường và danh sách đơn vị của tài khoản. Trước đây đổi tên chỉ chuyển giá mủ
→ số liệu còn lại thành mồ côi và tài khoản đơn vị mất quyền vào chính đơn vị của mình.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import member_unit_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

OLD, NEW = "_zz_ren_cu", "_zz_ren_moi (Việt Nam)"
USER = "zz_ren_mem"


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup(h: dict[str, str]) -> None:
    client.delete(f"/api/users/{USER}", headers=h)
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_stock_contract", "unit_purchase_plan", "market_demand"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": [OLD, NEW]})
        db.execute(text("DELETE FROM fact_price WHERE source = 'vrg' AND grade = ANY(:u)"), {"u": [OLD, NEW]})
    for n in (OLD, NEW):
        client.delete(f"/api/member-units/{n}", headers=h)


def test_rename_moves_data_and_member_accounts() -> None:
    h = _admin()
    _cleanup(h)  # dọn nếu phiên trước sót
    client.post("/api/member-units", json={"name": OLD}, headers=h)
    assert client.post("/api/users", json={"username": USER, "password": "pass123",
                                           "role": "member", "member_units": [OLD]},
                       headers=h).status_code == 200

    # Mỗi bảng 1 dòng số liệu đang gắn tên CŨ.
    with session_scope() as db:
        db.execute(text("INSERT INTO unit_daily_report (as_of, company, kind, payload) "
                        "VALUES ('2026-07-20', :c, 'purchase', '{\"latex_wet\": 5}'::jsonb)"), {"c": OLD})
        db.execute(text("INSERT INTO unit_stock_contract (company, grade, qty, start_date) "
                        "VALUES (:c, 'SVR 10', 100, '2026-07-01')"), {"c": OLD})
        db.execute(text("INSERT INTO unit_purchase_plan (year, company, plan_tonnes) "
                        "VALUES (2026, :c, 5000)"), {"c": OLD})
        db.execute(text("INSERT INTO market_demand (as_of, company, content) "
                        "VALUES ('2026-07-20', :c, 'test')"), {"c": OLD})
        db.execute(text("INSERT INTO fact_price (as_of, source, grade, price_type, price, currency, unit) "
                        "VALUES ('2026-07-20', 'vrg', :c, 'purchase', 380, 'VND', 'đồng/độ TSC')"), {"c": OLD})

    member_unit_repo.rename_unit(OLD, NEW)

    names = [u["name"] for u in member_unit_repo.list_units()]
    assert NEW in names and OLD not in names

    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_stock_contract", "unit_purchase_plan", "market_demand"):
            assert db.execute(text(f"SELECT count(*) FROM {tbl} WHERE company = :c"), {"c": NEW}).scalar() == 1, tbl
            assert db.execute(text(f"SELECT count(*) FROM {tbl} WHERE company = :c"), {"c": OLD}).scalar() == 0, tbl
        assert db.execute(text("SELECT count(*) FROM fact_price WHERE source='vrg' AND grade = :c"),
                          {"c": NEW}).scalar() == 1

    # Tài khoản đơn vị: danh sách đơn vị đổi theo → đăng nhập vẫn vào đúng đơn vị của mình.
    token = client.post("/api/auth/login",
                        json={"username": USER, "password": "pass123"}).json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["member_units"] == [NEW]

    _cleanup(h)
