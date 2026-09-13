#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH của sổ tay "Lãnh đạo Tập đoàn" (chạy khi giao diện đổi).

Cách làm: admin tạo (nếu chưa có) tài khoản mẫu `lanhdao@vrg.vn` trên máy dev → ĐĂNG NHẬP HỘ →
Playwright chụp ảnh có chú thích trên số liệu thật của DB dev → xoá tài khoản mẫu nếu script tự tạo.
Hai ảnh Trợ lý AI và Bản tin biến động gọi AI THẬT (mất vài chục giây, tốn một ít phí AI).

Chạy:  ./scripts/dev.sh (API 8390 + Web 5390) rồi
       uv run --directory apps/api --with playwright python \
           ../../docs/huong-dan/lanh-dao-tap-doan/shoot.py
       (chụp lại vài ảnh: thêm tiền tố tên file, vd `… shoot.py 03 04`)
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts"))

from playwright.sync_api import sync_playwright  # noqa: E402
from shoot import annotated_shot, browser_page  # noqa: E402

API = "http://localhost:8390"
WEB = "http://localhost:5390"
OUT = pathlib.Path(__file__).parent / "img"
LEADER = "lanhdao@vrg.vn"
AI_QUESTION = "Giá mủ nước 30 ngày qua diễn biến ra sao?"
AI_TIMEOUT_MS = 180_000

#: Tìm phần tử theo chữ — dùng chung cho mọi khung chú thích.
FIND = """
const byText = (sel, t, exact) => [...document.querySelectorAll(sel)]
  .find(e => exact ? e.textContent.trim() === t : e.textContent.includes(t));
// Khung + số thứ tự, BỎ mũi tên nối: mũi tên chạy ngang qua chữ trên thanh công cụ, khó đọc.
const mark = (els) => { const n = window.__annotate(els);
  document.querySelectorAll('#anno-overlay path').forEach(p => p.remove()); return n; };
const card = (t) => [...document.querySelectorAll('.card')].find(c => {
  const h = c.querySelector('h3, .card-head'); return h && h.textContent.includes(t); });
"""

#: DB dev còn sót đơn vị do bộ test tự tạo (tiền tố `_zz`) → gỡ khỏi chữ trên màn trước khi chụp.
HIDE_TEST_UNITS = """(() => {
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) if (n.nodeValue.includes('_zz'))
    n.nodeValue = n.nodeValue.replace(/,?\\s*_zz[^,…]*/g, '');
})()"""

#: Thanh vàng "đang đăng nhập hộ" che phần đầu trang → gỡ trước mọi ảnh (dò theo thuộc tính,
#: không theo chữ — div cha bọc cả trang cũng chứa chữ đó).
HIDE_BANNER = """(() => {
  document.querySelectorAll('div').forEach(d => {
    const st = getComputedStyle(d); const b = d.getBoundingClientRect();
    if (st.position === 'fixed' && Math.round(b.height) === 36 && b.top === 0) d.remove();
  });
  document.querySelectorAll('.ant-layout').forEach(l => {
    l.style.marginTop = '0';
    if (String(l.style.height).includes('calc')) l.style.height = '100vh';
  });
})()"""


def js(body: str) -> str:
    return f"(() => {{ {FIND} {body} }})()"


MENU = js("""
  const it = (t) => [...document.querySelectorAll('.ant-menu-submenu-title, .ant-menu-item')]
      .find(e => e.textContent.trim() === t);
  return mark([it('Dashboard'), it('Phân tích & Bản tin'), it('Báo cáo & Thống kê'),
    it('Số liệu thị trường (chỉ xem)'), it('Số liệu đơn vị (chỉ xem)'), it('Hợp đồng (chỉ xem)'),
    it('Hồ sơ cá nhân')]);""")

DASHBOARD = js("""
  return mark([byText('button', 'Cập nhật'), document.querySelector('.kpi-row'),
    document.querySelector('#sec-hoitu'), document.querySelector('#sec-giasan'),
    document.querySelector('#sec-tonkho .ant-segmented')]);""")

AI_EMPTY = js("""
  const seg = [...document.querySelectorAll('.ant-segmented')];
  const chips = byText('div', 'Gợi ý câu hỏi:', true)?.parentElement;
  return mark([seg[0], seg[1], byText('button, a', 'Trợ lý làm được gì?'), chips,
    document.querySelector('textarea'), byText('button', 'Gửi')]);""")

