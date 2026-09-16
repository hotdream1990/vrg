#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH sổ tay "Đề nghị sửa số liệu" — bản cho ĐƠN VỊ THÀNH VIÊN.

Chạy (API 8390 + Web 5390 phải đang chạy):
    cd apps/api && uv run --with playwright python \
        ../../docs/huong-dan/de-nghi-sua-so-lieu/shoot.py
    (chụp lại vài ảnh: thêm tiền tố tên file, vd `… shoot.py 05 06`)

Máy không có chromium riêng của Playwright → mở Chrome hệ thống (`channel="chrome"`).
Dữ liệu mẫu (đợt chốt, đề nghị) được xoá sạch ở cuối — xem `seed.py`.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts"))

import seed as S  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from shoot import annotated_shot  # noqa: E402  (helper của skill screenshot-annotate)

OUT = HERE / "img"
#: Bảng AntD có dòng đo ẩn ở đầu tbody — chờ nó là chờ mãi.
ROW = "tbody tr:not(.ant-table-measure-row)"
WIDE = {"width": 1900, "height": 880}
NORMAL = {"width": 1500, "height": 880}
#: Phiếu nhập ngày rất dài — phải nới cao mới thấy nút lưu ở chân form trong cùng một ảnh.
TALL = {"width": 1500, "height": 1260}

# ── Mô tả phần tử cần khoanh cho từng ảnh (IIFE, trả về window.__annotate) ──────────────────────
LOCKED_DAY = """(() => {
  const lock = [...document.querySelectorAll('.dsn')].find(d => d.textContent.includes('Đã chốt số liệu'));
  const row = [...document.querySelectorAll('tbody tr')].find(t => t.textContent.includes('20/08/2026'));
  const menu = [...document.querySelectorAll('.ant-menu-item')]
      .find(e => e.textContent.trim() === 'Đề nghị sửa số liệu');
  return window.__annotate([lock, row && row.querySelector('button'), menu]);
})()"""

OPEN_DAY = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const btn = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Đề nghị sửa'));
  const msg = m.querySelector('.ant-alert-section')   // AntD mới: phần chữ của Alert;
  return window.__annotate([m.querySelector('input'), msg, btn]);
})()"""

REQUEST_FORM = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const ins = m.querySelectorAll('input');
  const send = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Gửi đề nghị sửa'));
  return window.__annotate([m.querySelector('.ant-alert-warning'), ins[3], ins[4], send]);
})()"""

REASON_POPUP = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const ok = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Gửi đề nghị'));
  return window.__annotate([m.querySelector('textarea'),
                            [...m.querySelectorAll('.form-note')].pop(), ok]);
})()"""

ROW_BUTTONS = """(() => {
  const row = [...document.querySelectorAll('tbody tr')].find(t => t.textContent.includes('20/08/2026'));
  const bs = row.querySelectorAll('button');
  return window.__annotate([bs[0], bs[1]]);
})()"""

MOVE_MODAL = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const send = [...m.querySelectorAll('button')].find(b => b.textContent.includes('Gửi đề nghị sửa'));
  return window.__annotate([m.querySelector('input'), m.querySelector('.ant-alert'), send]);
})()"""

DEMAND_ROW = """(() => {
  // Dải nhắc "Còn thiếu … việc" cũng chứa chữ "Đề nghị sửa" → so khớp CẢ nhãn nút, không dùng includes.
  const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Đề nghị sửa');
  return window.__annotate([btn && btn.closest('.card'), btn]);
})()"""

CONTRACT_ROW = """(() => {
  const tr = [...document.querySelectorAll('tbody tr')].find(t => t.textContent.includes('(chỉ xem)'));
  const bs = [...tr.querySelectorAll('button')];
  const only = [...tr.querySelectorAll('span')].find(s => s.textContent.trim() === '(chỉ xem)');
  return window.__annotate([only,
                            bs.find(b => b.textContent.includes('Đề nghị sửa')),
                            bs.find(b => b.textContent.includes('Đề nghị xoá'))]);
})()"""

