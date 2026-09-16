#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH sổ tay "Duyệt đề nghị sửa số liệu" — bản cho CHUYÊN VIÊN BAN.

Chạy (API 8390 + Web 5390 phải đang chạy):
    cd apps/api && uv run --with playwright python \
        ../../docs/huong-dan/duyet-de-nghi-sua/shoot.py
    (chụp lại vài ảnh: thêm tiền tố tên file, vd `… shoot.py 03 04`)

Kịch bản: tạo đợt chốt + gửi một đề nghị thật từ đơn vị Tây Ninh → chụp toàn bộ màn duyệt →
xoá sạch dữ liệu mẫu. Dùng chung `seed.py` của sổ tay đơn vị (một nguồn, khỏi lệch).
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "de-nghi-sua-so-lieu"))          # seed.py dùng chung
sys.path.insert(0, str(pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts"))

import seed as S  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from shoot import annotated_shot  # noqa: E402  (helper của skill screenshot-annotate)

OUT = HERE / "img"
ROW = "tbody tr:not(.ant-table-measure-row)"
NORMAL = {"width": 1500, "height": 880}
#: Trang chi tiết dài hơn một màn 880 một chút — nới vừa đủ, không để thừa khoảng trắng.
DETAIL = {"width": 1500, "height": 940}

# ── Mô tả phần tử cần khoanh cho từng ảnh ──────────────────────────────────────────────────────
CAP_FIELD = """(() => {
  // Trang này dựng sẵn CẢ hộp đổi mật khẩu (đang ẩn) → lấy hộp đang hiện, không lấy hộp cuối.
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const all = [...m.querySelectorAll('*')].filter(e => e.textContent.includes('Duyệt đề nghị sửa số liệu của đơn vị'));
  const row = all.reverse().find(e => e.querySelector('.ant-segmented'));
  return window.__annotate([row, row && row.querySelector('.ant-segmented')]);
})()"""

MENU = """(() => {
  const it = [...document.querySelectorAll('.ant-menu-item')]
      .find(e => e.textContent.includes('Duyệt đề nghị sửa'));
  return window.__annotate([it]);
})()"""

LIST = """(() => {
  const selects = [...document.querySelectorAll('.sp-row .ant-select')];
  const row = document.querySelector('tbody tr:not(.ant-table-measure-row)');
  return window.__annotate([document.querySelector('.ant-segmented'), selects[0], selects[1],
                            document.querySelector('.ant-input-search'), row]);
})()"""

INFO = """(() => {
  const dts = [...document.querySelectorAll('.er-info dt')];
  const dd = (t) => { const d = dts.find(x => x.textContent.trim() === t); return d && d.nextElementSibling; };
  return window.__annotate([document.querySelector('.er-page .card'),
                            dd('Lý do chỉnh sửa'), dd('Vì sao không tự sửa')]);
})()"""

DIFF = """(() => {
  const head = [...document.querySelectorAll('th')];
  const col = (t) => head.find(h => h.textContent.trim() === t);
  // Ô "sẽ đổi" được tô vàng bằng style nội tuyến → dò theo màu nền thật, không dò chuỗi style.
  const cells = [...document.querySelectorAll('tbody td')]
      .filter(td => getComputedStyle(td).backgroundColor === 'rgb(254, 243, 199)');
  return window.__annotate([col('Lúc gửi'), col('Hiện tại'), col('Đề nghị'), cells.pop()]);
})()"""

LOCK_BLOCK = """(() => {
  const h = [...document.querySelectorAll('h3')].find(e => e.textContent.includes('Ảnh hưởng chốt'));
  const card = h && h.closest('.card');
  const note = card && card.querySelector('.form-note');
  return window.__annotate([card, note]);
})()"""

APPROVE_POPUP = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const note = m.querySelector('.form-note');
  const ta = m.querySelector('textarea');
  const ok = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Duyệt và ghi số liệu'));
  return window.__annotate([note, ta, ok]);
})()"""

REJECT_POPUP = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const ta = m.querySelector('textarea');
  const ok = [...m.querySelectorAll('button')].find(b => b.textContent.trim() === 'Từ chối');
  return window.__annotate([m.querySelector('.form-note'), ta, ok]);
})()"""

