"""Dựng HTML ruột bản tin ngày → PDF (Chromium), bám bố cục mẫu thật.

- Khổ trang = 7.5 x 10.83 in (đặt qua page.pdf width/height).
- Mỗi trang = 1 `.pg` (header xanh full trên cùng + body + footer dưới cùng); header/footer
  được "nướng" vào từng trang (crisp, tiêu đề trắng, flush mép) — KHÔNG dùng header Chromium.
- Ruột được chia thành các "block" nguyên khối; `pdf_export` đo chiều cao rồi xếp vào trang
  (measure-and-pack) → Section IV dài tự tràn nhiều trang mà header/footer vẫn lặp đúng.
- Bố cục: nhóm (I + II) · (III) · (IV — có thể nhiều trang).
- cover/back: ảnh bìa full trang (dựng riêng ở pdf_export).
"""

from __future__ import annotations

import base64
from pathlib import Path

from .convert import NO_TRADING, is_no_trading
from .models import BulletinData

PAGE_W, PAGE_H = "7.5in", "10.83in"

# ── Font NHÚNG (OFL/Apache-2.0) — làm PDF hiển thị GIỐNG NHAU trên mọi máy ──
# Tinos ~ Times New Roman, Arimo ~ Arial (cùng metric → không lệch bố cục), phủ đủ tiếng Việt.
# Nhúng qua data-URI để Chromium embed vào PDF, KHÔNG phụ thuộc font hệ thống của máy render.
_FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_FILES = [
    ("Tinos", 400, "normal", "Tinos-Regular.ttf"),
    ("Tinos", 700, "normal", "Tinos-Bold.ttf"),
    ("Tinos", 400, "italic", "Tinos-Italic.ttf"),
    ("Arimo", 400, "normal", "Arimo-Regular.ttf"),
    ("Arimo", 700, "normal", "Arimo-Bold.ttf"),
]


def _font_faces() -> str:
    """Sinh các @font-face (data-URI) một lần lúc import."""
    out = []
    for family, weight, style, fname in _FONT_FILES:
        b64 = base64.b64encode((_FONTS_DIR / fname).read_bytes()).decode()
        out.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:{style};"
            f"font-display:block;src:url(data:font/ttf;base64,{b64}) format('truetype');}}"
        )
    return "".join(out)


_FONT_FACE_CSS = _font_faces()

# Chiều cao body dùng được / trang (px CSS): 10.83in*96(≈1040) − header 148 − footer 56 − padding(14+6).
# Chừa slack để không bao giờ tràn (overflow bị cắt) — packing conservative, thừa thì thêm trang.
USABLE_PX = 808


# ── Format số ──
# Bảng (I/II/III) dùng dấu phẩy nghìn + phần trăm dấu chấm, cột thay đổi KHÔNG dấu '+' (theo mẫu).
def _fmt(v: int | None) -> str:
    """Ô giá: chưa có số → N/A; giá 0 → 'No Trading' (phiên đó sàn không giao dịch)."""
    if v is None:
        return "N/A"
    return NO_TRADING if is_no_trading(v) else f"{v:,}"


def _chg(v: int | None) -> str:
    # Cột USD/T: số dương có dấu '+' (theo mẫu: +11, +41), âm có '-', 0 → '0'.
    if v is None:
        return ""
    return f"+{v}" if v > 0 else str(v)


def _pct(v: float | None) -> str:
    return "" if v is None else f"{v:.1f}"


_WORLD_GROUPS = [
    ("OSE", ["RSS3"]),
    ("SHANGHAI", ["RSS3"]),
    ("SGX", ["RSS3", "TSR20"]),
    ("MRE", ["SMRCV", "SMR20", "LATEX"]),
]
_PHYS_ROWS = ["RSS3", "STR20", "SMR20", "SIR20",
              "Thai Latex 60% (Bulk)", "Thai Latex 60% (Drums)"]