AI_ANSWER = js("""
  const bubbles = [...document.querySelectorAll('div')].filter(d => d.style.borderRadius === '12px');
  const q = bubbles.find(b => b.textContent.includes('Giá mủ nước 30 ngày'));
  const a = bubbles[bubbles.length - 1];
  const art = a && (a.querySelector('.recharts-wrapper, table, canvas, svg')?.closest('div'));
  const src = a && [...a.querySelectorAll('div')].find(d => d.textContent.trim().startsWith('Nguồn:'));
  return mark([q, a && a.firstElementChild, art, src]);""")

HISTORY = js("""
  return mark([document.querySelector('.ant-picker-range'),
    document.querySelector('input[placeholder="Tìm theo câu hỏi…"]'),
    document.querySelector('.ant-table-row')]);""")

FLOOR_SUGGEST = js("""
  const table = [...document.querySelectorAll('.card table')]
    .find(t => t.textContent.includes('Đề xuất điều chỉnh'));
  const bar = byText('.card, .blt-toolbar', 'Chế độ:');
  return mark([bar, byText('button', 'Xem & xuất tờ trình'), table]);""")

MOVEMENT = js("""
  const box = document.querySelector('#sec-nhandinh');
  const btn = box && box.querySelector('button.btn-primary');
  // Lấy khối NHỎ NHẤT bắt đầu bằng "Tổng thể." — khối cha bọc cả danh sách cũng bắt đầu bằng chữ đó.
  const all = box && [...box.querySelectorAll('div')].filter(d => d.textContent.trim().startsWith('Tổng thể.'))
    .sort((a, b) => a.getBoundingClientRect().height - b.getBoundingClientRect().height)[0];
  const trend = box && [...box.querySelectorAll('div')].find(d => d.textContent.includes('Gợi ý xu hướng')
    && d.getBoundingClientRect().height < 260);
  return mark([btn, all, trend]);""")

BULLETIN_LIST = js("""
  const row = document.querySelector('.blt-list-table tbody tr');
  return mark([row && row.querySelector('a.blt-link'),
    row && byText('.blt-list-table tbody tr:first-child button, .blt-list-table tbody tr:first-child a', 'Xem'),
    row && byText('.blt-list-table tbody tr:first-child button, .blt-list-table tbody tr:first-child a', 'Tải')]);""")

BULLETIN_DETAIL = js("""
  return mark([document.querySelector('.blt-back'),
    document.querySelector('.actions .btn-primary'), document.querySelector('.blt-section')]);""")

WEEKLY = js("""
  const saved = card('Báo cáo đã lưu');
  return mark([saved, byText('button', 'Xuất PDF'),
    document.querySelectorAll('.blt-section')[1]]);""")

PERIOD = js("""
  const seg = [...document.querySelectorAll('.card .ant-segmented')];
  return mark([seg[0], seg[1], byText('button', 'Xuất Excel'), document.querySelector('table thead')]);""")

CONSUMPTION = js("""
  return mark([document.querySelector('.blt-toolbar'), document.querySelector('.kpi-row'),
    byText('button', 'Xuất Excel')]);""")

STATS = js("""
  return mark([document.querySelector('.card .ant-segmented')?.closest('.card'),
    document.querySelector('.ant-breadcrumb')?.closest('.card'), document.querySelector('.kpi-row'),
    document.querySelector('tr.row-drill'), byText('button', 'Xuất Excel')]);""")

STOCK = js("""
  return mark([byText('.card', 'Ảnh chụp tại ngày chốt'), document.querySelector('.kpi-row'),
    document.querySelector('tr.row-drill'), byText('button', 'Xuất Excel')]);""")

SUBMISSION = js("""
  return mark([document.querySelector('.ant-segmented'), byText('.card', 'Lượt cần nhập'),
    document.querySelector('.anticon-close-circle')?.closest('td')]);""")

PRICE_BOARD = js("""
  return mark([document.querySelector('.ant-alert'), document.querySelector('.dsn-head'),
    document.querySelector('.blt-toolbar'), document.querySelector('.card table')]);""")

FLOOR = js("""
  return mark([card('Các lần đã có'), document.querySelector('.blt-section.blt-editable table')]);""")

UNIT_DAILY = js("""
  const row = document.querySelector('.ant-table-tbody tr:not(.ant-table-measure-row)');
  return mark([document.querySelector('.ant-alert'), document.querySelector('.ant-segmented'),
    document.querySelector('.ant-picker'), row && row.querySelector('button')]);""")

