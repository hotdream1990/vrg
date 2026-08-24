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
#: Đơn vị mẫu — dò theo TỪ KHOÁ chứ không ghi cứng tên đầy đủ: tên đơn vị đổi (hoặc DB được
#: clone lại từ prod với tên đầy đủ "Công ty Cổ phần Cao Su Bảo Lâm") là script chết ở bước seed.
UNIT_KEY = "Bảo Lâm"
UNIT = UNIT_KEY          # gán lại bằng tên THẬT trong main(), sau khi hỏi API
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


def seed(tok: str, cus: int, master_id: int) -> None:
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
        "plan_sales_spot_tonnes": 4500,
        "signed_lt_tonnes": 8200, "carry_lt_tonnes": 350, "carry_spot_tonnes": 120})
    call("PUT", "/api/member/market-demand", tok, {
        "company": UNIT, "as_of": D(0),
        "content": "Khách Trung Quốc hỏi mua SVR 10 giao tháng sau, số lượng khoảng 500 tấn. "
                   "Giá chào quanh 41,5 triệu đ/tấn, đang thương lượng."})


    # HĐ giao 1 lần, ĐÃ giao → lên Báo cáo tiêu thụ. Ngày giao phải NẰM TRONG kỳ mặc định của màn
    # báo cáo (đầu tháng → hôm nay), nếu không ảnh chụp ra toàn số 0.
    delivered_1 = max(D(1), D(TODAY.day - 1))
    call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "code": "HĐ-101/2026", "customer_id": cus, "delivery_type": "single",
        "contract_type": "spot", "sign_date": D(9),
        "delivered_at": delivered_1, "channel": "domestic",
        "invoice_no": "HĐ 0001234",
        "lines": [{"grade": "SVR 3L", "qty": 120, "price": 43.5, "ccy": "VND"}]})
    # HĐ giao nhiều lần: 1 đợt đã giao + 1 đợt đang chờ giao. Còn 350 tấn chưa lập đợt để ảnh
    # "Hoàn thành hợp đồng" có phần chênh thật (nếu giao vừa đủ thì màn đó không nói lên điều gì).
    parent = call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "code": "HĐ-102/2026", "customer_id": cus, "delivery_type": "multi",
        "contract_type": "long_term", "master_id": master_id,   # HĐ dài hạn là phụ lục của hồ sơ
        "sign_date": D(20), "expiry_date": D(-160),
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 900, "price": 41.8, "ccy": "VND"}]})["contract"]
    call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "parent_id": parent["id"], "code": "Đợt 01/HĐ-102",
        "delivered_at": D(0), "channel": "export",
        "invoice_no": "HĐ 0001255",
        "payment_date": D(0), "payment_qty": 300,
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 300, "price": 1620, "ccy": "USD",
                   "fx": 26150}]})
    call("PUT", "/api/sales-contracts", tok, {
        "company": UNIT, "parent_id": parent["id"], "code": "Đợt 02/HĐ-102",
        "channel": "export",
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 250, "price": 1635, "ccy": "USD",
                   "fx": 26200}]})


def seed_customers(tok: str) -> int:
    """Danh mục khách hàng — tạo TRƯỚC hồ sơ mẹ (hồ sơ bắt buộc gán khách) và trước hợp đồng."""
    cus = call("PUT", "/api/customers", tok, {
        "company": UNIT, "name": "Công ty TNHH Cao su Sài Gòn", "code": "KH-01",
        "note": "Khách hàng dài hạn"})["id"]
    call("PUT", "/api/customers", tok, {
        "company": UNIT, "name": "Shanghai Rubber Trading Co.", "code": "KH-02"})
    return cus