CONTRACT_DONE = """(() => {
  const m = [...document.querySelectorAll('.ant-modal')].filter(x => x.getBoundingClientRect().width).pop();
  const bs = [...m.querySelectorAll('button')];
  const kpi = [...m.querySelectorAll('.kpi')].find(k => k.textContent.trim().startsWith('Trạng thái'));
  return window.__annotate([kpi,
                            bs.find(b => b.textContent.includes('Mở lại hợp đồng'))]);
})()"""

MY_LIST = """(() => {
  const th = [...document.querySelectorAll('th')].find(t => t.textContent.includes('Ghi chú của Ban'));
  const cancel = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Huỷ đề nghị');
  return window.__annotate([document.querySelector('.ant-segmented'), th, cancel]);
})()"""

AFTER_APPROVE = """(() => {
  const banner = [...document.querySelectorAll('.dsn')].find(d => d.textContent.includes('Yêu cầu chốt số liệu'));
  const tag = [...document.querySelectorAll('.ant-tag')].find(t => t.textContent.includes('Đã duyệt'));
  return window.__annotate([banner, tag, document.querySelector('tbody .form-note')]);
})()"""

CHIPS = """(() => {
  const dsn = [...document.querySelectorAll('.dsn')].find(d => d.textContent.includes('Còn thiếu'));
  const chips = [...dsn.querySelectorAll('.chip')];
  // Lấy ô CAM cuối cùng và ô XÁM đầu tiên — hai ô cạnh nhau nên mũi tên ngắn, dễ đọc.
  const warn = chips.filter(c => c.classList.contains('warn')).pop();
  const grey = chips.find(c => !c.classList.contains('warn'));
  return window.__annotate([warn, grey]);
})()"""


# ── Thao tác chuẩn bị từng ảnh ─────────────────────────────────────────────────────────────────
def open_day(pg):
    """Mở phiếu ngày 20/08 (ngày đã chốt) từ bảng."""
    pg.locator("tbody tr", has_text="20/08/2026").first.locator("button").first.click()
    pg.wait_for_selector(".ant-modal", state="attached")
    pg.wait_for_timeout(700)


def to_request_mode(pg):
    open_day(pg)
    pg.locator(".ant-modal button", has_text="Đề nghị sửa").last.click()
    pg.wait_for_timeout(600)
    ins = pg.locator(".ant-modal input")
    ins.nth(3).fill("12,5")
    ins.nth(4).fill("510")
    pg.locator(".ant-modal-title").first.click()      # rời ô nhập để số được ghi nhận
    pg.wait_for_timeout(400)


def to_reason_popup(pg):
    to_request_mode(pg)
    pg.locator(".ant-modal button", has_text="Gửi đề nghị sửa").last.click()
    pg.wait_for_selector(".ant-modal textarea")
    pg.wait_for_timeout(500)
    pg.locator(".ant-modal textarea").last.fill(
        "Nhập nhầm sản lượng và đơn giá mủ nước ngày 20/08. Theo phiếu cân, số đúng là 12,5 tấn "
        "quy khô, đơn giá 510 đồng/độ TSC.")
    pg.wait_for_timeout(300)


def open_move(pg):
    pg.locator("tbody tr", has_text="20/08/2026").first.locator("button").nth(1).click()
    pg.wait_for_selector(".ant-modal", state="attached")
    pg.wait_for_timeout(500)
    pg.locator(".ant-modal input").first.fill("21/08/2026")
    pg.locator(".ant-modal input").first.blur()
    pg.wait_for_timeout(500)


def find_contract(pg):
    """Lọc còn 2 hợp đồng của phụ lục Annex 08-26 rồi kéo dòng “(chỉ xem)” vào khung nhìn.

    Phải CHỜ danh sách nạp xong mới gõ: gõ sớm thì lượt tải đầu tiên về sau sẽ xoá ô tìm.
    """
    pg.wait_for_timeout(1500)
    pg.get_by_placeholder("Tìm theo số HĐ").first.fill("Annex 08-26")
    pg.wait_for_selector("text=2 hợp đồng", timeout=10000)
    pg.wait_for_timeout(800)
    pg.evaluate("""(() => {
      const tr = [...document.querySelectorAll('tbody tr')].find(t => t.textContent.includes('(chỉ xem)'));
      if (tr) { tr.scrollIntoView({block: 'center'}); }
    })()""")
    pg.wait_for_timeout(400)


