"""Render BulletinData → PDF qua Chromium (Playwright), ghép trang đầu/cuối bằng pypdf.

- Trang đầu (cover) & trang cuối (back): full trang, KHÔNG header/footer.
- Ruột: measure-and-pack — đo chiều cao từng block rồi xếp vào trang (.pg), header/footer
  "nướng" sẵn mỗi trang; Section IV dài tự tràn nhiều trang.
- Dùng Chromium bundled của Playwright (không cần Google Chrome).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from . import html_template as T
from .models import BulletinData

_GAP_PX = 4  # khoảng đệm ước lượng giữa 2 block khi xếp trang


def _data_uri(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _pack(groups: list[list[str]], heights: list[float]) -> list[list[str]]:
    """Xếp block của từng nhóm vào các trang (≤ USABLE_PX). Mỗi nhóm bắt đầu trang mới."""
    pages: list[list[str]] = []
    idx = 0
    for group in groups:
        cur: list[str] = []
        cur_h = 0.0
        for block in group:
            h = heights[idx] if idx < len(heights) else 0.0
            idx += 1
            add = h + (_GAP_PX if cur else 0)
            if cur and cur_h + add > T.USABLE_PX:
                pages.append(cur)
                cur, cur_h = [], 0.0
                add = h
            cur.append(block)
            cur_h += add
        if cur:
            pages.append(cur)
    return pages


def generate_pdf(data: BulletinData, assets: dict[str, str], output_path: str | Path) -> Path:
    """Tạo PDF bản tin. assets: {slot -> đường dẫn ảnh} (cover-front/back, header/footer-banner)."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    uris = {k: v for k, v in ((k, _data_uri(v)) for k, v in assets.items()) if v}

    groups = T.content_groups(data)
    flat = [b for g in groups for b in g]

    cover = T.cover_html(data, uris)
    back = T.back_html(data, uris)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    zero = {"top": "0", "bottom": "0", "left": "0", "right": "0"}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        def render(html: str) -> bytes:
            page.set_content(html, wait_until="load")
            return page.pdf(width=T.PAGE_W, height=T.PAGE_H, print_background=True, margin=zero)

        # Đo chiều cao từng block → xếp trang (measure-and-pack). Lỗi đo → fallback 1 nhóm/trang.
        try:
            page.set_content(T.measure_html(flat), wait_until="load")
            heights = page.evaluate(
                "() => Array.from(document.querySelectorAll('.measure > .blk'))"
                ".map(e => e.getBoundingClientRect().height)"
            )
            pages = _pack(groups, heights) if len(heights) == len(flat) else groups
        except Exception:  # noqa: BLE001 - đo lỗi → dựng theo nhóm
            pages = groups

        content = T.pages_html(pages, data, uris)

        cover_pdf = render(cover)
        content_pdf = render(content)
        back_pdf = render(back)
        browser.close()

    writer = PdfWriter()
    for blob in (cover_pdf, content_pdf, back_pdf):
        for pg in PdfReader(io.BytesIO(blob)).pages:
            writer.add_page(pg)
    with out.open("wb") as f:
        writer.write(f)
    return out