CHANGED = """(() => {
  const al = [...document.querySelectorAll('.ant-alert')]
      .find(a => a.textContent.includes('Số liệu đã thay đổi'));
  const reload = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Tải lại'));
  const head = [...document.querySelectorAll('th')].find(t => t.textContent.trim().toUpperCase() === 'HIỆN TẠI');
  return window.__annotate([al, reload, head]);
})()"""

OVERWRITE = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const cb = m.querySelector('.ant-checkbox-wrapper');
  const ok = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Duyệt và ghi số liệu'));
  return window.__annotate([m.querySelector('.form-note'), cb, ok]);
})()"""

DONE = """(() => {
  const tag = [...document.querySelectorAll('.ant-tag')].find(t => t.textContent.includes('Đã duyệt'));
  const h = [...document.querySelectorAll('h3')].find(e => e.textContent.includes('Nội dung thay đổi'));
  return window.__annotate([tag, h && h.closest('.card')]);
})()"""

AUDIT = """(() => {
  const row = [...document.querySelectorAll('tbody tr:not(.ant-table-measure-row)')]
      .find(t => t.textContent.includes('đề nghị sửa') || t.textContent.includes('Đề nghị sửa'));
  return window.__annotate([document.querySelector('.card'), row]);
})()"""


# ── Thao tác chuẩn bị ──────────────────────────────────────────────────────────────────────────
def send_request(pg) -> int:
    """Đơn vị Tây Ninh gửi một đề nghị sửa biểu Thu mua ngày đã chốt. Trả về mã đề nghị."""
    pg.goto(f"{S.WEB}/bao-cao-thu-mua", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    pg.locator("tbody tr", has_text="20/08/2026").first.locator("button").first.click()
    pg.wait_for_selector(".ant-modal", state="attached")
    pg.wait_for_timeout(700)
    pg.locator(".ant-modal button", has_text="Đề nghị sửa").last.click()
    pg.wait_for_timeout(600)
    ins = pg.locator(".ant-modal input")
    ins.nth(3).fill("12,5")
    ins.nth(4).fill("510")
    pg.locator(".ant-modal-title").first.click()
    pg.locator(".ant-modal button", has_text="Gửi đề nghị sửa").last.click()
    pg.wait_for_selector(".ant-modal textarea")
    pg.wait_for_timeout(400)
    pg.locator(".ant-modal textarea").last.fill(
        "Nhập nhầm sản lượng và đơn giá mủ nước ngày 20/08. Theo phiếu cân, số đúng là 12,5 tấn "
        "quy khô, đơn giá 510 đồng/độ TSC.")
    pg.locator(".ant-modal button", has_text="Gửi đề nghị").last.click()
    pg.wait_for_timeout(2500)
    return S.sql("SELECT max(id) AS m FROM edit_request")[0]["m"]


def open_cap_field(pg):
    """Mở hộp sửa một tài khoản chuyên viên rồi kéo dòng quyền cần chụp vào khung (KHÔNG lưu)."""
    pg.wait_for_timeout(1200)
    pg.locator("tbody tr", has_text="lthphung@vrg.vn").first.locator("button", has_text="Sửa").first.click()
    pg.wait_for_selector(".ant-modal-title", state="visible")
    pg.wait_for_timeout(800)
    pg.evaluate("""(() => {
      const all = [...document.querySelectorAll('.ant-modal *')]
          .filter(e => e.textContent.includes('Duyệt đề nghị sửa số liệu của đơn vị'));
      const row = all.reverse().find(e => e.querySelector('.ant-segmented'));
      if (row) row.scrollIntoView({block: 'center'});
    })()""")
    pg.wait_for_timeout(500)


def click_approve(pg):
    pg.wait_for_timeout(800)
    pg.locator("button", has_text="Duyệt").last.click()
    pg.wait_for_selector(".ant-modal")
    pg.wait_for_timeout(600)


def click_reject(pg):
    pg.wait_for_timeout(800)
    pg.locator("button", has_text="Từ chối").first.click()
    pg.wait_for_selector(".ant-modal")
    pg.wait_for_timeout(600)
    pg.locator(".ant-modal textarea").last.fill(
        "Số trên phiếu cân gửi kèm chưa khớp sổ kho. Đơn vị đối chiếu lại rồi gửi đề nghị mới.")
    pg.wait_for_timeout(300)


def tick_and_show(pg):
    click_approve(pg)
    pg.locator(".ant-modal .ant-checkbox-input").last.check()
    pg.wait_for_timeout(300)


def main() -> int:
    only = tuple(sys.argv[1:])
    OUT.mkdir(exist_ok=True)
    box = S.Sandbox()
    box.lock_rounds()

    def shot(page, url, targets, name, *, wait_for, setup=None, viewport=None):
        if only and not name.startswith(only):
            return

        def prep(pg):
            pg.mouse.move(4, 4)
            if setup:
                setup(pg)

        n = annotated_shot(page, url, targets, str(OUT / name), wait_for=wait_for, setup=prep,
                           viewport=viewport or NORMAL)
        print(f"  {'✓' if n else '✗'} {name} ({n} khung)")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            rid = send_request(S.page_for(browser, "tn"))
            print("  · đề nghị mẫu #", rid)
            ad = S.page_for(browser, "admin")
            detail = f"{S.WEB}/duyet-de-nghi-sua/{rid}"

            shot(ad, f"{S.WEB}/quan-tri/nguoi-dung", CAP_FIELD, "01-cap-quyen-duyet.png",
                 wait_for=ROW, setup=open_cap_field)
            shot(ad, f"{S.WEB}/duyet-de-nghi-sua", MENU, "02-menu-va-so-cho-duyet.png", wait_for=ROW)
            shot(ad, f"{S.WEB}/duyet-de-nghi-sua", LIST, "03-danh-sach-de-nghi.png", wait_for=ROW)
            shot(ad, detail, INFO, "04-chi-tiet-thong-tin.png", wait_for=".er-section", viewport=DETAIL)
            shot(ad, detail, DIFF, "05-bang-noi-dung-thay-doi.png", wait_for=ROW, viewport=DETAIL)
            shot(ad, detail, LOCK_BLOCK, "06-anh-huong-chot-so-lieu.png", wait_for=".er-section",
                 viewport=DETAIL)
            shot(ad, detail, APPROVE_POPUP, "07-popup-duyet.png", wait_for=ROW, setup=click_approve)
            shot(ad, detail, REJECT_POPUP, "08-popup-tu-choi.png", wait_for=ROW, setup=click_reject)

            # Đơn vị/chuyên viên khác vừa đổi số sau khi đề nghị được gửi → trang duyệt cảnh báo.
            box.bump_day_price()
            shot(ad, detail, CHANGED, "09-so-lieu-da-thay-doi.png", wait_for=ROW, viewport=DETAIL)
            shot(ad, detail, OVERWRITE, "10-popup-duyet-ghi-de.png", wait_for=ROW, setup=tick_and_show)

            if not only or any(n.startswith(only) for n in ("11", "12")):
                ad.goto(detail, wait_until="networkidle")
                ad.wait_for_timeout(1500)
                tick_and_show(ad)
                ad.locator(".ant-modal button", has_text="Duyệt và ghi số liệu").last.click()
                ad.wait_for_timeout(2500)
                shot(ad, detail, DONE, "11-sau-khi-duyet.png", wait_for=ROW, viewport=DETAIL)
                shot(ad, f"{S.WEB}/quan-tri/nhat-ky", AUDIT, "12-nhat-ky-hoat-dong.png", wait_for=ROW)
            browser.close()
    finally:
        box.restore()
        S.check_clean()
    return 0


if __name__ == "__main__":
    sys.exit(main())
