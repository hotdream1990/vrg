"""Dựng HTML cho bản tin ngày → PDF (Chromium), mô phỏng sát bố cục PPTX.

- Khổ trang = khổ slide PPTX: 7.5 x 10.83 in (đặt qua page.pdf width/height).
- Header/footer lặp mọi trang bằng header_template/footer_template của Chromium
  (banner xanh full + logo + tiêu đề · footer banner + RUBBERGROUP).
- Tách trang theo slide PPTX: (I+II) · (III) · (IV).
- cover/back: ảnh bìa full trang.
"""

from __future__ import annotations

from .models import BulletinData

PAGE_W, PAGE_H = "7.5in", "10.83in"


def _fmt(v: int | None) -> str:
    return f"{v:,}" if v is not None else "—"


def _chg(v: int | None) -> str:
    if v is None:
        return ""
    return f"+{v}" if v > 0 else str(v)


def _pct(v: float | None) -> str:
    return "" if v is None else f"{v:.1f}"


def _cls(v) -> str:
    if v is None:
        return "flat"
    return "up" if v > 0 else ("down" if v < 0 else "flat")


_WORLD_GROUPS = [
    ("OSE", ["RSS3"]),
    ("SHANGHAI", ["RSS3"]),
    ("SGX", ["RSS3", "TSR20"]),
    ("MRE", ["SMRCV", "SMR20", "LATEX"]),
]
_PHYS_ROWS = ["RSS3", "STR20", "SMR20", "SIR20",
              "Thai Latex 60% (Bulk)", "Thai Latex 60% (Drums)"]


_CONTENT_CSS = f"""
* {{ box-sizing: border-box; }}
html,body {{ margin: 0; }}
body {{ font-family: 'Times New Roman','Arial',sans-serif; color:#111; font-size: 11px; }}

/* Mỗi .pg = đúng 1 trang (header xanh trên cùng + body + footer dưới cùng) — mô phỏng slide PPTX. */
.pg {{ width:{PAGE_W}; height:{PAGE_H}; display:flex; flex-direction:column; overflow:hidden; break-after:page; }}
.pg:last-child {{ break-after:auto; }}
.pg-body {{ flex:1; padding:14px 26px 6px; overflow:hidden; }}

/* Header xanh full-width (bleed), logo tròn trái, tiêu đề TRẮNG */
.pg-hdr {{ position:relative; width:100%; height:96px; flex:0 0 auto; background:#2e8b4f; background-size:100% 100%; }}
.pg-hdr-logo {{ position:absolute; left:26px; top:50%; transform:translateY(-50%); height:68px; width:68px;
  border-radius:50%; background:#fff; object-fit:contain; }}
.pg-hdr-t {{ position:absolute; left:112px; right:16px; top:0; height:96px; display:flex; align-items:center;
  color:#ffffff; font-family:Arial,sans-serif; font-size:17px; font-weight:800; letter-spacing:.3px; }}
/* Footer xanh full-width */
.pg-ftr {{ position:relative; width:100%; height:40px; flex:0 0 auto; background:#2e8b4f; background-size:100% 100%;
  color:#fff; font-family:Arial,sans-serif; font-size:10px; font-weight:700; }}
.pg-ftr span {{ position:absolute; top:0; height:40px; display:flex; align-items:center; }}
.pg-ftr .l {{ left:34px; }} .pg-ftr .r {{ right:34px; }}

h2.section {{ font-size: 13px; color:#0b6b3a; margin: 4px 0 6px; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; margin-bottom:8px; }}
thead {{ display: table-header-group; }}
th,td {{ border:1px solid #b9c7bd; padding:4px 6px; font-size: 11px; }}
th {{ background:#dcebd0; background:#dcecdd; color:#0b6b3a; text-align:center; font-weight:700; }}
td.r {{ text-align:right; }} td.c {{ text-align:center; }}
tbody tr:nth-child(even) td {{ background:#f4f9f5; }}
tr {{ page-break-inside: avoid; }}
.up{{color:#c0392b}} .down{{color:#1e8449}} .flat{{color:#555}}
p.para {{ margin:4px 0; line-height:1.4; text-align:justify; }}
.src {{ font-size:9.5px; color:#666; margin-top:6px; }}
.note {{ color:#999; font-style:italic; }}
"""


