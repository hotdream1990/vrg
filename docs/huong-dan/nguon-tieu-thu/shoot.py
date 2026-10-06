#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH sổ tay "Nguồn tiêu thụ theo chủng loại" — bản cho ĐƠN VỊ THÀNH VIÊN.

Chạy (API + Web phải đang chạy, dữ liệu mẫu tạo bằng `seed.py`):
    cd apps/api && uv run python ../../docs/huong-dan/nguon-tieu-thu/seed.py
    cd apps/api && uv run python ../../docs/huong-dan/nguon-tieu-thu/shoot.py
    cd apps/api && uv run python ../../docs/huong-dan/nguon-tieu-thu/seed.py cleanup
`VRG_WEB` / `VRG_API` đổi địa chỉ (mặc định cổng 5390 / 8390). Máy không có chromium riêng của
Playwright → mở Chrome hệ thống (`channel="chrome"`). Đăng nhập bằng token, không qua form.
"""
from __future__ import annotations

import json
import os
import re
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, os.getcwd())

import seed as S  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

WEB = os.environ.get("VRG_WEB", "http://localhost:5390")
OUT = HERE / "img"
ANNOTATE = (pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts/annotate.js").read_text()
# Modal AntD có lúc kẹt ở khung hình mở (opacity 0) trong trình duyệt tự động — ép hiện.
FORCE = ".ant-modal,.ant-modal-mask,.ant-modal-wrap{opacity:1!important;transform:none!important;animation:none!important}"
HELPERS = r"""
window.__modal = (re) => [...document.querySelectorAll('.ant-modal')].filter(m => !re || re.test(m.textContent)).pop();
window.__btn = (root, re) => [...root.querySelectorAll('button')].find(b => re.test(b.textContent));
window.__union = (els) => {
  els = els.filter(Boolean); if (!els.length) return null;
  const rs = els.map(e => e.getBoundingClientRect()), d = document.createElement('div');
  const x = Math.min(...rs.map(r => r.left)), y = Math.min(...rs.map(r => r.top));
  Object.assign(d.style, {position: 'fixed', left: x + 'px', top: y + 'px', pointerEvents: 'none',
    width: Math.max(...rs.map(r => r.right)) - x + 'px', height: Math.max(...rs.map(r => r.bottom)) - y + 'px'});
  document.body.appendChild(d); return d;
};
window.__srcSelects = (root) => [...root.querySelectorAll('select')]
  .filter(s => [...s.options].some(o => /Hàng hóa cao su/.test(o.textContent)));
window.__col = (h) => { const t = h.closest('table'), i = [...h.parentElement.children].indexOf(h);
  return [h, ...[...t.querySelectorAll('tbody tr')].map(r => r.children[i]).filter(Boolean)]; };
