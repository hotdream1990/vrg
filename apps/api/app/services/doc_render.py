"""Chụp HTML thành PNG / in thành PDF bằng Chromium (Playwright — có sẵn trong image để xuất PDF bản
tin & báo cáo tuần). Dùng cho hình dự thảo giá sàn và PDF tờ trình.

Nhúng font Tinos (cùng metric Times New Roman, đủ tiếng Việt) bằng data-URI: máy chủ Linux không có
Times New Roman, không nhúng thì Chromium lấy font khác → lệch bố cục so với bản xem trên máy người dùng.
Đậm-nghiêng dùng họ `TinosBI` (Tinos-Bold, Chromium tự nghiêng) — tự đậm từ Tinos-Italic ra font Type 3
nhoè chữ Việt (kinh nghiệm từ services/weekly_report).
"""
from __future__ import annotations

import base64
from functools import lru_cache

from app.core.paths import services_dir

_FONTS = [("Tinos", 400, "normal", "Tinos-Regular.ttf"), ("Tinos", 700, "normal", "Tinos-Bold.ttf"),
          ("Tinos", 400, "italic", "Tinos-Italic.ttf"), ("TinosBI", 700, "normal", "Tinos-Bold.ttf")]


class RenderError(RuntimeError):
    """Không dựng được ảnh/PDF (thiếu Chromium…) — thông điệp tiếng Việt cho người dùng."""


@lru_cache(maxsize=1)
def _font_css() -> str:
    folder = services_dir() / "weekly_report" / "weekly" / "fonts"
    out = []
    for family, weight, style, fname in _FONTS:
        path = folder / fname
        if not path.is_file():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode()
        out.append(f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:{style};"
                   f"font-display:block;src:url(data:font/ttf;base64,{b64}) format('truetype');}}")
    out.append("body,table{font-family:Tinos,'Times New Roman',serif!important}"
               ".lead{font-family:TinosBI,Tinos,serif!important;font-style:italic}")
    return "".join(out)


def _with_fonts(html: str) -> str:
    return html.replace("</style>", _font_css() + "</style>", 1)


def _run(fn):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                return fn(browser)
            finally:
                browser.close()
    except RenderError:
        raise
    except Exception as exc:  # noqa: BLE001 - Chromium thiếu/lỗi → báo gọn cho người dùng
        raise RenderError(f"Không dựng được tệp (Chromium): {exc}".splitlines()[0][:300]) from exc


def html_to_png(html: str, selector: str, scale: float = 2.0) -> bytes:
    """Ảnh PNG của phần tử `selector` (độ nét x`scale` cho chép vào Zalo/email không mờ)."""
    def shot(browser):
        page = browser.new_page(device_scale_factor=scale, viewport={"width": 1000, "height": 800})
        page.set_content(_with_fonts(html), wait_until="load")
        page.evaluate("document.fonts.ready")
        return page.locator(selector).screenshot(type="png")
    return _run(shot)


def html_to_pdf(html: str) -> bytes:
    """PDF A4 theo @page của HTML (lề, khổ giấy do mẫu khai)."""
    def pdf(browser):
        page = browser.new_page()
        page.set_content(_with_fonts(html), wait_until="load")
        page.evaluate("document.fonts.ready")
        return page.pdf(prefer_css_page_size=True, print_background=True)
    return _run(pdf)
