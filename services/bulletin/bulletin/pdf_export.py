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


def _pack(groups: list[list], measures: list[dict]) -> list[list[str]]:
    """Xếp item của từng nhóm vào các trang (≤ USABLE_PX). Mỗi nhóm bắt đầu trang mới.
    Item str = block nguyên khối; item dict = bảng TÁCH DÒNG (thead lặp mỗi trang) để
    lấp đầy trang, không tràn/mồ côi khi bảng dài hơn 1 trang."""
    pages: list[list[str]] = []
    cur: list[str] = []
    cur_h = 0.0

    def newpage() -> None:
        nonlocal cur, cur_h
        if cur:
            pages.append(cur)
        cur, cur_h = [], 0.0

    idx = 0
    for group in groups:
        newpage()  # mỗi nhóm (I+II · III · IV) bắt đầu trang mới
        for item in group:
            m = measures[idx] if idx < len(measures) else {}
            idx += 1
            if isinstance(item, dict):  # bảng tách dòng
                head_h = m.get("head", 0.0)
                row_hs = m.get("rows", []) or [0.0] * len(item["rows"])
                rows = item["rows"]
                first, i, n = True, 0, len(rows)
                while i < n:
                    pre_h = m.get("pre", 0.0) if first else 0.0
                    gap = _GAP_PX if cur else 0.0
                    # Không đủ chỗ cho tiêu đề + thead + ít nhất 1 dòng → sang trang mới.
                    if cur and cur_h + gap + pre_h + head_h + row_hs[i] > T.USABLE_PX:
                        newpage()
                        gap = 0.0
                    used = pre_h + head_h
                    chunk: list[str] = []
                    while i < n and cur_h + gap + used + row_hs[i] <= T.USABLE_PX:
                        used += row_hs[i]
                        chunk.append(rows[i])
                        i += 1
                    if not chunk:  # an toàn: ép ≥1 dòng để không kẹt vòng lặp
                        used += row_hs[i]
                        chunk.append(rows[i])
                        i += 1
                    pre_html = item["pre"] if first else ""
                    cur.append(f"{pre_html}<table class='floor'>{item['head']}<tbody>{''.join(chunk)}</tbody></table>")
                    cur_h += gap + used
                    first = False
                    if i < n:  # còn dòng → sang trang, thead sẽ lặp lại
                        newpage()
            else:  # block nguyên khối (str)
                h = m.get("h", 0.0)
                gap = _GAP_PX if cur else 0.0
                if cur and cur_h + gap + h > T.USABLE_PX:
                    newpage()
                    gap = 0.0
                cur.append(item)
                cur_h += gap + h
    newpage()
    return pages


def generate_pdf(data: BulletinData, assets: dict[str, str], output_path: str | Path) -> Path:
    """Tạo PDF bản tin. assets: {slot -> đường dẫn ảnh} (cover-front/back, header/footer-banner)."""
    from pypdf import PdfReader, PdfWriter

    uris = {k: v for k, v in ((k, _data_uri(v)) for k, v in assets.items()) if v}

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Chromium thỉnh thoảng chết ngay lúc khởi động trong container (signal 11) → cả lần xuất hỏng.
    # Lần chạy lại luôn qua, nên thử lại thay vì bắt người dùng bấm lại và thấy "lỗi hệ thống".
    last_exc: Exception | None = None
    for attempt in range(_RENDER_TRIES):
        try:
            parts = _render_parts(data, uris)
            break
        except Exception as exc:  # noqa: BLE001 - Chromium chết giữa chừng: thử lại rồi mới bó tay
            last_exc = exc
            print(f"[bulletin] Render PDF lỗi (lần {attempt + 1}/{_RENDER_TRIES}): {exc}")
    else:
        raise RuntimeError(f"Chromium không render được PDF sau {_RENDER_TRIES} lần") from last_exc

    writer = PdfWriter()
    for blob in parts:
        for pg in PdfReader(io.BytesIO(blob)).pages:
            writer.add_page(pg)
    with out.open("wb") as f:
        writer.write(f)
    return out


_RENDER_TRIES = 2


def _render_parts(data: BulletinData, uris: dict[str, str]) -> tuple[bytes, bytes, bytes]:
    """Render (cover, ruột, back) qua Chromium — 1 phiên trình duyệt cho cả 3 phần."""
    from playwright.sync_api import sync_playwright

    groups = T.content_groups(data)
    flat = [b for g in groups for b in g]

    cover = T.cover_html(data, uris)
    back = T.back_html(data, uris)
    zero = {"top": "0", "bottom": "0", "left": "0", "right": "0"}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        def render(html: str) -> bytes:
            page.set_content(html, wait_until="load")
            return page.pdf(width=T.PAGE_W, height=T.PAGE_H, print_background=True, margin=zero)

        # Đo chiều cao từng item (block/bảng) → xếp trang (measure-and-pack).
        # Lỗi đo → fallback: mỗi nhóm 1 trang, bảng KHÔNG tách.
        fallback = [[T.item_html(it) for it in g] for g in groups]
        try:
            page.set_content(T.measure_html(flat), wait_until="load")
            measures = page.evaluate(
                "() => Array.from(document.querySelectorAll('.measure > .mitem')).map(el => {"
                "  const tbl = el.querySelector('table'), pre = el.querySelector('.mt-pre');"
                "  if (tbl && pre) {"
                "    const th = tbl.querySelector('thead');"
                "    const rs = Array.from(tbl.querySelectorAll('tbody > tr'));"
                "    return {pre: pre.getBoundingClientRect().height,"
                "            head: th ? th.getBoundingClientRect().height : 0,"
                "            rows: rs.map(r => r.getBoundingClientRect().height)};"
                "  }"
                "  return {h: el.getBoundingClientRect().height};"
                "})"
            )
            pages = _pack(groups, measures) if len(measures) == len(flat) else fallback
        except Exception:  # noqa: BLE001 - đo lỗi → dựng theo nhóm
            pages = fallback

        content = T.pages_html(pages, data, uris)

        parts = (render(cover), render(content), render(back))
        browser.close()
    return parts