def seed_master(tok: str, cus: int) -> int:
    """1 hồ sơ HỢP ĐỒNG MẸ (HĐDH) — phải lập TRƯỚC khi seed hợp đồng: từ 24/08/2026 mọi HĐ dài hạn
    bắt buộc thuộc một hồ sơ, seed hợp đồng trước là bị chặn 400."""
    master = call("PUT", "/api/master-contracts", tok, {
        "company": UNIT, "code": "01/2026/HĐDH-BL", "master_type": "long_term",
        "customer_id": cus, "sign_date": D(200), "expiry_date": D(-160),
        "price_formula": "Giá SICOM TSR20 bình quân tuần trước liền kề + 30 USD/tấn, FOB HCM",
        "lines": [{"grade": "SVR 3L", "qty": 1200, "price": 1780, "ccy": "USD", "fx": 26300},
                  {"grade": "SVR 10 / CSR 10", "qty": 800, "price": 1650, "ccy": "USD",
                   "fx": 26300}],
    })["master"]
    return master["id"]


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
        # `master_contract` phải xoá TRƯỚC `unit_customer` (hồ sơ trỏ tới khách) và SAU
        # `sales_contract` (không xoá được hồ sơ còn phụ lục ở tầng nghiệp vụ; ở đây xoá thẳng DB).
        for t in ("master_contract", "unit_customer", "unit_daily_report", "unit_purchase_plan",
                  "market_demand", "unit_stock_contract"):
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

#: Dùng chung cho màn Khách hàng và màn Hợp đồng — nút thêm ở hai màn khác chữ ("Thêm khách
#: hàng" / "Thêm hợp đồng") nên dò theo 'Thêm', dò cả câu là màn kia mất badge số 1.
CONTRACT_LIST = """(() => {
  const add = [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Thêm'));
  const row = document.querySelector('table tbody tr');
  const act = row && row.querySelector('button');
  return window.__annotate([add, act]);
})()"""

#: Riêng màn HỢP ĐỒNG: chỉ thêm ô lọc **Hình thức** (khoanh đúng ô, không khoanh cả thanh lọc —
#: hướng dẫn cần chỉ vào thứ người đọc phải bấm).
CONTRACT_LIST_SCREEN = """(() => {
  const add = [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Thêm hợp đồng'));
  const chan = [...document.querySelectorAll('.blt-date-label')]
      .find(e => e.textContent.trim().startsWith('Hình thức'));
  const row = document.querySelector('table tbody tr');
  return window.__annotate([add, chan, row && row.querySelector('button')]);
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


#: Trộn ô-có-nhãn `f('…')` và tiêu-đề-khối `b('…')` trong CÙNG một ảnh — form hợp đồng cần cả hai
#: (các ô ở đầu form + khối "Chi tiết hợp đồng" + ô "Thành tiền" nằm trong bảng dòng chi tiết).
MIXED = """(() => {
  const modals = [...document.querySelectorAll('.ant-modal')];
  const root = modals.length ? modals[modals.length - 1] : document;
  const f = (t) => [...root.querySelectorAll('.form-field')]
      .find(e => e.textContent.trim().startsWith(t)) || null;
  const b = (t) => {
    const hit = [...root.querySelectorAll('label, h3, h4, div, strong, button')]
        .filter(e => e.textContent.trim().startsWith(t));
    return hit.length ? hit[hit.length - 1] : null;
  };
  return window.__annotate([%s]);
})()"""


def mixed_targets(*items: tuple[str, str]) -> str:
    """`("f", "Số hợp đồng")` = ô có nhãn · `("b", "Chi tiết hợp đồng")` = tiêu đề khối."""
    return MIXED % ", ".join(f"{kind}({label!r})" for kind, label in items)


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


#: Hộp nhắc việc "đơn vị còn thiếu gì" — nằm ở khung nên hiện trên MỌI màn của đơn vị.
CHECKLIST = """(() => {
  const box = document.querySelector('.dsn');
  const row = (t) => [...box.querySelectorAll('div')].find(e => e.textContent.trim().startsWith(t));
  return window.__annotate([box.querySelector('.dsn-badge'), row('Thu mua'), row('Tồn kho'),
                            box.querySelector('.dsn-toggle')]);
})()"""

#: Popup thêm/sửa khách hàng (từ 06/08/2026 nhập trong popup, không nhập thẳng trên trang nữa).
CUSTOMER_MODAL = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].pop();
  const f = (t) => [...m.querySelectorAll('.form-field')]
      .find(e => e.textContent.trim().startsWith(t));
  return window.__annotate([f('Đơn vị'), f('Tên khách hàng'), f('Mã KH'), f('Mã số thuế'),
                            m.querySelector('.ant-modal-footer .ant-btn-primary')]);
})()"""

