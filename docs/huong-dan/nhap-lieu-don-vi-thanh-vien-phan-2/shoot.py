#!/usr/bin/env python3
"""Dựng lại BỘ ẢNH sổ tay "Nhập liệu đơn vị thành viên — Phần 2" (đặt cọc · chỉ thị giao hàng · chứng từ).

Chạy (API + Web phải đang chạy, dữ liệu mẫu tạo bằng `seed.py`):
    cd apps/api && uv run python ../../docs/huong-dan/nhap-lieu-don-vi-thanh-vien-phan-2/seed.py
    cd apps/api && uv run python ../../docs/huong-dan/nhap-lieu-don-vi-thanh-vien-phan-2/shoot.py
    cd apps/api && uv run python ../../docs/huong-dan/nhap-lieu-don-vi-thanh-vien-phan-2/seed.py cleanup
`VRG_WEB` / `VRG_API` đổi địa chỉ (mặc định cổng 5390 / 8390). Đăng nhập bằng token, không qua form.
Mỗi ảnh CẮT đúng vùng cần xem (không chụp cả màn hình) để ảnh trong sổ tay đọc được chữ.
"""
from __future__ import annotations

import json
import os
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
window.__h4 = (root, re) => [...root.querySelectorAll('h4')].find(h => re.test(h.textContent));
window.__label = (root, re) => [...root.querySelectorAll('label')].find(l => re.test(l.textContent.trim()));
window.__attach = (root, text) => [...root.querySelectorAll('div')].find(d => d.textContent === text)?.parentElement;
window.__note = (root, re) => [...root.querySelectorAll('p.form-note, div.blt-error')].find(p => re.test(p.textContent));
window.__union = (els) => {
  els = els.filter(Boolean); if (!els.length) return null;
  const rs = els.map(e => e.getBoundingClientRect()), d = document.createElement('div');
  const x = Math.min(...rs.map(r => r.left)), y = Math.min(...rs.map(r => r.top));
  Object.assign(d.style, {position: 'fixed', left: x + 'px', top: y + 'px', pointerEvents: 'none',
    width: Math.max(...rs.map(r => r.right)) - x + 'px', height: Math.max(...rs.map(r => r.bottom)) - y + 'px'});
  document.body.appendChild(d); return d;
};
// Vùng cắt ảnh = bao các phần tử, nới `pad`, kẹp trong khung nhìn (overlay chú thích là position:fixed).
window.__clip = (els, pad = 28) => {
  const rs = els.filter(Boolean).map(e => e.getBoundingClientRect());
  const x = Math.max(0, Math.min(...rs.map(r => r.left)) - pad), y = Math.max(0, Math.min(...rs.map(r => r.top)) - pad);
  const r = Math.min(innerWidth, Math.max(...rs.map(r => r.right)) + pad);
  const b = Math.min(innerHeight, Math.max(...rs.map(r => r.bottom)) + pad);
  return {x, y, width: r - x, height: b - y};
};
"""


def prep(page) -> None:
    page.add_style_tag(content=FORCE)
    page.add_script_tag(content=ANNOTATE)
    page.add_script_tag(content=HELPERS)
    page.wait_for_timeout(300)


def snap(page, name: str, targets: str, clip: str) -> None:
    """`targets` = IIFE gọi window.__annotate; `clip` = biểu thức JS trả về vùng cắt."""
    prep(page)
    n = page.evaluate(targets)
    # Mũi tên nối các khung cạnh nhau vắt qua nút/ô không đánh số → rối ảnh; sổ tay chỉ cần số.
    page.evaluate("() => document.querySelectorAll('#anno-overlay path').forEach(p => p.remove())")
    page.wait_for_timeout(300)
    page.screenshot(path=str(OUT / name), clip=page.evaluate(clip))
    print(f"{name}: {n} khung")


def scroll_to(page, js: str) -> None:
    page.evaluate(f"() => {{ const e = ({js}); e && e.scrollIntoView({{block: 'center'}}); }}")
    page.wait_for_timeout(500)


def list_contracts(page, q: str) -> None:
    page.goto(f"{WEB}/hop-dong")
    page.wait_for_timeout(2500)
    page.fill("input[placeholder='Tìm theo số HĐ']", q)
    page.wait_for_timeout(1800)


def edit_form(page, code: str) -> None:
    list_contracts(page, code)
    page.locator("tr", has_text=code).locator("button", has_text="Sửa").first.click()
    page.wait_for_timeout(1500)
    prep(page)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1500, "height": 1000}, device_scale_factor=2,
                                  locale="vi-VN")
        ctx.add_init_script(f"localStorage.setItem('vrg_token', {json.dumps(S.member_token())})")
        page = ctx.new_page()

        # 1. Phiếu Thêm hợp đồng — Ngày ký theo bản scan + dòng nhắc
        list_contracts(page, "")
        page.locator("button", has_text="Thêm hợp đồng").first.click()
        page.wait_for_timeout(1500)
        snap(page, "01-ngay-ky-theo-scan.png", """(() => {
          const m = __modal(/Thêm hợp đồng/);
          return window.__annotate([__label(m, /^Ngày ký \\(theo bản scan\\)/), __note(m, /^Ngày ký là ngày ký/)]);
        })()""", """(() => { const m = __modal(/Thêm hợp đồng/);
          return __clip([m.querySelector('.ant-modal-title'), __note(m, /^Ngày ký là ngày ký/)], 14); })()""")

        # 2. Đặt cọc nhiều đợt
        edit_form(page, "HD-MH-21")
        scroll_to(page, "__h4(__modal(/Sửa hợp đồng/), /^Đặt cọc/)")
        deposit_targets = """(() => {
          const m = __modal(/Sửa hợp đồng/), h = __h4(m, /^Đặt cọc/);
          return window.__annotate([h.nextElementSibling, __btn(m, /Thêm đợt cọc/),
                                    __note(m, /Mỗi lần nhận cọc|Tổng tiền cọc/)]);
        })()"""
        deposit_clip = """(() => { const m = __modal(/Sửa hợp đồng/);
          return __clip([__h4(m, /^Đặt cọc/), __note(m, /Mỗi lần nhận cọc|Tổng tiền cọc/)]); })()"""
        snap(page, "02-dat-coc-nhieu-dot.png", deposit_targets, deposit_clip)

        # 3. Gõ nhầm đồng vào ô triệu đồng → báo đỏ, không lưu được
        amount2 = page.locator(".ant-modal label", has_text="Số tiền cọc").nth(1).locator("input")
        amount2.fill("400000000")
        amount2.blur()
        page.wait_for_timeout(500)
        snap(page, "03-coc-vuot-gia-tri.png", """(() => {
          const m = __modal(/Sửa hợp đồng/);
          const amt = [...m.querySelectorAll('label')].filter(l => /^Số tiền cọc/.test(l.textContent.trim()))[1];
          return window.__annotate([amt, __note(m, /Tổng tiền cọc .* lớn hơn/)]);
        })()""", """(() => { const m = __modal(/Sửa hợp đồng/);
          return __clip([__h4(m, /^Đặt cọc/), __note(m, /Tổng tiền cọc .* lớn hơn/)]); })()""")

        # 4. Chỉ thị giao hàng
        edit_form(page, "HD-MH-21")
        scroll_to(page, "__h4(__modal(/Sửa hợp đồng/), /^Chỉ thị giao hàng/)")
        snap(page, "04-chi-thi-giao-hang.png", """(() => {
          const m = __modal(/Sửa hợp đồng/);
          return window.__annotate([__label(m, /^Thời gian giao/), __label(m, /^Địa điểm giao/),
                                    __attach(m, 'Chỉ thị giao hàng (scan)')]);
        })()""", """(() => { const m = __modal(/Sửa hợp đồng/), h = __h4(m, /^Chỉ thị giao hàng/);
          return __clip([h, h.nextElementSibling]); })()""")

        # 5. Thanh toán + scan hợp đồng + Lưu
        scroll_to(page, "__btn(__modal(/Sửa hợp đồng/), /^\\s*Lưu\\s*$/)")
        snap(page, "05-thanh-toan-scan-hd.png", """(() => {
          const m = __modal(/Sửa hợp đồng/);
          return window.__annotate([__attach(m, 'Chứng từ thanh toán'), __attach(m, 'Hợp đồng đã ký (scan)'),
                                    __btn(m, /^\\s*Lưu\\s*$/)]);
        })()""", """(() => { const m = __modal(/Sửa hợp đồng/);
          return __clip([__h4(m, /^Thanh toán/), m.querySelector('.ant-modal-footer')]); })()""")

        # 6. Danh sách — cột Chứng từ, tìm hợp đồng còn thiếu
        page.set_viewport_size({"width": 2100, "height": 900})
        list_contracts(page, "HD-MH-2")
        snap(page, "06-danh-sach-cot-chung-tu.png", """(() => {
          const th = [...document.querySelectorAll('table thead th')].find(t => t.textContent.trim() === 'Chứng từ');
          const i = [...th.parentElement.children].indexOf(th);
          const row = [...document.querySelectorAll('table tbody tr')].find(r => r.textContent.includes('HD-MH-22'));
          return window.__annotate([row.children[i].firstElementChild, __btn(row, /^\\s*Sửa\\s*$/)]);
        })()""", """(() => __clip([document.querySelector('.card.table-scroll')], 12))()""")

        # 7. Màn chi tiết — xem lại cọc, chỉ thị, thanh toán
        page.set_viewport_size({"width": 1500, "height": 1000})
        list_contracts(page, "HD-MH-21")
        page.locator("tr", has_text="HD-MH-21").locator("button", has_text="Xem").first.click()
        page.wait_for_timeout(1800)
        prep(page)
        scroll_to(page, "[...document.querySelectorAll('.ant-modal div')].find(d => d.textContent === 'Đặt cọc')")
        snap(page, "07-chi-tiet-hop-dong.png", """(() => {
          const lbl = t => [...document.querySelectorAll('.ant-modal div')].find(d => d.textContent === t && d.style.color)?.parentElement;
          return window.__annotate([lbl('Đặt cọc'), lbl('Chỉ thị giao hàng'), lbl('Thanh toán')]);
        })()""", """(() => { const lbl = t => [...document.querySelectorAll('.ant-modal div')].find(d => d.textContent === t && d.style.color)?.parentElement;
          const m = __modal(/HD-MH-21/);
          return __clip([m.querySelector('.ant-modal-title'), lbl('Hợp đồng đã ký (scan)'), lbl('Thanh toán'), lbl('Đặt cọc')], 14); })()""")
        # 14. Kế hoạch năm — rà chỉ tiêu trước khi chốt
        page.goto(f"{WEB}/ke-hoach-nam")
        page.wait_for_timeout(2500)
        snap(page, "14-ke-hoach-nam.png", """(() => {
          const row = [...document.querySelectorAll('table tbody tr')].find(r => r.textContent.includes('Minh Hoạ'));
          const note = [...document.querySelectorAll('p.form-note')].find(p => /Kế hoạch bán hàng/.test(p.textContent));
          return window.__annotate([row, note]);
        })()""", """(() => { const row = [...document.querySelectorAll('table tbody tr')].find(r => r.textContent.includes('Minh Hoạ'));
          const note = [...document.querySelectorAll('p.form-note')].find(p => /Kế hoạch bán hàng/.test(p.textContent));
          return __clip([note, row.closest('table')], 16); })()""")

        # 15. Hàng đỏ "Yêu cầu chốt số liệu" ở đầu màn hình
        snap(page, "15-yeu-cau-chot.png", """(() => {
          const b = document.querySelector('.dsn.dsn-manual');
          return window.__annotate([__btn(b, /Xem số liệu/)]);
        })()""", """(() => __clip([document.querySelector('.dsn.dsn-manual')], 14))()""")

        # 16. Bảng xác nhận chốt — khối Kế hoạch năm (chốt cùng đợt) + nút xác nhận
        page.locator(".dsn.dsn-manual button", has_text="Xem số liệu").first.click()
        page.wait_for_timeout(2500)
        prep(page)
        scroll_to(page, "__btn(__modal(/Số liệu chốt/), /Xác nhận chốt số liệu/)")
        plan_block = "__h4(__modal(/Số liệu chốt/), /^Kế hoạch năm/).parentElement"
        snap(page, "16-xac-nhan-ke-hoach.png", f"""(() => {{
          const m = __modal(/Số liệu chốt/);
          return window.__annotate([{plan_block}, __btn(m, /Xác nhận chốt số liệu/)]);
        }})()""", f"""(() => __clip([{plan_block}, __modal(/Số liệu chốt/).querySelector('.ant-modal-footer')], 16))()""")

        # 17. Sau khi chốt: kế hoạch chỉ xem, muốn đổi thì Đề nghị sửa
        page.locator(".ant-modal button", has_text="Xác nhận chốt số liệu").first.click()
        page.wait_for_timeout(2000)
        page.set_viewport_size({"width": 1500, "height": 1500})   # đủ chỗ cho cả dòng + nút Đề nghị sửa
        page.goto(f"{WEB}/ke-hoach-nam")
        page.wait_for_timeout(2500)
        page.evaluate("""() => { const a = [...document.querySelectorAll('.ant-alert')]
            .find(x => /đã chốt cùng đợt/.test(x.textContent)); a && a.scrollIntoView({block: 'start'}); scrollBy(0, -20); }""")
        page.wait_for_timeout(400)
        snap(page, "17-ke-hoach-da-chot.png", """(() => {
          const alert = [...document.querySelectorAll('.ant-alert')].find(a => /đã chốt cùng đợt/.test(a.textContent));
          const tag = [...document.querySelectorAll('.ant-tag')].find(t => /Đã chốt/.test(t.textContent));
          return window.__annotate([alert, tag, __btn(document.querySelector('table'), /Đề nghị sửa/)]);
        })()""", """(() => { const alert = [...document.querySelectorAll('.ant-alert')].find(a => /đã chốt cùng đợt/.test(a.textContent));
          return __clip([alert, document.querySelector('table')], 16); })()""")
        browser.close()


if __name__ == "__main__":
    main()
