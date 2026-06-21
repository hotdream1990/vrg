"""Render BulletinData → PDF qua Chromium (Playwright), ghép trang đầu/cuối bằng pypdf.

- Trang đầu (cover) & trang cuối (back): full trang, KHÔNG header/footer.
- Các trang giữa (content): tự nhảy trang, header/footer lặp trên mọi trang (Chromium).
Dùng Chrome hệ thống (channel="chrome") để khỏi tải Chromium.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from . import html_template as T
from .models import BulletinData


def _data_uri(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def generate_pdf(data: BulletinData, assets: dict[str, str], output_path: str | Path) -> Path:
    """Tạo PDF bản tin. assets: {slot -> đường dẫn ảnh} (cover-front/back, header/footer-banner)."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    uris = {k: _data_uri(v) for k, v in assets.items()}
    uris = {k: v for k, v in uris.items() if v}

    cover = T.cover_html(data, uris)
    content = T.content_html(data)
    back = T.back_html(data, uris)
    header = T.header_template(data, uris)
    footer = T.footer_template(data, uris)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    zero = {"top": "0", "bottom": "0", "left": "0", "right": "0"}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page()

        def render(html: str, **kw) -> bytes:
            page.set_content(html, wait_until="load")
            return page.pdf(width=T.PAGE_W, height=T.PAGE_H, print_background=True, **kw)

        cover_pdf = render(cover, margin=zero)
        content_pdf = render(
            content,
            margin={"top": "1.28in", "bottom": "0.62in", "left": "0.36in", "right": "0.36in"},
            display_header_footer=True, header_template=header, footer_template=footer,
        )
        back_pdf = render(back, margin=zero)
        browser.close()

    writer = PdfWriter()
    for blob in (cover_pdf, content_pdf, back_pdf):
        for pg in PdfReader(io.BytesIO(blob)).pages:
            writer.add_page(pg)
    with out.open("wb") as f:
        writer.write(f)
    return out