_CONTENT_CSS = f"""
{_FONT_FACE_CSS}
* {{ box-sizing: border-box; }}
html,body {{ margin: 0; }}
body {{ font-family: 'Tinos','Times New Roman',serif; color:#111; font-size: 13px; }}

/* Mỗi .pg = đúng 1 trang (header xanh trên cùng + body + footer dưới cùng). */
.pg {{ width:{PAGE_W}; height:{PAGE_H}; display:flex; flex-direction:column; overflow:hidden; break-after:page; }}
.pg:last-child {{ break-after:auto; }}
.pg-body {{ flex:1; padding:14px 26px 6px; overflow:hidden; }}
/* .measure = khung đo chiều cao block (cùng bề rộng nội dung với .pg-body). */
.measure {{ width:{PAGE_W}; padding:0 26px; }}
/* Mỗi block nguyên khối — flow-root để chứa margin con (đo/hiển thị nhất quán, không co margin). */
.blk {{ display:flow-root; }}
/* Khung đo 1 item (block hoặc bảng có thể tách dòng) — flow-root cho khớp lúc render. */
.mitem,.mt-pre {{ display:flow-root; }}

/* Header xanh full-width, logo tròn trái, tiêu đề TRẮNG — cao 148px như mẫu */
.pg-hdr {{ position:relative; width:100%; height:148px; flex:0 0 auto; background:#2e8b4f; background-size:100% 100%; }}
.pg-hdr-logo {{ position:absolute; left:30px; top:50%; transform:translateY(-50%); height:100px; width:100px;
  border-radius:50%; background:#fff; object-fit:contain; }}
.pg-hdr-t {{ position:absolute; left:150px; right:20px; top:0; height:148px; display:flex; align-items:center;
  color:#ffffff; font-family:'Arimo',Arial,sans-serif; font-size:21px; font-weight:800; letter-spacing:.3px; }}
/* Footer xanh full-width — cao 56px như mẫu */
.pg-ftr {{ position:relative; width:100%; height:56px; flex:0 0 auto; background:#2e8b4f; background-size:100% 100%;
  color:#fff; font-family:'Arimo',Arial,sans-serif; font-size:12px; font-weight:700; }}
.pg-ftr span {{ position:absolute; top:0; height:56px; display:flex; align-items:center; }}
.pg-ftr .l {{ left:34px; }} .pg-ftr .r {{ right:34px; }}

h2.section {{ font-size:15px; color:#0a9e48; margin:6px 0 8px; font-weight:700; }}
p.sub {{ font-weight:700; margin:10px 0 6px; line-height:1.45; font-size:13.5px; }}
table {{ width:100%; border-collapse:collapse; margin:2px 0 10px; }}
thead {{ display: table-header-group; }}
th,td {{ border:1px solid #b9c7bd; padding:9px 8px; font-size:13px; }}
/* Bảng giá sàn (III.1): giãn dòng lấp bớt khoảng trống cuối trang. Ngưỡng đã đo trên prod (font Tinos,
   Chromium): 7px là mức tối đa còn giữ III.1 + III.2 chung 1 trang; ≥8px đẩy III.2 sang trang sau. */
table.floor th, table.floor td {{ padding:7px 8px; line-height:1.35; }}
/* Bảng II (giao ngay) giãn dòng để lấp khoảng trống cuối trang cho cân đối (chỉ riêng mục này). */
table.phys th, table.phys td {{ padding-top:16px; padding-bottom:16px; }}
th {{ background:#e8f0d8; color:#0a9e48; text-align:center; font-weight:700; }}
td.r {{ text-align:right; }} td.c {{ text-align:center; }}
ul.blt {{ margin:4px 0 10px; padding-left:24px; }}
ul.blt li {{ margin:6px 0; line-height:1.55; text-align:justify; font-size:13.5px; }}
p.para {{ margin:6px 0; line-height:1.5; font-size:13.5px; }}
p.src {{ font-size:12px; margin:10px 0 0; word-break:break-all; }}
p.src b {{ color:#0a9e48; }}
.note {{ color:#999; font-style:italic; }}
"""