CONTRACT_DETAIL = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].pop();
  const tab = (t) => [...m.querySelectorAll('.ant-tabs-tab')].find(e => e.textContent.startsWith(t));
  const btn = (t) => [...m.querySelectorAll('button')].find(b => b.textContent.includes(t));
  // Nút đổi loại giao đổi CHỮ theo hợp đồng ("Chuyển sang giao nhiều lần" / "Chuyển về giao 1
  // lần") — dò đúng một câu là ảnh mất badge và các số bước sau bị dồn lên.
  return window.__annotate([m.querySelector('.kpi-row'), btn('Chuyển'),
                            btn('Hoàn thành hợp đồng'), tab('Thông tin'), tab('Đợt giao'),
                            btn('Thêm đợt giao')]);
})()"""

#: Màn "Hoàn thành hợp đồng" — modal nhỏ nên nút ở đáy vẫn nằm trong khung nhìn.
COMPLETE_MODAL = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].pop();
  const sum = m.querySelector('.ant-modal-body > div');
  const day = [...m.querySelectorAll('.form-field')]
      .find(e => e.textContent.trim().startsWith('Ngày hoàn thành'));
  const ok = m.querySelector('.ant-modal-footer .ant-btn-primary');
  return window.__annotate([sum, day, ok]);
})()"""


def open_contract_form(page) -> None:
    """Form hợp đồng, dòng đầu chọn sẵn LATEX — có vậy ảnh mới hiện đúng cặp ô "SL nước (tấn)" +
    "Quy khô (tấn)" của 3 chủng loại bán theo mủ nước (chốt PA1). Để trống chủng loại thì nhãn chỉ
    là "SL (tấn)", người đọc hướng dẫn không thấy được chỗ khác biệt."""
    open_modal(page, "Thêm hợp đồng")
    # Chọn HĐ DÀI HẠN để ảnh có ô "Hợp đồng mẹ *": ô này CHỈ hiện với HĐ dài hạn (HĐ chuyến ẩn
    # hẳn — chốt 24/08/2026), để mặc định thì người đọc hướng dẫn không thấy ô đang được nói tới.
    page.locator('label:has-text("Loại hợp đồng") select').first.select_option("long_term")
    page.wait_for_timeout(400)
    page.locator(".ct-line select").first.select_option(label="LATEX")
    page.wait_for_timeout(400)


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


def open_batch_form(page) -> None:
    """Form ĐỢT GIAO nằm 2 lớp: bấm Xem hợp đồng giao-nhiều-lần → Thêm đợt giao."""
    open_detail(page)
    page.click('button:has-text("Thêm đợt giao")')
    page.wait_for_timeout(600)


def open_master_form(page) -> None:
    """Phiếu THÊM hợp đồng mẹ."""
    page.click('button:has-text("Thêm hợp đồng mẹ")')
    page.wait_for_timeout(700)


def open_master_detail(page) -> None:
    """Màn chi tiết hồ sơ (có mục Phụ lục + 2 nút thêm/gắn)."""
    page.click('tbody button:has-text("Xem")')
    page.wait_for_timeout(900)


def open_complete_modal(page) -> None:
    """Màn chốt HOÀN THÀNH hợp đồng — chỉ MỞ để chụp, không bấm nút hoàn thành."""
    open_detail(page)
    page.click('button:has-text("Hoàn thành hợp đồng")')
    page.wait_for_timeout(600)


