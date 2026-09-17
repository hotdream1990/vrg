#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH của sổ tay "Lãnh đạo đơn vị thành viên" (chạy khi giao diện đổi).

Cách làm: admin ĐĂNG NHẬP HỘ tài khoản lãnh đạo mẫu (tính năng có sẵn) → seed số liệu + hộp thư
mẫu → Playwright chụp ảnh có chú thích → XOÁ sạch dữ liệu mẫu.

Chạy:  ./scripts/dev.sh (API 8390 + Web 5390) rồi
       uv run --directory apps/api --with playwright python \
           ../../docs/huong-dan/lanh-dao-don-vi/shoot.py
       (chụp lại vài ảnh: thêm tiền tố tên file, vd `… shoot.py 03 04`)
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts"))

import seed as S  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from shoot import annotated_shot, browser_page  # noqa: E402
from playwright.sync_api import Error as PlaywrightError  # noqa: E402

WEB = "http://localhost:5390"
OUT = pathlib.Path(__file__).parent / "img"

#: Thanh vàng "đang đăng nhập hộ" che mất phần đầu trang → gỡ trước mọi ảnh.
HIDE_BANNER = """(() => {
  // Thanh vàng "Đang xem với tư cách …" (ImpersonationBanner) là div position:fixed, cao 36px.
  // Dò theo THUỘC TÍNH chứ không theo nội dung: div cha bọc cả trang cũng bắt đầu bằng chữ đó,
  // dò theo chữ là xoá nhầm nguyên trang (đã dính).
  document.querySelectorAll('div').forEach(d => {
    const st = getComputedStyle(d);
    if (st.position === 'fixed' && Math.round(d.getBoundingClientRect().height) === 36
        && d.getBoundingClientRect().top === 0) d.remove();
  });
  document.querySelectorAll('.ant-layout').forEach(l => {
    l.style.marginTop = '0';
    if (String(l.style.height).includes('calc')) l.style.height = '100vh';
  });
})()"""


def btn(label: str) -> str:
    """JS: nút có chứa chữ `label`."""
    return f"[...document.querySelectorAll('button')].find(b=>b.textContent.includes({label!r}))"


MENU = """(() => {
  const it = (t) => [...document.querySelectorAll('.ant-menu-submenu-title, .ant-menu-item')]
      .find(e => e.textContent.trim() === t);
  return window.__annotate([it('Hỗ trợ & Thông báo'), it('Cảnh báo bất thường'),
                            it('Số liệu đơn vị (chỉ xem)'), it('Hợp đồng (chỉ xem)'), it('Báo cáo')]);
})()"""

INBOX = f"""(() => {{
  const send = {btn('Gửi yêu cầu hỗ trợ')};
  const filter = document.querySelector('.sp-row .ant-select');
  const search = document.querySelector('.ant-input-search input');
  const row = document.querySelector('.sp-item');
  return window.__annotate([send, filter, search, row]);
}})()"""

THREAD = f"""(() => {{
  const msg = document.querySelector('.sp-msg');
  const box = document.querySelector('textarea.sp-textarea');
  const send = {btn('Gửi phản hồi')};
  const done = {btn('Đánh dấu đã xong')};
  return window.__annotate([msg, box, send, done]);
}})()"""