def open_completed_contract(pg):
    find_contract(pg)
    pg.locator("tbody tr", has_text="Hoàn thành").first.locator("button", has_text="Xem").first.click()
    pg.wait_for_selector(".ant-modal", state="attached")
    pg.wait_for_timeout(900)


def main() -> int:
    only = tuple(sys.argv[1:])
    OUT.mkdir(exist_ok=True)
    box = S.Sandbox()
    box.lock_rounds()

    def shot(page, url, targets, name, *, wait_for, setup=None, viewport=None):
        if only and not name.startswith(only):
            return
        def prep(pg):
            pg.mouse.move(4, 4)      # chuột còn đọng ở ảnh trước → tooltip lọt vào ảnh sau
            if setup:
                setup(pg)

        n = annotated_shot(page, url, targets, str(OUT / name), wait_for=wait_for, setup=prep,
                           viewport=viewport or NORMAL)
        print(f"  {'✓' if n else '✗'} {name} ({n} khung)")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            tn = S.page_for(browser, "tn")
            purchase = f"{S.WEB}/bao-cao-thu-mua"

            shot(tn, purchase, LOCKED_DAY, "01-dau-hieu-ngay-bi-khoa.png", wait_for=ROW)
            shot(tn, purchase, OPEN_DAY, "02-mo-ngay-cu.png", wait_for=ROW, setup=open_day)
            shot(tn, purchase, REQUEST_FORM, "03-form-de-nghi-sua.png", wait_for=ROW,
                 setup=to_request_mode, viewport=TALL)
            shot(tn, purchase, REASON_POPUP, "04-popup-ly-do.png", wait_for=ROW,
                 setup=to_reason_popup)
            shot(tn, purchase, ROW_BUTTONS, "05-nut-tren-dong.png", wait_for=ROW)
            shot(tn, purchase, MOVE_MODAL, "06-de-nghi-doi-ngay.png", wait_for=ROW,
                 setup=open_move)
            shot(tn, purchase, CHIPS, "07-o-cam-o-xam.png", wait_for=".dsn")

            dp = S.page_for(browser, "dp")
            shot(dp, f"{S.WEB}/nhu-cau-thi-truong", DEMAND_ROW, "08-nhu-cau-thi-truong.png",
                 wait_for=".card")

            brk = S.page_for(browser, "brk", 1900, 880)
            shot(brk, f"{S.WEB}/hop-dong", CONTRACT_ROW, "09-hop-dong-dot-giao.png",
                 wait_for=ROW, setup=find_contract, viewport=WIDE)
            shot(brk, f"{S.WEB}/hop-dong", CONTRACT_DONE, "10-hop-dong-hoan-thanh.png",
                 wait_for=ROW, setup=open_completed_contract, viewport=WIDE)

            # Hai ảnh cuối cần một đề nghị CÓ THẬT → gửi rồi mượn tài khoản quản trị duyệt.
            if only and not any(n.startswith(only) for n in ("11", "12")):
                browser.close()
                return 0
            tn.goto(purchase, wait_until="networkidle")
            tn.wait_for_timeout(1200)
            to_reason_popup(tn)
            tn.locator(".ant-modal button", has_text="Gửi đề nghị").last.click()
            tn.wait_for_timeout(2000)
            shot(tn, f"{S.WEB}/de-nghi-sua", MY_LIST, "11-theo-doi-de-nghi.png", wait_for=ROW)

            ad = S.page_for(browser, "admin")
            ad.goto(f"{S.WEB}/duyet-de-nghi-sua", wait_until="networkidle")
            ad.wait_for_timeout(1500)
            ad.locator("tbody tr", has_text="20/08/2026").first.click()
            ad.wait_for_timeout(2000)
            ad.locator("button", has_text="Duyệt").last.click()
            ad.wait_for_selector(".ant-modal")
            ad.wait_for_timeout(600)
            ad.locator(".ant-modal button", has_text="Duyệt và ghi số liệu").last.click()
            ad.wait_for_timeout(2500)

            shot(tn, f"{S.WEB}/de-nghi-sua", AFTER_APPROVE, "12-sau-khi-ban-duyet.png",
                 wait_for=ROW)
            browser.close()
    finally:
        box.restore()
        S.check_clean()
    return 0


if __name__ == "__main__":
    sys.exit(main())