def resolve_unit(admin: str) -> str:
    """Tên THẬT của đơn vị mẫu (dò theo `UNIT_KEY`). Không có thì dừng hẳn với thông báo rõ ràng —
    chạy tiếp với tên sai chỉ tạo ra bộ ảnh trống mà không ai để ý."""
    names = [u["name"] for u in call("GET", "/api/member-units", admin)]
    hit = [n for n in names if UNIT_KEY in n]
    if len(hit) != 1:
        raise SystemExit(f"Không xác định được đơn vị mẫu từ khoá {UNIT_KEY!r}: {hit or 'không có'}")
    return hit[0]


def main() -> int:
    global UNIT
    admin = call("POST", "/api/auth/login", None,
                 {"username": "admin", "password": "admin"})["access_token"]
    UNIT = resolve_unit(admin)
    tok = call("POST", "/api/auth/impersonate", admin, {"username": MEMBER})["access_token"]
    clean()               # chạy lại lần 2 không nhân đôi dữ liệu mẫu
    cus = seed_customers(tok)
    seed(tok, cus, seed_master(tok, cus))
    seed_legacy()
    OUT.mkdir(exist_ok=True)

    with sync_playwright() as p:
        page = browser_page(p, 1500, 820)
        page.context.add_init_script(f"localStorage.setItem('vrg_token', {tok!r});"
                                     "localStorage.removeItem('vrg_admin_token');")

        # Chụp lại MỘT vài ảnh: `… shoot.py 05` (lọc theo đầu tên file). Ảnh mang ngày tháng của
        # số liệu mẫu nên chụp lại cả bộ là 14 file đều đổi — chỉ nên làm khi đổi giao diện diện rộng.
        only = tuple(sys.argv[1:])

        def shot(url: str, targets: str, name: str, *, wait_for: str, setup=None) -> None:
            """Mọi ảnh đều gỡ thanh 'đăng nhập hộ' trước, rồi mới chạy setup riêng của màn."""
            if only and not name.startswith(only):
                return

            def _prep(pg):
                pg.evaluate(HIDE_BANNER)
                if setup:
                    setup(pg)
            annotated_shot(page, url, targets, str(OUT / name), wait_for=wait_for, setup=_prep)

        shot(f"{WEB}/bao-cao-thu-mua", MENU, "01-menu.png", wait_for=".ant-menu")
        shot(f"{WEB}/bao-cao-thu-mua", CHECKLIST, "01b-nhac-viec.png", wait_for=".dsn")
        shot(f"{WEB}/bao-cao-thu-mua", LIST_SCREEN, "02-thu-mua-danh-sach.png",
             wait_for=".ant-table")
        shot(f"{WEB}/bao-cao-thu-mua",
             block_targets("Hôm nay đơn vị KHÔNG", "Mủ nước", "Mủ chén", "Thu mua thành phẩm"),
             "03-thu-mua-form.png", wait_for=".ant-table",
             setup=lambda pg: open_modal(pg, "Thêm số liệu"))
        shot(f"{WEB}/bao-cao-ton-kho",
             block_targets("Lấy tồn ngày trước", "1. Tồn kho thành phẩm chế biến",
                           "2. Tồn kho thành phẩm đã nhập kho", "3. Tồn kho nguyên liệu"),
             "04-ton-kho.png", wait_for=".ant-table",
             setup=lambda pg: open_modal(pg, "Thêm số liệu"))
        shot(f"{WEB}/hop-dong/khach-hang", CONTRACT_LIST, "05-khach-hang.png", wait_for="table")
        shot(f"{WEB}/hop-dong/khach-hang", CUSTOMER_MODAL, "05b-khach-hang-popup.png",
             wait_for="table", setup=lambda pg: open_modal(pg, "Thêm khách hàng"))
        shot(f"{WEB}/hop-dong", CONTRACT_LIST_SCREEN, "06-hop-dong-danh-sach.png", wait_for="table")
        shot(f"{WEB}/hop-dong",
             mixed_targets(("f", "Số hợp đồng"), ("f", "Hợp đồng mẹ"), ("f", "Khách hàng"),
                           ("f", "Loại hợp đồng"), ("f", "Loại giao"), ("f", "Ngày ký"),
                           ("f", "Ngày giao"), ("b", "Chi tiết hợp đồng"), ("f", "Thành tiền")),
             "07-hop-dong-form.png", wait_for="table", setup=open_contract_form)
        shot(f"{WEB}/hop-dong", CONTRACT_DETAIL, "08-hop-dong-chi-tiet.png",
             wait_for="table", setup=open_detail)
        shot(f"{WEB}/hop-dong",
             mixed_targets(("f", "Số đợt giao"), ("f", "Ngày giao"), ("f", "Hình thức tiêu thụ"),
                           ("b", "Chi tiết đợt giao"), ("f", "Số hoá đơn"),
                           ("b", "Thanh toán (mỗi đợt")),
             "09-dot-giao-form.png", wait_for="table", setup=open_batch_form)
        shot(f"{WEB}/hop-dong", COMPLETE_MODAL, "10-hoan-thanh-hop-dong.png",
             wait_for="table", setup=open_complete_modal)
        shot(f"{WEB}/hop-dong/hop-dong-me",
             "(() => window.__annotate([document.querySelector('.blt-toolbar'),"
             " document.querySelector('table')]))()",
             "05c-hop-dong-me-danh-sach.png", wait_for="table")
        shot(f"{WEB}/hop-dong/hop-dong-me",
             block_targets("Số hợp đồng *", "Loại hợp đồng mẹ *", "Khách hàng *",
                           "Chủng loại &", "Công thức giá"),
             "05d-hop-dong-me-form.png", wait_for="table", setup=open_master_form)
        shot(f"{WEB}/hop-dong/hop-dong-me",
             "(() => window.__annotate([document.querySelector('.ct-kpi'),"
             " [...document.querySelectorAll('h4')].find(e => e.textContent.includes('Phụ lục')),"
             " [...document.querySelectorAll('button')].find(e => e.textContent.includes('Thêm phụ lục')),"
             " [...document.querySelectorAll('button')].find(e => e.textContent.includes('Gắn hợp đồng'))"
             "]))()",
             "05e-hop-dong-me-chi-tiet.png", wait_for="table", setup=open_master_detail)
        shot(f"{WEB}/bao-cao-tieu-thu",
             "(() => window.__annotate([document.querySelector('.blt-toolbar'),"
             " document.querySelector('table')]))()",
             "11-bao-cao-tieu-thu.png", wait_for="table")
        shot(f"{WEB}/nhu-cau-thi-truong",
             "(() => window.__annotate([document.querySelector('.card')]))()",
             "12-nhu-cau-thi-truong.png", wait_for=".card")
        shot(f"{WEB}/ke-hoach-nam",
             r"""(() => {
               // Khớp CẢ HAI mảnh chữ: 4 cột đầu đều bắt đầu bằng "HĐ dài hạn"/"Kế hoạch" nên
               // chỉ dò startsWith sẽ trỏ trùng ô, số bước bị chồng lên nhau.
               const th = (a, b) => [...document.querySelectorAll('th')].find((e) => {
                 const t = e.textContent.replace(/\s+/g, ' ').trim();
                 return t.startsWith(a) && (!b || t.includes(b));
               });
               return window.__annotate([th('Kế hoạch thu mua'), th('Kế hoạch tiêu thụ'),
                                         th('HĐ dài hạn', 'đã ký'),
                                         th('HĐ dài hạn', 'chuyển sang'),
                                         th('Kế hoạch doanh thu')]);
             })()""",
             "13-ke-hoach-nam.png", wait_for="table")
        shot(f"{WEB}/thong-ke-hop-dong",
             "(() => window.__annotate([document.querySelector('.ant-table')]))()",
             "14-hop-dong-cu.png", wait_for=".ant-table")

    clean()
    print(f"Xong. Ảnh ở {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