def _world_table(data: BulletinData) -> str:
    if not data.world_prices:
        return '<p class="note">Không có dữ liệu giá thế giới cho ngày này.</p>'
    m = {(w.exchange, w.grade): w for w in data.world_prices}
    prev = data.prev_date.strftime("%d/%m/%y")
    curr = data.report_date.strftime("%d/%m/%y")
    head = (
        "<thead><tr><th rowspan='2'>STT</th><th rowspan='2'>Sàn</th>"
        "<th rowspan='2'>Chủng loại</th><th rowspan='2'>Đơn vị tính</th>"
        f"<th rowspan='2'>Giá<br>({prev})</th><th rowspan='2'>Giá<br>({curr})</th>"
        "<th colspan='2'>Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead>"
    )
    body = ""
    for i, (exc, grades) in enumerate(_WORLD_GROUPS, 1):
        n = len(grades)
        for j, g in enumerate(grades):
            w = m.get((exc, g))
            lead = (f"<td class='c' rowspan='{n}'>{i}</td>"
                    f"<td class='c' rowspan='{n}'>{exc}</td>") if j == 0 else ""
            kl = _cls(w.change_abs) if w else "flat"
            body += (
                f"<tr>{lead}<td>{g}</td><td class='c'>USD/T</td>"
                f"<td class='r'>{_fmt(w.price_prev) if w else 'N/A'}</td>"
                f"<td class='r'>{_fmt(w.price_curr) if w else 'N/A'}</td>"
                f"<td class='r {kl}'>{_chg(w.change_abs) if w else ''}</td>"
                f"<td class='r {kl}'>{_pct(w.change_pct) if w else ''}</td></tr>"
            )
    return f"<table>{head}<tbody>{body}</tbody></table>"


def _physical_table(data: BulletinData) -> str:
    if not data.physical_prices:
        return '<p class="note">Không có dữ liệu giá vật chất (ANRPC) cho ngày này.</p>'
    m = {p.grade: p for p in data.physical_prices}
    prev = (data.physical_prev_date or data.prev_date).strftime("%d/%m/%y")
    curr = (data.physical_curr_date or data.report_date).strftime("%d/%m/%y")
    head = (
        "<thead><tr><th rowspan='2'>Chủng loại</th>"
        f"<th rowspan='2'>Giá<br>({prev})</th><th rowspan='2'>Giá<br>({curr})</th>"
        "<th colspan='2'>Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead>"
    )
    body = ""
    for g in _PHYS_ROWS:
        p = m.get(g)
        kl = _cls(p.change_abs) if p else "flat"
        body += (
            f"<tr><td>{g}</td>"
            f"<td class='r'>{_fmt(p.price_prev) if p else 'N/A'}</td>"
            f"<td class='r'>{_fmt(p.price_curr) if p else 'N/A'}</td>"
            f"<td class='r {kl}'>{_chg(p.change_abs) if p else ''}</td>"
            f"<td class='r {kl}'>{_pct(p.change_pct) if p else ''}</td></tr>"
        )
    return f"<table>{head}<tbody>{body}</tbody></table>"


def _vrg_floor_table(data: BulletinData) -> str:
    if not data.vrg_floor_curr:
        return ""
    prev = {r.grade: r for r in data.vrg_floor_prev}
    rows = ""
    for c in data.vrg_floor_curr:
        p = prev.get(c.grade)
        rows += (
            f"<tr><td>{c.grade}</td>"
            f"<td class='r'>{_fmt(p.fob_usd) if p else '—'}</td>"
            f"<td class='r'>{_fmt(p.domestic_vnd) if p else '—'}</td>"
            f"<td class='r'>{_fmt(c.fob_usd)}</td><td class='r'>{_fmt(c.domestic_vnd)}</td></tr>"
        )
    pl = (data.vrg_floor_prev_label or "Lần trước").replace("\n", " ")
    cl = (data.vrg_floor_curr_label or "Hiện tại").replace("\n", " ")
    return (
        f"<table><thead><tr><th rowspan='2'>Chủng loại</th><th colspan='2'>{pl}</th>"
        f"<th colspan='2'>{cl}</th></tr>"
        "<tr><th>Giá XK FOB/FCA<br>(USD/T)</th><th>Giá nội địa<br>(VNĐ/T)</th>"
        "<th>Giá XK FOB/FCA<br>(USD/T)</th><th>Giá nội địa<br>(VNĐ/T)</th></tr></thead><tbody>"
        + rows + "</tbody></table>"
    )