CONTRACTS = js("""
  const status = byText('label, .blt-date-label', 'Trạng thái');
  const filters = status && status.closest('.card, .blt-toolbar');
  const row = document.querySelector('.card.table-scroll tbody tr');
  const view = row && [...row.querySelectorAll('button')].find(b => b.textContent.includes('Xem'));
  return mark([document.querySelector('.ant-alert'), filters, row, view]);""")

PROFILE = js("""
  const pw = [...document.querySelectorAll('input[type="password"]')];
  return mark([pw[0], pw[1], pw[2], byText('button', 'Đổi mật khẩu')]);""")


def call(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def ensure_leader(admin: str) -> bool:
    """Tạo tài khoản mẫu nếu chưa có. Trả True nếu script tự tạo (để dọn sau)."""
    if any(u["username"] == LEADER for u in call("GET", "/api/users", admin)):
        return False
    call("POST", "/api/users", admin, {"username": LEADER, "password": "docs-only-123",
                                       "full_name": "Lãnh đạo Tập đoàn", "role": "executive",
                                       "email": LEADER})
    return True


def main() -> int:
    admin = call("POST", "/api/auth/login", None, {"username": "admin", "password": "admin"})["access_token"]
    created = ensure_leader(admin)
    lead = call("POST", "/api/auth/impersonate", admin, {"username": LEADER})["access_token"]
    bulletins = call("GET", "/api/bulletins/published", lead)["bulletins"]
    OUT.mkdir(exist_ok=True)
    only = tuple(sys.argv[1:])

    with sync_playwright() as p:
        page = browser_page(p, 1500, 860)
        page.context.add_init_script(f"localStorage.setItem('vrg_token', {lead!r});"
                                     "localStorage.removeItem('vrg_admin_token');")

        def shot(url: str, targets: str, name: str, *, wait_for: str, setup=None,
                 width: int = 1500, height: int = 860) -> None:
            if only and not name.startswith(only):
                return

            def _prep(pg):
                pg.evaluate(HIDE_BANNER)
                if setup:
                    setup(pg)
                pg.evaluate(HIDE_TEST_UNITS)
            annotated_shot(page, url, targets, str(OUT / name), wait_for=wait_for, setup=_prep,
                           viewport={"width": width, "height": height}, settle=1500)
            print("  ✓", name)

        def click(text: str, selector: str = "button"):
            def _do(pg):
                pg.locator(selector, has_text=text).first.click()
                pg.wait_for_timeout(2500)
            return _do

        def set_dates(*values: str | None, after: str | None = None):
            """Gõ ngày vào các ô chọn ngày theo thứ tự (None = giữ nguyên). DB dev là bản sao prod
            cũ vài tuần nên các màn mặc định lấy "hôm nay" sẽ trống — phải lùi về kỳ có số liệu."""
            def _do(pg):
                inputs = pg.locator(".ant-picker input")
                for i, v in enumerate(values):
                    if v is None:
                        continue
                    # Ô ngày chỉ chốt chữ GÕ PHÍM THẬT (fill() không phát keydown) → gõ từng
                    # phím rồi Tab ra ngoài để ô tự chốt.
                    box = inputs.nth(i)
                    box.click()
                    pg.keyboard.press("ControlOrMeta+a")
                    box.press_sequentially(v, delay=30)
                    pg.keyboard.press("Tab")
                    pg.wait_for_timeout(800)
                pg.keyboard.press("Escape")
                if after:
                    pg.wait_for_selector(after, timeout=20000)
                pg.wait_for_timeout(2500)
            return _do

        def wait_gone(text: str, scope: str = "body"):
            def _do(pg):
                pg.wait_for_function(
                    f"!document.querySelector({scope!r}).textContent.includes({text!r})", timeout=60000)
                pg.wait_for_timeout(1000)
            return _do

        def chain(*steps):
            def _do(pg):
                for st in steps:
                    st(pg)
            return _do

        def ask_ai(pg):
            pg.fill("textarea", AI_QUESTION)
            pg.locator("button", has_text="Gửi").click()
            pg.wait_for_selector("text=Nguồn:", timeout=AI_TIMEOUT_MS)
            pg.wait_for_timeout(1500)

        def run_movement_ai(pg):
            pg.locator("#sec-nhandinh button.btn-primary").click()
            pg.wait_for_selector("#sec-nhandinh >> text=Tổng thể.", timeout=AI_TIMEOUT_MS)
            pg.wait_for_timeout(1000)

        # ── Tổng quan ───────────────────────────────────────────────────────────────────────
        shot(f"{WEB}/", MENU, "01-menu.png", wait_for=".ant-menu", height=1480)
        shot(f"{WEB}/", DASHBOARD, "02-dashboard.png", wait_for="#sec-tonkho", height=1500,
             setup=wait_gone("Đang tải", "#sec-tonkho"))
        # ── Phân tích & Bản tin ─────────────────────────────────────────────────────────────
        shot(f"{WEB}/tro-ly-ai", AI_EMPTY, "03-tro-ly-ai.png", wait_for="textarea")
        shot(f"{WEB}/tro-ly-ai", AI_ANSWER, "04-tro-ly-ai-tra-loi.png", wait_for="textarea",
             setup=ask_ai, height=1100)
        shot(f"{WEB}/tro-ly-ai/lich-su", HISTORY, "05-lich-su-hoi-dap.png", wait_for=".ant-table-row")
        shot(f"{WEB}/goi-y-gia-san", FLOOR_SUGGEST, "06-goi-y-gia-san.png", wait_for=".card table",
             setup=chain(wait_gone("Chọn lần ban hành"), wait_gone("Đang tính toán")), height=1100)
        shot(f"{WEB}/ban-tin-bien-dong", MOVEMENT, "07-ban-tin-bien-dong.png",
             wait_for="#sec-nhandinh button.btn-primary", setup=run_movement_ai, height=1100)
        shot(f"{WEB}/ban-tin", BULLETIN_LIST, "08-ban-tin-ngay.png", wait_for=".blt-list-table")
        if bulletins:
            shot(f"{WEB}/ban-tin/xem/{bulletins[0]['filename']}", BULLETIN_DETAIL,
                 "09-ban-tin-chi-tiet.png", wait_for=".blt-section")
        weekly_first = click("Tuần", ".card:has(h3:text('Báo cáo đã lưu')) .btn")
        shot(f"{WEB}/ban-tin/tuan", WEEKLY, "10-bao-cao-tuan.png", wait_for=".card",
             setup=weekly_first, height=1000)
        # ── Báo cáo & Thống kê ──────────────────────────────────────────────────────────────
        shot(f"{WEB}/bao-cao-tong-hop", PERIOD, "11-bao-cao-tong-hop.png", wait_for="table",
             setup=click("Tháng trước", ".ant-segmented-item"), width=1900, height=1000)
        shot(f"{WEB}/bao-cao-tieu-thu", CONSUMPTION, "12-bao-cao-tieu-thu.png", wait_for=".kpi-row",
             setup=set_dates("01/08/2026", "22/08/2026"), width=1700)
        shot(f"{WEB}/thong-ke/thu-mua", STATS, "13-thong-ke-thu-mua.png", wait_for=".ant-breadcrumb",
             setup=chain(click("Tháng trước", ".ant-segmented-item"),
                         lambda pg: pg.wait_for_selector("tr.row-drill", timeout=30000)), height=1300)
        shot(f"{WEB}/thong-ke/ton-kho", STOCK, "14-thong-ke-ton-kho.png", wait_for=".ant-breadcrumb",
             setup=set_dates("21/08/2026", after="tr.row-drill"), height=1300)
        shot(f"{WEB}/thong-ke/tinh-trang-nop", SUBMISSION, "15-theo-doi-nop-bao-cao.png",
             wait_for="table", setup=set_dates("10/08/2026", "23/08/2026"), width=1900, height=1000)
        # ── Số liệu & Hợp đồng (chỉ xem) ────────────────────────────────────────────────────
        shot(f"{WEB}/quan-ly-so-lieu/bang-gia-san", PRICE_BOARD, "16-bang-gia-cac-san.png",
             wait_for=".card table", width=1700)
        shot(f"{WEB}/quan-ly-so-lieu/gia-san-tap-doan", FLOOR, "17-gia-san-tap-doan.png",
             wait_for=".card", setup=chain(set_dates("01/07/2026"), click("Lần thứ 18")), height=1100)
        shot(f"{WEB}/bao-cao-ton-kho", UNIT_DAILY, "18-so-lieu-don-vi.png", wait_for=".ant-table",
             setup=set_dates("21/08/2026"), width=1900)
        shot(f"{WEB}/hop-dong", CONTRACTS, "19-hop-dong.png", wait_for="tfoot", width=2300,
             height=1000)
        shot(f"{WEB}/ho-so", PROFILE, "20-ho-so.png", wait_for=".ant-card")

    if created and not only:
        call("DELETE", f"/api/users/{LEADER}", admin)
        print("Đã xoá tài khoản mẫu.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
