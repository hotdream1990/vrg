"""Render WeeklyReportData → PDF qua Chromium (Playwright), ghép bìa đầu/cuối bằng pypdf.

Ruột: measure-and-pack — đo chiều cao từng block rồi xếp vào trang (.pg), header/footer nướng
sẵn mỗi trang; Phần III/IV dài tự tràn nhiều trang. Bìa/back = full trang, không header/footer.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from . import html_template as T
from .models import WeeklyReportData

_GAP_PX = 4


def _data_uri(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def _pack(groups: list[list[str]], heights: list[float]) -> list[list[str]]:
    """Xếp block CHẢY LIÊN TỤC vào các trang (≤ USABLE_PX) — không ép mỗi nhóm sang trang mới,
    để ruột bám sát mẫu ~6 trang (bìa + nội dung liền mạch + bìa sau)."""
    pages: list[list[str]] = []
    cur: list[str] = []
    cur_h = 0.0
    idx = 0
    for group in groups:
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


def generate_pdf(data: WeeklyReportData, assets: dict[str, str], output_path: str | Path) -> Path:
    """Tạo PDF báo cáo tuần. assets: {slot -> đường dẫn ảnh}."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    uris = {k: v for k, v in ((k, _data_uri(v)) for k, v in assets.items()) if v}
    groups = T.content_groups(data)
    flat = [b for g in groups for b in g]

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    zero = {"top": "0", "bottom": "0", "left": "0", "right": "0"}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        def render(html: str) -> bytes:
            page.set_content(html, wait_until="load")
            return page.pdf(width=T.PAGE_W, height=T.PAGE_H, print_background=True, margin=zero)

        try:
            page.set_content(T.measure_html(flat), wait_until="load")
            heights = page.evaluate(
                "() => Array.from(document.querySelectorAll('.measure > .blk'))"
                ".map(e => e.getBoundingClientRect().height)"
            )
            pages = _pack(groups, heights) if len(heights) == len(flat) else groups
        except Exception:  # noqa: BLE001
            pages = groups

        cover_pdf = render(T.cover_html(data, uris))
        content_pdf = render(T.pages_html(pages, uris))
        back_pdf = render(T.back_html(uris))
        browser.close()

    writer = PdfWriter()
    for blob in (cover_pdf, content_pdf, back_pdf):
        for pg in PdfReader(io.BytesIO(blob)).pages:
            writer.add_page(pg)
    with out.open("wb") as f:
        writer.write(f)
    return out