# ── Section I — Giá cao su thiên nhiên thế giới ──
def _world_table(data: BulletinData) -> str:
    if not data.world_prices:
        return '<p class="note">Không có dữ liệu giá thế giới cho ngày này.</p>'
    m = {(w.exchange, w.grade): w for w in data.world_prices}
    prev = data.prev_date.strftime("%d/%m/%y")
    curr = data.report_date.strftime("%d/%m/%y")
    head = (
        "<thead><tr><th rowspan='2'>STT</th><th rowspan='2'></th>"
        "<th rowspan='2'>Chủng loại</th><th rowspan='2'>Đơn vị<br>tính</th>"
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
            body += (
                f"<tr>{lead}<td>{g}</td><td class='c'>USD/T</td>"
                f"<td class='r'>{_fmt(w.price_prev) if w else 'N/A'}</td>"
                f"<td class='r'>{_fmt(w.price_curr) if w else 'N/A'}</td>"
                f"<td class='r'>{_chg(w.change_abs) if w else ''}</td>"
                f"<td class='r'>{_pct(w.change_pct) if w else ''}</td></tr>"
            )
    return f"<table>{head}<tbody>{body}</tbody></table>"


# ── Section II — Giá các sản phẩm cao su giao ngay (physical) ──
def _physical_table(data: BulletinData) -> str:
    if not data.physical_prices:
        return '<p class="note">Không có giá vật chất giao dịch cho ngày này.</p>'
    m = {p.grade: p for p in data.physical_prices}
    prev = (data.physical_prev_date or data.prev_date).strftime("%d/%m/%y")
    curr = (data.physical_curr_date or data.report_date).strftime("%d/%m/%y")
    head = (
        "<thead><tr><th rowspan='2'>Chủng Loại</th>"
        f"<th rowspan='2'>Giá<br>({prev})</th><th rowspan='2'>Giá<br>({curr})</th>"
        "<th colspan='2'>Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead>"
    )
    body = ""
    for g in _PHYS_ROWS:
        p = m.get(g)
        body += (
            f"<tr><td>{g}</td>"
            f"<td class='r'>{_fmt(p.price_prev) if p else 'N/A'}</td>"
            f"<td class='r'>{_fmt(p.price_curr) if p else 'N/A'}</td>"
            f"<td class='r'>{_chg(p.change_abs) if p else ''}</td>"
            f"<td class='r'>{_pct(p.change_pct) if p else ''}</td></tr>"
        )
    return f"<table class='phys'>{head}<tbody>{body}</tbody></table>"


# ── Section III — Giá sàn Tập đoàn (2 lần) ──
def _floor_short(label: str | None) -> str | None:
    """'Giá sàn lần 14\\n(09/06/2026)' → 'lần 14' (bỏ tiền tố 'Giá sàn ' + phần ngày)."""
    if not label:
        return None
    title = label.split("\n")[0].strip()
    return title[len("Giá sàn "):].strip() if title.startswith("Giá sàn ") else title


def _floor_ref(data: BulletinData) -> str:
    ps = _floor_short(data.vrg_floor_prev_label)
    cs = _floor_short(data.vrg_floor_curr_label)
    if ps and cs:
        return f"{ps} & {cs}"
    return cs or ps or ""


def _floor_parts(data: BulletinData) -> tuple[str, list[str]] | None:
    """(thead, [tr,...]) bảng giá sàn — TÁCH DÒNG ĐƯỢC (mỗi grade 1 dòng, không rowspan thân bảng)
    để phân trang xếp vừa trang, không tràn/mồ côi. None nếu không có dữ liệu."""
    if not data.vrg_floor_curr:
        return None
    prev = {r.grade: r for r in data.vrg_floor_prev}
    rows: list[str] = []
    for c in data.vrg_floor_curr:
        p = prev.get(c.grade)
        # Ẩn dòng KHÔNG có giá ở cả 2 lần (vd SkimBlock chưa nhập) — tránh dòng toàn N/A.
        curr_empty = c.fob_usd is None and c.domestic_vnd is None
        prev_empty = p is None or (p.fob_usd is None and p.domestic_vnd is None)
        if curr_empty and prev_empty:
            continue
        rows.append(
            f"<tr><td>{c.grade}</td>"
            f"<td class='r'>{_fmt(p.fob_usd) if p else '—'}</td>"
            f"<td class='r'>{_fmt(p.domestic_vnd) if p else '—'}</td>"
            f"<td class='r'>{_fmt(c.fob_usd)}</td><td class='r'>{_fmt(c.domestic_vnd)}</td></tr>"
        )
    if not rows:
        return None
    pl = (data.vrg_floor_prev_label or "Lần trước").replace("\n", "<br>")
    cl = (data.vrg_floor_curr_label or "Hiện tại").replace("\n", "<br>")
    head = (
        f"<thead><tr><th rowspan='2'>Chủng Loại</th><th colspan='2'>{pl}</th>"
        f"<th colspan='2'>{cl}</th></tr>"
        "<tr><th>Giá XK<br>FOB/FCA<br>(USD/T)</th><th>Giá nội địa<br>(VNĐ/T)</th>"
        "<th>Giá XK<br>FOB/FCA<br>(USD/T)</th><th>Giá nội địa<br>(VNĐ/T)</th></tr></thead>"
    )
    return head, rows


def _raw_material_lines(data: BulletinData) -> str:
    """Giá mủ nguyên liệu GOM THEO KHU VỰC (đồng/độ TSC) — chỉ khu vực có giá."""
    regions = {k: v for k, v in data.raw_material_regions.items() if v}
    if not regions:
        return ""
    return "".join(f"<p class='para'>Khu vực {k}: {v} đ/độ TSC</p>" for k, v in regions.items())


# ── Section IV — Các thông tin thị trường liên quan ──
def _bullets(items: list[str]) -> str:
    lis = "".join(f"<li>{s}</li>" for s in items if s)
    return f"<ul class='blt'>{lis}</ul>" if lis else ""


# ── Header/footer nướng vào mỗi trang ──
def _page_header(data: BulletinData, assets: dict[str, str]) -> str:
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


# ── Blocks chia theo nhóm trang: (I+II) · (III) · (IV) ──
# Item = str (block nguyên khối) HOẶC dict bảng tách-dòng {"pre","head","rows"}.
def _table_item(pre: str, head: str, rows: list[str]) -> dict:
    """Bảng có thể tách dòng khi phân trang; `pre` = tiêu đề/đầu đề dính chunk đầu."""
    return {"pre": pre, "head": head, "rows": rows}


def item_html(it) -> str:
    """Dựng HTML đầy đủ 1 item (bảng KHÔNG tách) — dùng cho đường không đo (fallback)."""
    if isinstance(it, dict):
        return f"{it['pre']}<table class='floor'>{it['head']}<tbody>{''.join(it['rows'])}</tbody></table>"
    return it


def content_groups(data: BulletinData) -> list[list]:
    """Trả về các NHÓM item; mỗi nhóm bắt đầu 1 trang mới, item trong nhóm được xếp packing
    (bảng dict được tách dòng vừa trang; str là block nguyên khối).

    Nhóm: (I+II) · (III: giá sàn NÉN GỌN + mủ nguyên liệu — vừa 1 trang) · (IV: sang trang mới).
    Bảng giá sàn nén (class 'floor') giữ III.1 + III.2 chung 1 trang; IV ở nhóm riêng nên luôn
    bắt đầu trang kế (không dồn IV chung trang với III)."""
    d = data.report_date.strftime("%d/%m/%Y")
    dd_mm = data.report_date.strftime("%d/%m")
    phys_dd_mm = (data.physical_curr_date or data.report_date).strftime("%d/%m")

    # Nhóm 1 — Section I + II (bảng nhỏ, giữ nguyên khối)
    g_top = [
        f'<h2 class="section">I. Giá cao su thiên nhiên thế giới ngày {d}</h2>' + _world_table(data),
        '<h2 class="section">II. Giá các sản phẩm cao su giao ngay:</h2>' + _physical_table(data),
    ]

    # Nhóm 2 — Section III (giá sàn = bảng tách-dòng để không tràn + mủ nguyên liệu)
    fp = _floor_parts(data)
    iii = '<h2 class="section">III. Giá cao su trong nước:</h2>'
    g_local: list = []
    if fp:
        ref = _floor_ref(data)
        pre = iii + (
            f'<p class="sub">1. Giá sàn Tập đoàn {ref}: Giá xuất khẩu FOB/FCA (USD/T) cảng '
            "Tp.HCM và giá bán Nội địa (VNĐ/tấn) giao hàng tại kho.</p>"
        )
        g_local.append(_table_item(pre, fp[0], fp[1]))
    else:
        g_local.append(iii)
    rm_lines = _raw_material_lines(data)
    if rm_lines:
        g_local.append(
            '<p class="sub">2. Giá mủ nguyên liệu (do các đơn vị thành viên cung cấp) '
            "- đồng/độ TSC:</p>" + rm_lines
        )

    # Nhóm 3 — Section IV (nhóm riêng → luôn bắt đầu trang mới; tràn nhiều trang khi dài).
    g_news: list[str] = []
    head_iv = '<h2 class="section">IV. Các thông tin thị trường liên quan:</h2>'
    ex = [s for s in data.market_exchange_summary if s]
    b1 = head_iv + f'<p class="sub">1. Giá cao su {dd_mm} trên các sàn giao dịch thế giới:</p>'
    b1 += _bullets(ex) if ex else '<p class="note">Chưa có dữ liệu giá thế giới.</p>'
    g_news.append(b1)

    if data.market_physical_summary:
        g_news.append(
            f'<p class="sub">2. Giá Physical {phys_dd_mm}:</p>'
            + _bullets([data.market_physical_summary])
        )
    else:
        g_news.append(f'<p class="sub">2. Giá Physical {phys_dd_mm}: không có giá giao dịch.</p>')

    analysis = [a for a in data.market_analysis if a]
    if analysis:
        # "3." heading dính với đoạn đầu (không mồ côi); các đoạn sau tách block để tràn trang.
        g_news.append(
            '<p class="sub">3. Các thông tin có liên quan:</p>' + _bullets([analysis[0]])
        )
        for a in analysis[1:]:
            g_news.append(_bullets([a]))

    urls = [u for u in data.source_urls if u]
    if urls:
        g_news.append('<p class="src"><b>Nguồn tin:</b> ' + "; ".join(urls) + "</p>")

    return [g_top, g_local, g_news]


def measure_html(items: list) -> str:
    """HTML để Chromium đo chiều cao từng item (cùng bề rộng nội dung với trang thật).
    Bảng dict → đo riêng tiêu đề (.mt-pre) + thead + từng dòng để tách trang chính xác."""
    parts = []
    for it in items:
        if isinstance(it, dict):
            rows = "".join(it["rows"])
            parts.append(
                f"<div class='mitem'><div class='mt-pre'>{it['pre']}</div>"
                f"<table class='floor'>{it['head']}<tbody>{rows}</tbody></table></div>"
            )
        else:
            parts.append(f"<div class='mitem'>{it}</div>")
    inner = "".join(parts)
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{_CONTENT_CSS}</style>"
            f"</head><body><div class='measure'>{inner}</div></body></html>")


