#!/usr/bin/env python3
"""Số liệu mẫu cho sổ tay "Lãnh đạo đơn vị thành viên" — dựng và xoá sạch sau khi chụp.

Tách khỏi `shoot.py` để mỗi file một việc: đây là DỮ LIỆU, bên kia là ẢNH.
Đơn vị mẫu phải KHÔNG có số liệu thật (mặc định "Bảo Lâm") — `clean()` xoá theo đơn vị.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

API = "http://localhost:8390"
UNIT_KEY = "Bảo Lâm"                      # dò theo từ khoá: tên đầy đủ khác nhau giữa các bản DB
MEMBER = "caosubaolam@gmail.com"          # tài khoản NHẬP LIỆU của đơn vị (seed số liệu)
LEADER = "lanhdao.baolam@vrg.vn"          # tài khoản LÃNH ĐẠO của đơn vị (chụp ảnh)
LEADER_NAME = "Nguyễn Văn A"

TODAY = date.today()
D = lambda n=0: (TODAY - timedelta(days=n)).isoformat()  # noqa: E731


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} → {e.code}: {e.read().decode()[:300]}") from e


def resolve_unit(admin: str) -> str:
    hit = [u["name"] for u in call("GET", "/api/member-units", admin) if UNIT_KEY in u["name"]]
    if len(hit) != 1:
        raise SystemExit(f"Không xác định được đơn vị mẫu {UNIT_KEY!r}: {hit or 'không có'}")
    return hit[0]


def ensure_leader(admin: str, unit: str) -> None:
    """Tài khoản lãnh đạo mẫu — tạo nếu chưa có, có rồi thì ép lại vai trò/đơn vị/email."""
    users = {u["username"] for u in call("GET", "/api/users", admin)}
    body = {"full_name": LEADER_NAME, "email": LEADER, "role": "leader", "member_units": [unit]}
    if LEADER in users:
        call("PUT", f"/api/users/{LEADER}", admin, body)
    else:
        call("POST", "/api/users", admin, {"username": LEADER, "password": "Vrg@2026@",
                                           "permissions": [], **body})


# ── Số liệu của đơn vị (ghi bằng tài khoản NHẬP LIỆU — lãnh đạo không ghi được) ───────────────
def seed_unit_data(tok: str, unit: str) -> None:
    for n, latex, cup, p_latex, p_cup in ((3, 118.4, 22.5, 372, 318), (2, 131.0, 18.9, 374, 320),
                                          (1, 128.5, 24.0, 376, 321), (0, 143.0, 19.5, 378, 323)):
        call("PUT", "/api/member/daily-report", tok, {
            "kind": "purchase", "company": unit, "as_of": D(n),
            "fields": {"latex_wet": latex, "coagulum": cup, "cup_basis": "drc"}})
        # Đơn giá thu mua nằm ở KHO GIÁ riêng (không phải trong phiếu) — không ghi thì cột đơn giá
        # trên màn Thu mua hiện dấu "—" và ảnh hướng dẫn trông như thiếu số.
        call("PUT", "/api/member/prices", tok, {
            "company": unit, "as_of": D(n), "price_type": "purchase", "price": p_latex,
            "basis": "tsc"})
        call("PUT", "/api/member/prices", tok, {
            "company": unit, "as_of": D(n), "price_type": "purchase_cup", "price": p_cup,
            "basis": "drc"})
    call("PUT", "/api/member/daily-report", tok, {
        "kind": "consumption", "company": unit, "as_of": D(0),
        "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 220}],
                   "stock_warehoused": [{"grade": "SVR 3L", "qty": 480},
                                        {"grade": "SVR 10 / CSR 10", "qty": 310}],
                   "stock_material": 95.0}})
    call("PUT", "/api/member/plan", tok, {
        "year": TODAY.year, "company": unit, "plan_tonnes": 12000,
        "plan_sales_spot_tonnes": 4500, "plan_revenue_ty": 640,
        "signed_lt_tonnes": 8200, "carry_lt_tonnes": 350, "carry_spot_tonnes": 120})
    call("PUT", "/api/member/market-demand", tok, {
        "company": unit, "as_of": D(0),
        "content": "Khách Trung Quốc hỏi mua SVR 10 giao tháng sau, khoảng 500 tấn. "
                   "Giá chào quanh 41,5 triệu đ/tấn, đang thương lượng."})

    cus = call("PUT", "/api/customers", tok, {
        "company": unit, "name": "Công ty TNHH Cao su Sài Gòn", "code": "KH-01",
        "note": "Khách hàng dài hạn"})["id"]
    call("PUT", "/api/customers", tok, {
        "company": unit, "name": "Shanghai Rubber Trading Co.", "code": "KH-02"})

    master = call("PUT", "/api/master-contracts", tok, {
        "company": unit, "code": "01/2026/HĐDH-BL", "master_type": "long_term",
        "customer_id": cus, "sign_date": D(200), "expiry_date": D(-160),
        "price_formula": "Giá SICOM TSR20 bình quân tuần trước liền kề + 30 USD/tấn, FOB HCM",
        "lines": [{"grade": "SVR 3L", "qty": 1200, "price": 1780, "ccy": "USD", "fx": 26300},
                  {"grade": "SVR 10 / CSR 10", "qty": 800, "price": 1650, "ccy": "USD",
                   "fx": 26300}]})["master"]

    # Ngày giao phải NẰM TRONG kỳ mặc định của màn Báo cáo tiêu thụ (đầu tháng → hôm nay),
    # nếu không ảnh chụp ra bảng toàn số 0.
    delivered = max(D(1), D(TODAY.day - 1))
    call("PUT", "/api/sales-contracts", tok, {
        "company": unit, "code": "HĐ-101/2026", "customer_id": cus, "delivery_type": "single",
        "contract_type": "spot", "sign_date": D(9), "delivered_at": delivered,
        "channel": "domestic", "invoice_no": "HĐ 0001234",
        "lines": [{"grade": "SVR 3L", "qty": 120, "price": 43.5, "ccy": "VND"}]})
    parent = call("PUT", "/api/sales-contracts", tok, {
        "company": unit, "code": "HĐ-102/2026", "customer_id": cus, "delivery_type": "multi",
        "contract_type": "long_term", "master_id": master["id"],
        "sign_date": D(20), "expiry_date": D(-160),
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 900, "price": 41.8, "ccy": "VND"}]})["contract"]
    call("PUT", "/api/sales-contracts", tok, {
        "company": unit, "parent_id": parent["id"], "code": "Đợt 01/HĐ-102",
        "delivered_at": delivered, "channel": "export", "invoice_no": "HĐ 0001255",
        "payment_date": D(0), "payment_qty": 300,
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 300, "price": 1620, "ccy": "USD",
                   "fx": 26150}]})
    call("PUT", "/api/sales-contracts", tok, {
        "company": unit, "parent_id": parent["id"], "code": "Đợt 02/HĐ-102", "channel": "export",
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 250, "price": 1635, "ccy": "USD",
                   "fx": 26200}]})


# ── Lỗi nhập liệu MẪU cho ảnh "Cảnh báo bất thường" ─────────────────────────────────────────────
def seed_anomalies(tok: str, unit: str) -> None:
    """Hai lỗi nhân viên hay mắc nhất: giá bán gõ ĐỒNG thay cho triệu đồng/tấn · có sản lượng thu
    mua mà quên đơn giá. `shoot.py` gọi hàm này SAU CÙNG, sau khi đã chụp xong các màn số liệu —
    ghi sớm thì Báo cáo tiêu thụ trong ảnh ra doanh thu gấp 1.000 lần. `clean()` xoá cả hai."""
    customers = call("GET", "/api/customers", tok)["items"]
    call("PUT", "/api/sales-contracts", tok, {
        "company": unit, "code": "HĐ-109/2026", "customer_id": customers[0]["id"],
        "delivery_type": "single", "contract_type": "spot", "sign_date": D(4),
        "delivered_at": D(3), "channel": "domestic", "invoice_no": "HĐ 0001301",
        "lines": [{"grade": "SVR 3L", "qty": 60, "price": 43500, "ccy": "VND"}]})
    call("PUT", "/api/member/daily-report", tok, {
        "kind": "purchase", "company": unit, "as_of": D(5),
        "fields": {"latex_wet": 96.2, "coagulum": 15.0, "cup_basis": "drc"}})


# ── Hộp thư: 4 thẻ đủ 3 loại + 1 thẻ đã khép ─────────────────────────────────────────────────
def seed_inbox(admin: str, leader_tok: str, unit: str) -> dict[str, int]:
    """Trả về {khoá: thread_id} để `shoot.py` mở đúng thẻ cần chụp."""
    call("POST", "/api/support/announcements", admin, {
        "subject": "Kế hoạch giá sàn tháng 9/2026",
        "body": "Kính gửi Quý đơn vị,\n\nTập đoàn thông báo khung giá sàn dự kiến áp dụng từ ngày "
                "10/9/2026. Đề nghị đơn vị rà soát lượng hàng tồn và kế hoạch giao hàng trong "
                "tháng, phản hồi về Ban Thị trường Kinh doanh trước 17h ngày 09/9/2026.\n\n"
                "Trân trọng.",
        "scope": "units", "units": [unit]})

    req = call("POST", "/api/support/requests", leader_tok, {
        "company": unit,
        "subject": "Đề nghị mở lại kỳ nhập liệu tháng 8",
        "body": "Kính gửi Tập đoàn,\n\nĐơn vị phát hiện số tồn kho ngày 28/8 nhập thiếu 12 tấn "
                "SVR 3L. Kỳ nhập liệu đã khoá nên đơn vị không sửa được. Đề nghị Tập đoàn mở lại "
                "giúp trong ngày để đơn vị cập nhật.\n\nTrân trọng."})["thread_id"]
    call("POST", f"/api/support/threads/{req}/reply", admin, {
        "body": "Tập đoàn đã mở lại kỳ nhập liệu tháng 8 cho đơn vị đến hết ngày mai. "
                "Đề nghị đơn vị cập nhật xong và báo lại để chốt số."})

    done = call("POST", "/api/support/requests", leader_tok, {
        "company": unit,
        "subject": "Xin cấp thêm 01 tài khoản nhập liệu",
        "body": "Đơn vị đề nghị cấp thêm một tài khoản nhập liệu cho cán bộ phòng Kế hoạch."})["thread_id"]
    call("POST", f"/api/support/threads/{done}/reply", admin, {
        "body": "Tập đoàn đã cấp tài khoản và gửi mật khẩu qua email của đơn vị."})
    call("PUT", f"/api/support/threads/{done}/status", admin, {"status": "closed"})

    rem = call("POST", "/api/support/reminders", admin, {
        "title": "Nhắc nộp Báo cáo tiêu thụ - tồn kho hằng ngày",
        "body": "Đề nghị đơn vị nhập số liệu thu mua và tồn kho trong ngày trước 16h00.",
        "scope": "units", "units": [unit], "repeat_rule": "daily",
        "next_at": (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0,
                                                                microsecond=0).isoformat(),
        "enabled": True})["id"]
    call("POST", f"/api/support/reminders/{rem}/run", admin)      # phát ngay để có thẻ "Nhắc lịch"

    rows = call("GET", "/api/support/threads", leader_tok)["rows"]
    by_subject = {r["subject"]: r["id"] for r in rows}
    return {
        "announce": by_subject["Kế hoạch giá sàn tháng 9/2026"],
        "request": req,
        "closed": done,
        "reminder": by_subject["Nhắc nộp Báo cáo tiêu thụ - tồn kho hằng ngày"],
        "reminder_id": rem,
    }


def clean(unit: str) -> None:
    """Xoá sạch số liệu + hộp thư mẫu của ĐÚNG đơn vị mẫu (chạy lại lần 2 không nhân đôi)."""
    import psycopg

    dsn = os.environ.get("DATABASE_URL", "postgresql://vrg:changeme@localhost:5433/vrg_caosu")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM sales_contract WHERE company = %s OR to_company = %s", (unit, unit))
        for t in ("master_contract", "unit_customer", "unit_daily_report", "unit_purchase_plan",
                  "market_demand"):
            cur.execute(f"DELETE FROM {t} WHERE company = %s", (unit,))
        cur.execute("DELETE FROM fact_price WHERE source = 'vrg_unit' AND grade = %s", (unit,))
        cur.execute("DELETE FROM support_message WHERE thread_id IN "
                    "(SELECT id FROM support_thread WHERE company = %s)", (unit,))
        cur.execute("DELETE FROM support_thread WHERE company = %s", (unit,))
        cur.execute("DELETE FROM support_reminder WHERE units::text LIKE %s", (f"%{unit}%",))
        conn.commit()
