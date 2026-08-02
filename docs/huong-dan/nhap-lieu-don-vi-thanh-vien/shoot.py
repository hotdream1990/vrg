#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH của hướng dẫn "Nhập liệu — Đơn vị thành viên" (chạy khi giao diện đổi).

Cách làm: admin ĐĂNG NHẬP HỘ một tài khoản đơn vị (tính năng có sẵn của hệ thống, không cần mật
khẩu của đơn vị) → seed vài số liệu mẫu → Playwright chụp ảnh có chú thích → XOÁ sạch số liệu mẫu.

Đơn vị dùng làm mẫu phải KHÔNG có số liệu thật (mặc định "Bảo Lâm") — script xoá theo đơn vị
sau khi chụp, dùng nhầm đơn vị có số thật là mất dữ liệu.

Chạy:  ./scripts/dev.sh (API 8390 + Web 5390) rồi
       uv run --directory apps/api --with playwright python \
           ../../docs/huong-dan/nhap-lieu-don-vi-thanh-vien/shoot.py
"""
from __future__ import annotations

import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

SKILL = pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts"
sys.path.insert(0, str(SKILL))
from shoot import annotated_shot, browser_page  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

API = "http://localhost:8390"
WEB = "http://localhost:5390"
UNIT = "Bảo Lâm"
MEMBER = "caosubaolam@gmail.com"
OUT = pathlib.Path(__file__).parent / "img"

TODAY = date.today()
D = lambda n=0: (TODAY - timedelta(days=n)).isoformat()  # noqa: E731


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    import json

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


def seed(tok: str) -> None:
    """Số liệu mẫu vừa đủ để mọi màn có nội dung thật (không màn nào trống)."""
    call("PUT", "/api/member/daily-report", tok, {
        "kind": "purchase", "company": UNIT, "as_of": D(1),
        "fields": {"latex_wet": 128.5, "coagulum": 24.0, "cup_basis": "drc",
                   "finished": [{"grade": "SVR 3L", "qty": 40, "price": 43.2, "ccy": "VND"}]}})
    call("PUT", "/api/member/daily-report", tok, {
        "kind": "purchase", "company": UNIT, "as_of": D(0),
        "fields": {"latex_wet": 143.0, "coagulum": 19.5, "cup_basis": "drc"}})
    call("PUT", "/api/member/daily-report", tok, {
        "kind": "consumption", "company": UNIT, "as_of": D(0),
        "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 220}],
                   "stock_warehoused": [{"grade": "SVR 3L", "qty": 480},
                                        {"grade": "SVR 10 / CSR 10", "qty": 310}],
                   "stock_material": 95.0}})
    call("PUT", "/api/member/plan", tok, {
        "year": TODAY.year, "company": UNIT, "plan_tonnes": 12000,
        "signed_lt_tonnes": 8200, "carry_lt_tonnes": 350, "carry_spot_tonnes": 120})
    call("PUT", "/api/member/market-demand", tok, {
        "company": UNIT, "as_of": D(0),
        "content": "Khách Trung Quốc hỏi mua SVR 10 giao tháng sau, số lượng khoảng 500 tấn. "
                   "Giá chào quanh 41,5 triệu đ/tấn, đang thương lượng."})

    cus = call("PUT", "/api/customers", tok, {
        "company": UNIT, "name": "Công ty TNHH Cao su Sài Gòn", "code": "KH-01",
        "note": "Khách hàng dài hạn"})["id"]
    call("PUT", "/api/customers", tok, {
        "company": UNIT, "name": "Shanghai Rubber Trading Co.", "code": "KH-02"})

    # HĐ giao 1 lần, ĐÃ giao → lên Báo cáo tiêu thụ. Ngày giao phải NẰM TRONG kỳ mặc định của màn
    # báo cáo (đầu tháng → hôm nay), nếu không ảnh chụp ra toàn số 0.
    delivered_1 = max(D(1), D(TODAY.day - 1))
    call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "code": "HĐ-101/2026", "customer_id": cus, "delivery_type": "single",
        "contract_type": "spot", "sign_date": D(9), "start_date": D(9),
        "delivered_at": delivered_1, "channel": "domestic",
        "lines": [{"grade": "SVR 3L", "qty": 120, "price": 43.5, "ccy": "VND"}]})
    # HĐ giao nhiều lần: 1 phụ lục đã giao + 1 phụ lục đang chờ giao (nằm ở "đã ký HĐ chưa giao").
    parent = call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "code": "HĐ-102/2026", "customer_id": cus, "delivery_type": "multi",
        "contract_type": "long_term", "sign_date": D(20), "expiry_date": D(-160),
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 900, "price": 41.8, "ccy": "VND"}]})["contract"]
    call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "parent_id": parent["id"], "code": "PL-01/HĐ-102",
        "start_date": D(12), "delivered_at": D(0), "channel": "export",
        "payment_date": D(0), "payment_qty": 300, "payment_cost": 145,
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 300, "price": 1620, "ccy": "USD",
                   "fx": 26150, "cost": 145}]})
    call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "parent_id": parent["id"], "code": "PL-02/HĐ-102",
        "start_date": D(2), "channel": "export",
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 250, "price": 1635, "ccy": "USD",
                   "fx": 26200}]})


def seed_legacy() -> None:
    """1 hợp đồng ở bảng CŨ (`unit_stock_contract`) — màn "Hợp đồng cũ" chỉ đọc bảng này, không
    seed thì ảnh chụp ra bảng trống. Ghi thẳng DB vì giao diện đã chuyển sang chỉ-xem."""
    import os

    import psycopg

    dsn = os.environ.get("DATABASE_URL", "postgresql://vrg:changeme@localhost:5433/vrg_caosu")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO unit_stock_contract (company, code, grade, qty, price, ccy, start_date, "
            " delivered_date, updated_by) VALUES "
            " (%s,'HĐ-088/2026','SVR 3L',180,43.1,'VND',%s::date,%s::date,'seed'),"
            " (%s,'HĐ-092/2026','SVR 10 / CSR 10',240,41.6,'VND',%s::date,NULL,'seed')",
            (UNIT, D(45), D(28), UNIT, D(20)))
        conn.commit()


def clean() -> None:
    """Xoá SẠCH số liệu mẫu (chỉ của đơn vị mẫu) — không để lại rác trong DB dev."""
    import os

    import psycopg

    dsn = os.environ.get("DATABASE_URL", "postgresql://vrg:changeme@localhost:5433/vrg_caosu")
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM sales_contract WHERE company = %s OR to_company = %s", (UNIT, UNIT))
        for t in ("unit_customer", "unit_daily_report", "unit_purchase_plan", "market_demand",
                  "unit_stock_contract"):
            cur.execute(f"DELETE FROM {t} WHERE company = %s", (UNIT,))
        conn.commit()


# ── Chú thích từng ảnh: IIFE trả về window.__annotate([...]) theo thứ tự bước ──────────────────
def q(text_: str, tag: str = "*") -> str:
    """JS tìm phần tử theo NỘI DUNG CHỮ (bền hơn selector CSS khi đổi class)."""
    return (f"[...document.querySelectorAll('{tag}')]"
            f".find(e=>e.textContent.trim().startsWith({text_!r}) && !e.querySelector('{tag}'))")


MENU = """(() => {
  const it = (t) => [...document.querySelectorAll('.ant-menu-submenu-title, .ant-menu-item')]
      .find(e => e.textContent.trim() === t);
  return window.__annotate([it('Nhập liệu số liệu'), it('Quản lý hợp đồng'), it('Báo cáo')]);
})()"""

LIST_SCREEN = """(() => {
  const add = [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Thêm số liệu'));
  const row = document.querySelector('.ant-table-tbody tr');
  const edit = row && row.querySelector('button');
  return window.__annotate([add, edit]);
})()"""

CONTRACT_LIST = """(() => {
  const add = [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Thêm hợp đồng'));
  const row = document.querySelector('table tbody tr');
  const act = row && row.querySelector('button');
  return window.__annotate([add, act]);
})()"""

#: Ô nhập có nhãn (`.form-field`) — dùng cho form hợp đồng / phụ lục.
FIELD = """(() => {
  // Form phụ lục mở CHỒNG lên modal chi tiết → có 2 `.ant-modal`. Phải lấy cái TRÊN CÙNG,
  // không thì dò nhầm sang modal dưới và không thấy ô nào.
  const modals = [...document.querySelectorAll('.ant-modal')];
  const root = modals.length ? modals[modals.length - 1] : document;
  const f = (t) => [...root.querySelectorAll('.form-field')]
      .find(e => e.textContent.trim().startsWith(t)) || null;
  return window.__annotate(%s);
})()"""

#: TIÊU ĐỀ KHỐI (vd "1. Tồn kho thành phẩm…") là thẻ thường, không phải `.form-field`. Lấy phần tử
#: SÂU NHẤT khớp để khung ôm đúng dòng tiêu đề chứ không bọc cả khối bên dưới.
BLOCK = """(() => {
  // Form phụ lục mở CHỒNG lên modal chi tiết → có 2 `.ant-modal`. Phải lấy cái TRÊN CÙNG,
  // không thì dò nhầm sang modal dưới và không thấy ô nào.
  const modals = [...document.querySelectorAll('.ant-modal')];
  const root = modals.length ? modals[modals.length - 1] : document;
  const f = (t) => {
    const hit = [...root.querySelectorAll('label, h3, h4, div, strong, button')]
        .filter(e => e.textContent.trim().startsWith(t));
    return hit.length ? hit[hit.length - 1] : null;
  };
  return window.__annotate(%s);
})()"""


def _targets(tpl: str, labels: tuple[str, ...]) -> str:
    return tpl % ("[" + ", ".join(f"f({x!r})" for x in labels) + "]")


def field_targets(*labels: str) -> str:
    return _targets(FIELD, labels)


def block_targets(*labels: str) -> str:
    return _targets(BLOCK, labels)


#: Đăng nhập hộ có thanh cảnh báo vàng cố định trên cùng — đơn vị thật KHÔNG thấy nó, phải gỡ
#: khỏi ảnh. Gỡ luôn phần chừa chỗ (marginTop/top/height) mà khung admin cộng thêm cho thanh đó.
HIDE_BANNER = """(() => {
  // Bắt ĐÚNG thanh banner bằng style riêng của nó (position:fixed + z-index 2000). Dò theo
  // textContent sẽ khớp cả div TỔ TIÊN bọc toàn trang → xoá nhầm là mất sạch giao diện.
  document.querySelectorAll('div[style*="z-index: 2000"]').forEach((e) => e.remove());
  document.querySelectorAll('[style*="margin-top: 36px"], [style*="top: 36px"]').forEach((e) => {
    e.style.marginTop = '0'; e.style.top = '0'; e.style.height = '100vh';
  });
  return true;
})()"""


def open_modal(page, button_text: str) -> None:
    """Bấm nút mở modal + ép hiện (animation AntD hay kẹt khi chạy headless)."""
    page.add_style_tag(content=".ant-modal,.ant-modal-mask{opacity:1!important;"
                               "transform:none!important;animation:none!important}")
    page.click(f'button:has-text("{button_text}")')
    page.wait_for_selector(".ant-modal", timeout=8000)
    page.wait_for_timeout(500)


CONTRACT_DETAIL = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].pop();
  const tab = (t) => [...m.querySelectorAll('.ant-tabs-tab')].find(e => e.textContent.startsWith(t));
  const add = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Thêm phụ lục'));
  return window.__annotate([m.querySelector('.kpi-row'), tab('Thông tin'), tab('Phụ lục'), add]);
})()"""


def open_detail(page) -> None:
    """Mở màn chi tiết của hợp đồng giao-nhiều-lần (bấm Xem trên bảng danh sách)."""
    page.add_style_tag(content=".ant-modal,.ant-modal-mask{opacity:1!important;"
                               "transform:none!important;animation:none!important}")
    page.evaluate("""(() => {
      const row = [...document.querySelectorAll('table tbody tr')]
          .find(r => r.textContent.includes('HĐ-102/2026'));
      [...row.querySelectorAll('button')].find(b => b.textContent.trim() === 'Xem').click();
    })()""")
    page.wait_for_selector(".ant-modal", timeout=8000)
    page.wait_for_timeout(700)


def open_annex_form(page) -> None:
    """Form PHỤ LỤC nằm 2 lớp: bấm Xem hợp đồng giao-nhiều-lần → Thêm phụ lục."""
    page.add_style_tag(content=".ant-modal,.ant-modal-mask{opacity:1!important;"
                               "transform:none!important;animation:none!important}")
    page.evaluate("""(() => {
      const row = [...document.querySelectorAll('table tbody tr')]
          .find(r => r.textContent.includes('HĐ-102/2026'));
      [...row.querySelectorAll('button')].find(b => b.textContent.trim() === 'Xem').click();
    })()""")
    page.wait_for_selector(".ant-modal", timeout=8000)
    page.wait_for_timeout(400)
    page.click('button:has-text("Thêm phụ lục")')
    page.wait_for_timeout(600)


def main() -> int:
    admin = call("POST", "/api/auth/login", None,
                 {"username": "admin", "password": "admin"})["access_token"]
    tok = call("POST", "/api/auth/impersonate", admin, {"username": MEMBER})["access_token"]
    clean()               # chạy lại lần 2 không nhân đôi dữ liệu mẫu
    seed(tok)
    seed_legacy()
    OUT.mkdir(exist_ok=True)

    with sync_playwright() as p:
        page = browser_page(p, 1500, 820)
        page.context.add_init_script(f"localStorage.setItem('vrg_token', {tok!r});"
                                     "localStorage.removeItem('vrg_admin_token');")

        def shot(url: str, targets: str, name: str, *, wait_for: str, setup=None) -> None:
            """Mọi ảnh đều gỡ thanh 'đăng nhập hộ' trước, rồi mới chạy setup riêng của màn."""
            def _prep(pg):
                pg.evaluate(HIDE_BANNER)
                if setup:
                    setup(pg)
            annotated_shot(page, url, targets, str(OUT / name), wait_for=wait_for, setup=_prep)

        shot(f"{WEB}/bao-cao-thu-mua", MENU, "01-menu.png", wait_for=".ant-menu")
        shot(f"{WEB}/bao-cao-thu-mua", LIST_SCREEN, "02-thu-mua-danh-sach.png",
             wait_for=".ant-table")
        shot(f"{WEB}/bao-cao-thu-mua",
             block_targets("Hôm nay đơn vị KHÔNG", "Mủ nước", "Mủ chén",
                           "Mủ nguyên liệu nước chưa cán vắt", "Thu mua thành phẩm"),
             "03-thu-mua-form.png", wait_for=".ant-table",
             setup=lambda pg: open_modal(pg, "Thêm số liệu"))
        shot(f"{WEB}/bao-cao-ton-kho",
             block_targets("Lấy tồn ngày trước", "1. Tồn kho thành phẩm chế biến",
                           "2. Tồn kho thành phẩm đã nhập kho", "3. Tồn kho nguyên liệu"),
             "04-ton-kho.png", wait_for=".ant-table",
             setup=lambda pg: open_modal(pg, "Thêm số liệu"))
        shot(f"{WEB}/hop-dong/khach-hang", CONTRACT_LIST, "05-khach-hang.png", wait_for="table")
        shot(f"{WEB}/hop-dong", CONTRACT_LIST, "06-hop-dong-danh-sach.png", wait_for="table")
        shot(f"{WEB}/hop-dong",
             field_targets("Số hợp đồng", "Khách hàng", "Loại hợp đồng", "Loại giao",
                           "Ngày ký", "Ngày bắt đầu"),
             "07-hop-dong-form.png", wait_for="table",
             setup=lambda pg: open_modal(pg, "Thêm hợp đồng"))
        shot(f"{WEB}/hop-dong", CONTRACT_DETAIL, "08-hop-dong-chi-tiet.png",
             wait_for="table", setup=open_detail)
        shot(f"{WEB}/hop-dong",
             field_targets("Số phụ lục", "Ngày bắt đầu", "Ngày giao", "Hình thức tiêu thụ"),
             "09-phu-luc-form.png", wait_for="table", setup=open_annex_form)
        shot(f"{WEB}/bao-cao-tieu-thu",
             "(() => window.__annotate([document.querySelector('table')]))()",
             "10-bao-cao-tieu-thu.png", wait_for="table")
        shot(f"{WEB}/nhu-cau-thi-truong",
             "(() => window.__annotate([document.querySelector('.card')]))()",
             "11-nhu-cau-thi-truong.png", wait_for=".card")
        shot(f"{WEB}/ke-hoach-nam", "(() => window.__annotate([document.querySelector('table')]))()",
             "12-ke-hoach-nam.png", wait_for="table")
        shot(f"{WEB}/thong-ke-hop-dong",
             "(() => window.__annotate([document.querySelector('.ant-table')]))()",
             "13-hop-dong-cu.png", wait_for=".ant-table")

    clean()
    print(f"Xong. Ảnh ở {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