def pages_html(pages: list[list[str]], data: BulletinData, assets: dict[str, str] | None = None) -> str:
    """Ghép các trang đã xếp block → HTML cuối (mỗi trang = header + body + footer)."""
    assets = assets or {}
    hdr, ftr = _page_header(data, assets), _page_footer(data, assets)

    def page(blocks: list[str]) -> str:
        inner = "".join(f"<div class='blk'>{b}</div>" for b in blocks)
        return f"<div class='pg'>{hdr}<div class='pg-body'>{inner}</div>{ftr}</div>"

    body = "".join(page(p) for p in pages if p)
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{_CONTENT_CSS}</style>"
            f"</head><body>{body}</body></html>")


def content_html(data: BulletinData, assets: dict[str, str] | None = None) -> str:
    """Fallback không đo: mỗi NHÓM = 1 trang (pdf_export bình thường dùng đường measure-and-pack)."""
    pages = [[item_html(it) for it in g] for g in content_groups(data)]
    return pages_html(pages, data, assets or {})


# ── Bìa đầu / cuối (full trang, không header/footer) ──
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
    """Bìa đầu — ĐẶT NGÀY vào ô xanh đậm đã in sẵn trên ảnh bìa (x≈74.7–98.2%, y≈40–54%)."""
    img = assets.get("cover-front")
    bg = f"background-image:url('{img}');" if img else "background:#0b6b3a;"
    d = data.report_date.strftime("%d/%m/%Y")
    css = (
        f"@page{{size:{PAGE_W} {PAGE_H};margin:0;}}html,body{{margin:0;height:100%;}}"
        f".pg{{width:{PAGE_W};height:{PAGE_H};" + bg + "background-size:cover;background-position:center;"
        "position:relative;font-family:Arial,sans-serif;}"
        ".date-box{position:absolute;left:74.7%;right:1.8%;top:40%;height:13.5%;"
        "display:flex;align-items:center;justify-content:center;color:#fff;"
        "font-weight:700;font-size:25px;letter-spacing:.5px;}"
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style>"
            f"</head><body><div class='pg'><div class='date-box'>{d}</div></div></body></html>")


def back_html(data: BulletinData, assets: dict[str, str]) -> str:
    return _cover(assets.get("cover-back"), "", "")
