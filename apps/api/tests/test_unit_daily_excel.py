"""Test nhập liệu bằng Excel cho báo cáo đơn vị — tải mẫu · xem trước · ghi.

Hai điểm quan trọng nhất được khoá lại ở đây:
1. Tài khoản chỉ quản 1 đơn vị → mẫu KHÔNG có cột 'Đơn vị', khi nhập server tự gán đúng đơn vị đó.
2. Không thể lách quyền: client sửa payload (xoá cờ lỗi) để ghi cho đơn vị khác vẫn bị server chặn.
"""

from __future__ import annotations

import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_zz_xl_unit"
OTHER = "_zz_xl_other"
MEMBER = "xl_mem"


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


# Tiêu đề cột đúng như file mẫu (bộ đọc dò cột THEO TIÊU ĐỀ nên bắt buộc phải có dòng này).
_PURCHASE_HEAD = ["Đơn vị", "Ngày", "SL thu mua mủ nước", "SL thu mua mủ chén",
                  "Đơn giá mủ nước", "Đơn giá mủ chén", "SL tiêu thụ mủ thu mua", "Doanh thu"]


def _rows_to_xlsx(sheet: str, head: list[str], rows: list[tuple], header_row: int = 5) -> bytes:
    """Dựng file .xlsx giống mẫu: tiêu đề ở `header_row`, dữ liệu từ header_row+2."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    for c, t in enumerate(head, start=1):
        ws.cell(row=header_row, column=c, value=t)
    for i, r in enumerate(rows, start=header_row + 2):
        for c, v in enumerate(r, start=1):
            ws.cell(row=i, column=c, value=v)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_import_single_unit_and_permission() -> None:
    h = _admin()
    today = date.today().isoformat()
    client.delete(f"/api/users/{MEMBER}", headers=h)
    for u in (UNIT, OTHER):
        client.post("/api/member-units", json={"name": u}, headers=h)
    client.post("/api/users", json={"username": MEMBER, "password": "pass123", "role": "member",
                                    "member_units": [UNIT]}, headers=h)
    mh = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": MEMBER, "password": "pass123"}
    ).json()["access_token"]}

    # 1) Mẫu của tài khoản 1 đơn vị: KHÔNG còn cột 'Đơn vị', ghi rõ áp dụng cho đơn vị nào.
    tpl = client.get("/api/member/import/template?kind=purchase", headers=mh)
    assert tpl.status_code == 200
    ws = load_workbook(io.BytesIO(tpl.content))["Thu mua"]
    titles = [ws.cell(row=5, column=c).value for c in range(1, 10)]
    assert "Đơn vị" not in titles and "Ngày" in titles
    assert UNIT in str(ws.cell(row=2, column=1).value)

    # 2) Nhập file không có cột 'Đơn vị' → server tự gán đơn vị của tài khoản.
    data = _rows_to_xlsx("Thu mua", _PURCHASE_HEAD[1:],   # mẫu 1 đơn vị: bỏ cột "Đơn vị"
                          [(today, 12.5, 4.5, 500, 450, 9, 0.4)])
    prev = client.post("/api/member/import/preview?kind=purchase", headers=mh,
                       files={"file": ("f.xlsx", data)}).json()
    assert prev["summary"] == {"total": 1, "ok": 1, "error": 0}
    assert prev["rows"][0]["company"] == UNIT
    assert client.post("/api/member/import/commit", headers=mh,
                       json={"kind": "purchase", "rows": prev["rows"]}).json()["saved"] == 1

    # 3) Không lách được quyền: dùng mẫu có cột 'Đơn vị' điền đơn vị KHÁC.
    admin_tpl = client.get("/api/unit-daily/import/template?kind=purchase", headers=h)
    ws2 = load_workbook(io.BytesIO(admin_tpl.content))["Thu mua"]
    assert ws2.cell(row=5, column=1).value == "Đơn vị"      # mẫu chuyên viên vẫn có cột này
    bad = _rows_to_xlsx("Thu mua", _PURCHASE_HEAD,
                         [(OTHER, today, 99, 99, 900, 900, 99, 9.9)])
    prev2 = client.post("/api/member/import/preview?kind=purchase", headers=mh,
                        files={"file": ("f.xlsx", bad)}).json()
    assert prev2["rows"][0]["_errors"], "phải báo lỗi đơn vị ngoài quyền"

    # Kẻ xấu xoá cờ lỗi ở client rồi ép ghi → server vẫn phải chặn.
    hacked = [dict(r, _errors=[]) for r in prev2["rows"]]
    res = client.post("/api/member/import/commit", headers=mh,
                      json={"kind": "purchase", "rows": hacked}).json()
    assert res["saved"] == 0 and res["skipped"] == 1

    # Dọn SẠCH dữ liệu test (kể cả bản ghi đã ghi vào bảng số liệu) — không để rác lại DB.
    client.delete(f"/api/users/{MEMBER}", headers=h)
    for u in (UNIT, OTHER):
        client.delete(f"/api/member-units/{u}", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company IN (:a, :b)"),
                   {"a": UNIT, "b": OTHER})
        db.execute(text("DELETE FROM fact_price WHERE source = 'vrg' AND grade IN (:a, :b)"),
                   {"a": UNIT, "b": OTHER})


def test_template_download_then_import_roundtrip() -> None:
    """Tải mẫu → điền vào ĐÚNG file mẫu → xem trước → ghi → đọc lại: số phải khớp.

    Khoá lại 2 lỗi từng gặp: (1) thêm cột vào mẫu nhưng bộ ghi bỏ qua (cup_basis từng bị gán
    SAU lệnh upsert nên không lưu); (2) mẫu và bộ đọc lệch cột.
    """
    from datetime import timedelta
    h = _admin()
    unit = "_zz_xl_rt"
    client.post("/api/member-units", json={"name": unit}, headers=h)
    d = date.today() - timedelta(days=2)
    dmy, iso = d.strftime("%d/%m/%Y"), d.isoformat()

    cases = {
        "purchase": [(unit, dmy, 120.0, 50.0, 540, 510, "Độ DRC", 90, 4.3)],
        "sales": [(unit, dmy, "Dài hạn", "XK / UTXK", "SVR CV 50", 25, 1800, "USD", dmy)],
        "stock": [(unit, dmy, "Chế biến chưa nhập kho", "SVR CV 50", 33, None, None, None, None),
                  (unit, dmy, "Đã nhập kho", "SVR 3L", 66, None, None, None, None),
                  (unit, dmy, "Đã ký HĐ", "RSS 3", 12, 1750, "USD", dmy, 21)],
    }
    for kind, rows in cases.items():
        tpl = client.get(f"/api/unit-daily/import/template?kind={kind}", headers=h)
        assert tpl.status_code == 200
        wb = load_workbook(io.BytesIO(tpl.content))
        ws = wb.active
        for i, r in enumerate(rows, start=7):
            for j, v in enumerate(r, start=1):
                if v is not None:
                    ws.cell(row=i, column=j, value=v)
        buf = io.BytesIO()
        wb.save(buf)
        prev = client.post(f"/api/unit-daily/import/preview?kind={kind}", headers=h,
                           files={"file": ("f.xlsx", buf.getvalue())}).json()
        assert prev["summary"]["error"] == 0, (kind, prev["rows"])
        assert client.post("/api/unit-daily/import/commit", headers=h,
                           json={"kind": kind, "rows": prev["rows"]}).json()["saved"] >= 1

    pur = client.get(f"/api/unit-daily/day?kind=purchase&as_of={iso}",
                     headers=h).json()["entries"][unit]["fields"]
    assert pur["cup_basis"] == "drc" and pur["latex_wet"] == 120.0

    con = client.get(f"/api/unit-daily/day?kind=consumption&as_of={iso}",
                     headers=h).json()["entries"][unit]["fields"]
    assert con["sales_ccy"] == "USD" and con["sales"][0]["invoice_date"] == iso
    assert con["stock_ccy"] == "USD"
    assert con["stock_not_warehoused"][0]["qty"] == 33
    assert con["stock_warehoused"][0]["qty"] == 66
    assert con["stock_signed_undelivered"][0]["qty"] == 12
    assert con["stock_material"] == 21

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :u"), {"u": unit})
        db.execute(text("DELETE FROM fact_price WHERE source='vrg' AND grade = :u"), {"u": unit})
    client.delete(f"/api/member-units/{unit}", headers=h)