"""


def snap(page, name: str, targets: str) -> None:
    page.add_style_tag(content=FORCE)
    page.add_script_tag(content=ANNOTATE)
    page.add_script_tag(content=HELPERS)
    page.wait_for_timeout(300)
    n = page.evaluate(targets)
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / name))
    print(f"{name}: {n} khung")


def open_contract(page, code: str, tab: str | None = None) -> None:
    page.goto(f"{WEB}/hop-dong")
    page.wait_for_timeout(2500)
    page.fill("input[placeholder='Tìm theo số HĐ']", code)
    page.wait_for_timeout(1800)
    page.locator("button", has_text="Xem").last.click()
    page.wait_for_timeout(1800)
    page.add_style_tag(content=FORCE)
    if tab:
        page.locator(".ant-tabs-tab", has_text=tab).first.click()
        page.wait_for_timeout(800)


def batch_form(page) -> None:
    """Mở phiếu Thêm đợt giao của HĐ-MH-03 và điền 2 dòng (dòng 2 CHƯA chọn nguồn)."""
    open_contract(page, "HD-MH-03", "Đợt giao")
    page.locator("button", has_text="Thêm đợt giao").first.click()
    page.wait_for_timeout(1200)
    dlg = page.locator(".ant-modal").last
    dlg.locator("label", has_text="Số đợt giao").locator("input").first.fill("3")
    dlg.locator("input[placeholder='dd/mm/yyyy']").first.fill("06/10/2026")
    dlg.locator("select").filter(has=page.locator("option", has_text="Tiêu thụ trong nước")).first \
        .select_option(label="Tiêu thụ trong nước")
    for i, (grade, qty, price) in enumerate((("SVR 20 / CSR 20", "5", "38"), ("SVR 3L", "8", "42"))):
        if i:
            dlg.locator("button", has_text="Thêm dòng").first.click()
            page.wait_for_timeout(400)
        ln = dlg.locator(".ct-line").nth(i)
        ln.locator("select").nth(0).select_option(label=grade)
        txt = ln.locator("input[type='text']")
        txt.nth(0).fill(qty)
        txt.nth(1).fill(price)
    src = dlg.locator(".ct-line").nth(0).locator("select").filter(
        has=page.locator("option", has_text="Hàng hóa cao su")).first
    src.select_option(value="exploit")
    dlg.locator(".ct-line").nth(1).locator("select").filter(
        has=page.locator("option", has_text="Hàng hóa cao su")).first.select_option(value="")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": 1500, "height": 1000}, device_scale_factor=2,
                                  locale="vi-VN")
        ctx.add_init_script(f"localStorage.setItem('vrg_token', {json.dumps(S.member_token())})")
        page = ctx.new_page()

        # 1. Phiếu đợt giao: nguồn ở TỪNG DÒNG chủng loại
        batch_form(page)
        page.locator(".ant-modal .ct-line").last.locator("select").filter(
            has=page.locator("option", has_text="Hàng hóa cao su")).first.select_option(value="goods")
        page.evaluate("() => document.querySelector('.ant-modal .ct-line').scrollIntoView({block:'center'})")
        snap(page, "01-chon-nguon-tung-dong.png", """(() => {
          const m = __modal(/Thêm đợt giao/);
          const day = m.querySelector("input[placeholder='dd/mm/yyyy']");
          const ch = [...m.querySelectorAll('select')].find(s => [...s.options].some(o => /Tiêu thụ trong nước/.test(o.textContent)));
          const [s1, s2] = __srcSelects(m).map(s => s.closest('label') || s);
          return window.__annotate([day, ch, s1, s2, __btn(m, /Thêm dòng/)]);
        })()""")

        # 2. Thiếu nguồn ở một dòng → hệ thống báo đúng dòng
        batch_form(page)
        page.locator(".ant-modal-footer button.ant-btn-primary").last.click()
        page.wait_for_timeout(800)
        page.evaluate("""() => { const e = [...document.querySelectorAll('.ant-modal *')]
            .filter(x => x.children.length === 0 && /chọn nguồn tiêu thụ\\./.test(x.textContent)).pop();
          (e || document.body).scrollIntoView({block:'center'}); }""")
        snap(page, "02-bao-thieu-nguon.png", """(() => {
          const m = __modal(/Thêm đợt giao/);
          const err = [...m.querySelectorAll('*')].filter(x => /Dòng 2 \\(SVR 3L\\): chọn nguồn tiêu thụ\\./.test(x.textContent)).pop();
          const box = err && (err.closest('.blt-error, .ant-alert, ul, div') || err);
          const s2 = __srcSelects(m)[1];
          return window.__annotate([s2 && (s2.closest('label') || s2), box]);
        })()""")

        # 3. Mở hợp đồng giao nhiều lần → tab Đợt giao → nút Sửa nguồn
        open_contract(page, "HD-MH-03", "Đợt giao")
        snap(page, "03-nut-sua-nguon.png", """(() => {
          const m = __modal(/HD-MH-03/);
          const tab = [...m.querySelectorAll('.ant-tabs-tab')].find(t => /Đợt giao/.test(t.textContent));
          const h = [...m.querySelectorAll('th')].find(e => e.textContent.trim() === 'Nguồn');
          return window.__annotate([tab, __btn(m, /Sửa nguồn/), h && __union(__col(h))]);
        })()""")

        # 4. Hộp Sửa nguồn — chọn theo từng dòng
        page.locator(".ant-modal button", has_text="Sửa nguồn").first.click()
        page.wait_for_timeout(1000)
        snap(page, "04-hop-sua-nguon.png", """(() => {
          const m = __modal(/Sửa nguồn tiêu thụ/);
          const quick = [...m.querySelectorAll('label')].find(l => /Chọn nhanh/.test(l.textContent));
          const rows = [...m.querySelectorAll('label')].filter(l => /^Dòng \\d/.test(l.textContent.trim()));
          return window.__annotate([quick, __union(rows), __btn(m, /^\\s*Lưu\\s*$/)]);
        })()""")

        # 5. Hoàn thành hợp đồng giao 1 lần chưa có ngày giao
        open_contract(page, "HD-MH-05")
        page.locator(".ant-modal button", has_text="Hoàn thành hợp đồng").first.click()
        page.wait_for_timeout(1000)
        dlg = page.locator(".ant-modal", has_text="Hoàn thành hợp đồng HD-MH-05").last
        dlg.locator("select").filter(has=page.locator("option", has_text="Tiêu thụ trong nước")).first \
            .select_option(label="Tiêu thụ trong nước")
        # Chỉ các ô "Dòng N" — ô "Chọn nhanh cho tất cả dòng" cũng chứa chữ "dòng", lọc theo đầu câu.
        srcs = dlg.locator("label").filter(has_text=re.compile(r"^Dòng \d")).locator("select")
        srcs.nth(0).select_option(value="exploit")
        srcs.nth(1).select_option(value="goods")
        snap(page, "05-hoan-thanh-chon-nguon.png", """(() => {
          const m = __modal(/Hoàn thành hợp đồng HD-MH-05/);
          const ch = [...m.querySelectorAll('select')].find(s => [...s.options].some(o => /Tiêu thụ trong nước/.test(o.textContent)));
          const rows = [...m.querySelectorAll('label')].filter(l => /Chọn nhanh|^Dòng \\d/.test(l.textContent.trim()));
          return window.__annotate([ch && (ch.closest('label') || ch), __union(rows), __btn(m, /^\\s*Hoàn thành\\s*$/)]);
        })()""")

        # 6. Dashboard đơn vị — tỷ trọng nguồn + bảng cơ cấu nguồn theo chủng loại
        page.goto(f"{WEB}/dashboard-don-vi")
        page.wait_for_timeout(3500)
        page.evaluate("""() => { const t = [...document.querySelectorAll('.ud-mini-title')]
            .find(e => /Cơ cấu nguồn/.test(e.textContent)); t.scrollIntoView({block:'center'}); scrollBy(0, 110); }""")
        snap(page, "06-dashboard-co-cau-nguon.png", """(() => {
          const ratio = [...document.querySelectorAll('p, div, span')].filter(e => /Tỷ trọng nguồn:/.test(e.textContent)).pop();
          const t = [...document.querySelectorAll('.ud-mini-title')].find(e => /Cơ cấu nguồn/.test(e.textContent));
          return window.__annotate([ratio, t && t.closest('.ud-table-wrap')]);
        })()""")

        # 7. Báo cáo ▸ Tiêu thụ — 3 cột nguồn + bảng nguồn × chủng loại
        page.goto(f"{WEB}/bao-cao-tieu-thu")
        page.wait_for_timeout(3500)
        page.evaluate("""() => { const th = [...document.querySelectorAll('th')].find(e => /^Nguồn khai thác/i.test(e.textContent.trim()));
            th.scrollIntoView({block:'start'}); scrollBy(0, -60); }""")
        snap(page, "07-bao-cao-nguon-chung-loai.png", """(() => {
          const first = [...document.querySelectorAll('th')].find(e => /^Nguồn khai thác/i.test(e.textContent.trim()));
          const t = first.closest('table');
          const ths = [...t.querySelectorAll('th')].filter(e => /^Nguồn (khai thác|thu mua|hàng hóa)/i.test(e.textContent.trim()));
          const cells = ths.flatMap(h => { const i = [...h.parentElement.children].indexOf(h);
            return [...t.querySelectorAll('tbody tr, tfoot tr')].map(r => r.children[i]); });
          const title = [...document.querySelectorAll('div, span, b, strong')].find(e => e.textContent.trim() === 'Tiêu thụ theo nguồn × chủng loại');
          const matrix = title && (title.closest('.blt-toolbar')?.nextElementSibling || title);
          return window.__annotate([__union([...ths, ...cells]), __union([title, matrix])]);
        })()""")
        browser.close()


if __name__ == "__main__":
    main()