COMPOSER = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].pop();
  if (!m) return 0;
  const inp = m.querySelector('input.sp-textarea');
  const area = m.querySelector('textarea.sp-textarea');
  const file = [...m.querySelectorAll('button')].find(b=>b.textContent.includes('Đính kèm'));
  const ok = [...m.querySelectorAll('button')].find(b=>b.textContent.trim() === 'Gửi yêu cầu');
  return window.__annotate([inp, area, file, ok]);
})()"""

CLOSED = f"""(() => {{
  const tag = [...document.querySelectorAll('.ant-tag')].find(t=>t.textContent.includes('Đã đóng'));
  const note = document.querySelector('.sp-compose h3');
  const again = {btn('Gửi yêu cầu mới')};
  return window.__annotate([tag, note, again]);
}})()"""

READONLY = """(() => {
  const alert = document.querySelector('.ant-alert');
  const range = document.querySelector('.blt-date-input');      // <select> thuần, không phải AntD
  const row = document.querySelector('.ant-table-tbody tr:not(.ant-table-measure-row)');
  const eye = row && row.querySelector('button');
  return window.__annotate([alert, range, eye]);
})()"""

PLAN = """(() => {
  const alert = document.querySelector('.ant-alert');
  const year = document.querySelector('.ant-select');
  const table = document.querySelector('table');
  return window.__annotate([alert, year, table]);
})()"""

CONSUMPTION = f"""(() => {{
  const dates = document.querySelector('.blt-toolbar, .card');
  const xlsx = {btn('Xuất Excel')};
  const table = document.querySelector('table');
  return window.__annotate([dates, xlsx, table]);
}})()"""

LIST_ONLY = """(() => {
  // Khoanh CẢ khối bộ lọc (không chỉ một ô) — người đọc cần thấy chỗ chọn kỳ/khách/trạng thái.
  const alert = document.querySelector('.ant-alert');
  const table = document.querySelector('table');
  const boxes = [...document.querySelectorAll('.card, .blt-toolbar')];
  const filter = boxes.find(c => !c.contains(table) && c.querySelector('input, select, .ant-select'));
  return window.__annotate([alert, filter, table]);
})()"""

#: Màn Nhu cầu thị trường: dòng chỉ xem · thanh lọc · ô Giao hàng + ô Kết quả của phiếu đã ký.
#: Lãnh đạo không có nút Thêm và cột Thao tác.
DEMAND = """(() => {
  const alert = document.querySelector('.ant-alert');
  const cards = [...document.querySelectorAll('.main .card')];
  const filter = cards.find(c => c.textContent.includes('Khoảng thời gian'));
  const box = cards.find(c => c.querySelector('table'));
  // Cột Kết quả đứng ngay sau cột Giao hàng → lấy hai ô liền nhau của cùng một dòng.
  const result = [...box.querySelectorAll('tbody td')]
      .find(td => td.textContent.trim().startsWith('Đã ký HĐMB'));
  const delivery = result && result.previousElementSibling;
  // Khung thanh lọc = từ chữ "Khoảng thời gian" tới hết ô Tìm (thẻ lọc rộng hết trang, khoanh cả thẻ
  // là dính vào khung dòng chỉ xem ngay phía trên).
  const a = filter.firstElementChild.getBoundingClientRect();
  const z = filter.querySelector('.ant-input-affix-wrapper').getBoundingClientRect();
  const bar = { getBoundingClientRect: () => ({ x: a.x, y: Math.min(a.y, z.y), width: z.right - a.x,
                                                height: Math.max(a.bottom, z.bottom) - Math.min(a.y, z.y) }) };
  return window.__annotate([alert, bar, delivery, result]);
})()"""


PROFILE = """(() => {
  const pw = [...document.querySelectorAll('input[type="password"]')];
  const save = [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Đổi mật khẩu'));
  return window.__annotate([pw[0], pw[1], pw[2], save]);
})()"""


#: Cảnh báo bất thường: khoảng ngày · thẻ tổng quan · tiêu đề nhóm đầu tiên · bảng · Xuất Excel.
ANOMALY = f"""(() => {{
  const range = document.querySelector('.ant-picker-range');
  const kpi = document.querySelector('.kpi-row');
  const head = document.querySelector('.ant-collapse-header');
  const table = document.querySelector('.ant-collapse .ant-table');
  const xlsx = {btn('Xuất Excel')};
  return window.__annotate([range, kpi, head, table, xlsx]);
}})()"""


def open_page(p, width: int, height: int):
    """Ưu tiên Chrome cài sẵn: bản Chromium đi kèm Playwright hay lệch phiên bản sau mỗi lần nâng
    cấp thư viện (chạy là báo thiếu file thực thi). Máy không có Chrome thì mới dùng bản kèm theo."""
    try:
        browser = p.chromium.launch(channel="chrome")
    except PlaywrightError:
        return browser_page(p, width, height)
    return browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)


def main() -> int:
    admin = S.call("POST", "/api/auth/login", None,
                   {"username": "admin", "password": "admin"})["access_token"]
    unit = S.resolve_unit(admin)
    S.ensure_leader(admin, unit)
    lead = S.call("POST", "/api/auth/impersonate", admin, {"username": S.LEADER})["access_token"]
    member = S.call("POST", "/api/auth/impersonate", admin, {"username": S.MEMBER})["access_token"]

    S.clean(unit)                       # chạy lại lần 2 không nhân đôi dữ liệu mẫu
    S.seed_unit_data(member, unit)
    ids = S.seed_inbox(admin, lead, unit)
    OUT.mkdir(exist_ok=True)

    with sync_playwright() as p:
        page = open_page(p, 1500, 860)
        page.context.add_init_script(f"localStorage.setItem('vrg_token', {lead!r});"
                                     "localStorage.removeItem('vrg_admin_token');")
        only = tuple(sys.argv[1:])

        def shot(url: str, targets: str, name: str, *, wait_for: str, setup=None,
                 wide: bool = False) -> None:
            """`wide`: bảng nhiều cột (tồn kho · hợp đồng) cần khung rộng hơn mới đủ cột.

            Phải nới VIEWPORT chứ đừng thu nhỏ bằng `body.style.zoom`: overlay chú thích vẽ theo
            toạ độ viewport nên zoom làm khung lệch hẳn khỏi phần tử (đã dính).
            """
            if only and not name.startswith(only):
                return

            def _prep(pg):
                pg.evaluate(HIDE_BANNER)
                if setup:
                    setup(pg)
            annotated_shot(page, url, targets, str(OUT / name), wait_for=wait_for, setup=_prep,
                           viewport={"width": 1900 if wide else 1500, "height": 860})
            print("  ✓", name)

        def open_composer(pg):
            """Mở form soạn + ép hiện (animation AntD hay kẹt khi chạy headless)."""
            pg.add_style_tag(content=".ant-modal,.ant-modal-mask{opacity:1!important;"
                                     "transform:none!important;animation:none!important}")
            pg.click('button:has-text("Gửi yêu cầu hỗ trợ")')
            pg.wait_for_selector(".ant-modal", timeout=8000)
            pg.wait_for_timeout(500)

        # ── Phần 1: hộp thư với Tập đoàn ─────────────────────────────────────────────────────
        shot(f"{WEB}/ho-tro", MENU, "01-menu.png", wait_for=".ant-menu")
        shot(f"{WEB}/ho-tro", INBOX, "02-hop-thu.png", wait_for=".sp-item")
        shot(f"{WEB}/ho-tro/{ids['announce']}", THREAD, "03-nhan-thong-bao.png",
             wait_for=".sp-msg")
        shot(f"{WEB}/ho-tro", COMPOSER, "04-gui-yeu-cau.png", wait_for=".sp-item",
             setup=open_composer)
        shot(f"{WEB}/ho-tro/{ids['request']}", THREAD, "05-tap-doan-tra-loi.png",
             wait_for=".sp-msg")
        shot(f"{WEB}/ho-tro/{ids['closed']}", CLOSED, "06-the-da-dong.png", wait_for=".sp-compose")
        shot(f"{WEB}/ho-tro/{ids['reminder']}", THREAD, "07-nhac-lich.png",
             wait_for=".sp-msg")

        # ── Phần 2: xem số liệu của đơn vị ───────────────────────────────────────────────────
        shot(f"{WEB}/bao-cao-thu-mua", READONLY, "08-thu-mua.png", wait_for=".ant-table",
             wide=True)
        shot(f"{WEB}/bao-cao-ton-kho", READONLY, "09-ton-kho.png", wait_for=".ant-table",
             wide=True)
        shot(f"{WEB}/nhu-cau-thi-truong", DEMAND, "10-nhu-cau-thi-truong.png",
             wait_for=".ant-table-tbody tr.ant-table-row", wide=True)
        shot(f"{WEB}/ke-hoach-nam", PLAN, "11-ke-hoach-nam.png", wait_for="table",
             wide=True)
        shot(f"{WEB}/hop-dong/khach-hang", LIST_ONLY, "12-khach-hang.png", wait_for="table",
             wide=True)
        shot(f"{WEB}/hop-dong/hop-dong-me", LIST_ONLY, "13-hop-dong-me.png", wait_for="table",
             wide=True)
        shot(f"{WEB}/hop-dong", LIST_ONLY, "14-hop-dong-dot-giao.png", wait_for="table",
             wide=True)
        shot(f"{WEB}/bao-cao-tieu-thu", CONSUMPTION, "15-bao-cao-tieu-thu.png",
             wait_for="table", wide=True)
        shot(f"{WEB}/ho-so", PROFILE, "16-ho-so.png", wait_for=".ant-card")

        # ── Cảnh báo bất thường: ghi 2 lỗi mẫu SAU CÙNG để không lọt vào các ảnh số liệu ở trên ──
        if not only or "17-canh-bao-bat-thuong.png".startswith(only):
            S.seed_anomalies(member, unit)
            shot(f"{WEB}/canh-bao-bat-thuong", ANOMALY, "17-canh-bao-bat-thuong.png",
                 wait_for=".kpi-row", wide=True)

    if not only:
        S.clean(unit)
        print("Đã xoá sạch dữ liệu mẫu.")
    else:
        print("⚠ Giữ nguyên dữ liệu mẫu (chụp một phần) — chạy lại đủ bộ để dọn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