def _raw_materials(data: BulletinData) -> str:
    """Giá thu mua mủ nước theo công ty VRG (đồng/độ TSC) — chỉ hiện công ty có giá."""
    regions = {k: v for k, v in data.raw_material_regions.items() if v}
    if not regions:
        return ""
    rows = "".join(f"<tr><td>{k}</td><td class='r'>{v}</td></tr>" for k, v in regions.items())
    return (
        "<p class='para'><b>Giá mủ nguyên liệu — giá thu mua mủ nước theo công ty:</b></p>"
        "<table><thead><tr><th>Công ty</th><th>Giá (đồng/độ TSC)</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _news(data: BulletinData) -> str:
    """Section IV — bố cục đúng template: tóm tắt giá sàn + physical (auto) + phân tích + nguồn."""
    dd_mm = data.report_date.strftime("%d/%m")
    out = ""
    # 1. Giá cao su trên các sàn (auto)
    ex = [s for s in data.market_exchange_summary if s]
    if ex:
        out += f"<p class='para'><b>1. Giá cao su {dd_mm} trên các sàn giao dịch thế giới:</b></p>"
        for s in ex:
            out += f"<p class='para'>{s}</p>"
    # 2. Giá Physical (auto) — ngày = phiên vật chất THẬT (có thể khác ngày báo cáo)
    phys_dd_mm = (data.physical_curr_date or data.report_date).strftime("%d/%m")
    if data.market_physical_summary:
        out += f"<p class='para'><b>2. Giá Physical {phys_dd_mm}:</b></p>"
        out += f"<p class='para'>{data.market_physical_summary}</p>"
    else:
        out += f"<p class='para'><b>2. Giá Physical {phys_dd_mm}: không có giá giao dịch.</b></p>"
    # 3. Phân tích (admin/AI nhập tay)
    if data.market_analysis:
        out += "<p class='para'><b>3. Các thông tin có liên quan:</b></p>"
        for a in data.market_analysis:
            out += f"<p class='para'>{a}</p>"
    if data.source_urls:
        out += "<p class='src'>Nguồn: " + " · ".join(data.source_urls) + "</p>"
    return out or '<p class="note">Chưa có thông tin thị trường.</p>'


def _page_header(data: BulletinData, assets: dict[str, str]) -> str:
    """Header xanh full-width (logo + tiêu đề TRẮNG) — nướng vào đầu mỗi trang content."""
    hb = assets.get("header-banner")
    logo = assets.get("logo-vrg")
    style = f"background-image:url('{hb}');" if hb else ""
    lg = f"<img class='pg-hdr-logo' src='{logo}'/>" if logo else ""
    return (f"<div class='pg-hdr' style=\"{style}\">{lg}"
            f"<div class='pg-hdr-t'>BẢN TIN THỊ TRƯỜNG CAO SU NGÀY {data.report_date:%d/%m/%Y}</div></div>")


def _page_footer(data: BulletinData, assets: dict[str, str]) -> str:
    fb = assets.get("footer-banner") or assets.get("header-banner")
    style = f"background-image:url('{fb}');" if fb else ""
    return (f"<div class='pg-ftr' style=\"{style}\">"
            "<span class='l'>RUBBERGROUP.VN</span>"
            "<span class='r'>BẢN TIN THỊ TRƯỜNG KINH DOANH</span></div>")


def content_html(data: BulletinData, assets: dict[str, str] | None = None) -> str:
    """Nội dung bản tin — mỗi trang (.pg) = header xanh + body + footer (mô phỏng slide PPTX)."""
    assets = assets or {}
    hdr, ftr = _page_header(data, assets), _page_footer(data, assets)

    def page(inner: str) -> str:
        return f"<div class='pg'>{hdr}<div class='pg-body'>{inner}</div>{ftr}</div>"

    d = data.report_date.strftime("%d/%m/%Y")
    p1 = (f'<h2 class="section">I. Giá cao su thiên nhiên thế giới ngày {d}</h2>' + _world_table(data)
          + '<h2 class="section">II. Giá các sản phẩm cao su giao ngay</h2>' + _physical_table(data))
    p2 = ('<h2 class="section">III. Giá trong nước — Giá sàn VRG</h2>'
          + _vrg_floor_table(data) + _raw_materials(data))
    p3 = '<h2 class="section">IV. Các thông tin thị trường liên quan</h2>' + _news(data)
    body = page(p1) + page(p2) + page(p3)
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{_CONTENT_CSS}</style>"
            f"</head><body>{body}</body></html>")


def _cover(image_uri: str | None, title: str, subtitle: str) -> str:
    bg = f"background-image:url('{image_uri}');" if image_uri else "background:#0b6b3a;"
    css = (
        f"@page{{size:{PAGE_W} {PAGE_H};margin:0;}}html,body{{margin:0;height:100%;}}"
        f".pg{{width:{PAGE_W};height:{PAGE_H};" + bg + "background-size:cover;background-position:center;"
        "position:relative;font-family:'Times New Roman',Arial,sans-serif;}"
        ".band{position:absolute;left:0;right:0;bottom:16%;text-align:center;color:#fff;"
        "text-shadow:0 2px 6px rgba(0,0,0,.55);}"
        ".band h1{font-size:26px;margin:0 0 6px;} .band p{font-size:16px;margin:0;}"
    )
    band = f"<div class='band'><h1>{title}</h1><p>{subtitle}</p></div>" if title else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style>"
            f"</head><body><div class='pg'>{band}</div></body></html>")


def cover_html(data: BulletinData, assets: dict[str, str]) -> str:
    return _cover(assets.get("cover-front"), "BẢN TIN THỊ TRƯỜNG CAO SU",
                  f"Ngày {data.report_date:%d/%m/%Y}")


def back_html(data: BulletinData, assets: dict[str, str]) -> str:
    return _cover(assets.get("cover-back"), "", "")
