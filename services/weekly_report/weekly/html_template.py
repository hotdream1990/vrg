"""Dựng HTML ruột Báo cáo tuần → PDF (Chromium), bám mẫu 'BÁO CÁO PHÂN TÍCH THỊ TRƯỜNG CAO SU TUẦN'.

- Khổ A4 (595.32 x 842.04 pt). Mỗi trang = 1 `.pg` (header xanh + body + footer), header/footer
  nướng sẵn mỗi trang; ruột chia block, measure-and-pack ở pdf_export → Phần III/IV dài tự tràn.
- Bố cục nhóm: (I+II) · (III) · (IV) · (V+VI) · (Lời cảm ơn + Khuyến cáo boilerplate).
- Bìa/back = ảnh collage + đường cây cao su (trích từ mẫu), full trang, không header/footer.
- Số theo mẫu: 2.740,5 (chấm nghìn, phẩy thập phân); +/- kế toán (âm trong ngoặc); % có dấu -.
"""

from __future__ import annotations

from .models import WeeklyReportData

PAGE_W, PAGE_H = "8.27in", "11.69in"  # A4
# Body dùng được/trang (px CSS): 11.69in*96(≈1122) − header 76 − footer 16 − padding ~20, chừa slack.
USABLE_PX = 985


# ── Định dạng số kiểu Việt Nam (chấm nghìn, phẩy thập phân) ──
def _vn(x: float, dec: int = 1) -> str:
    """abs(x) → '2.740,5' (dec chữ số thập phân). Không kèm dấu."""
    s = f"{abs(x):,.{dec}f}"                      # 2,740.5
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _price(x: float | None, dec: int = 1) -> str:
    return _vn(x, dec) if x is not None else "N/A"


def _acc(x: float | None, dec: int = 1) -> str:
    """Cột +/- kiểu kế toán: âm trong ngoặc '(83,2)', dương '19,2', 0 → '0'."""
    if x is None:
        return ""
    if round(x, dec) == 0:
        return "0"
    return f"({_vn(x, dec)})" if x < 0 else _vn(x, dec)


def _pct(x: float | None, dec: int = 2) -> str:
    if x is None:
        return ""
    return f"-{_vn(x, dec)}%" if x < 0 else f"{_vn(x, dec)}%"


_EXCHANGE_GROUPS = [
    ("OSE", ["RSS3"]),
    ("SHANGHAI", ["RSS3"]),
    ("SGX", ["RSS3", "TSR20"]),
    ("MRE", ["SMR CV", "SMR20", "LATEX"]),
]
_PHYS_ROWS = ["RSS3", "STR20", "SMR20", "LATEX"]


_CSS = f"""
* {{ box-sizing:border-box; }}
html,body {{ margin:0; }}
body {{ font-family:'Times New Roman','Arial',sans-serif; color:#111; font-size:13.5px; }}
.pg {{ width:{PAGE_W}; height:{PAGE_H}; display:flex; flex-direction:column; overflow:hidden; break-after:page; }}
.pg:last-child {{ break-after:auto; }}
.pg-body {{ flex:1; padding:14px 30px 6px; overflow:hidden; }}
.measure {{ width:{PAGE_W}; padding:0 30px; }}
.blk {{ display:flow-root; }}

/* Header = letterhead nền TRẮNG (như mẫu): logo nhỏ + tiêu đề chữ gradient teal→lá + gạch chân gradient. */
.pg-hdr {{ position:relative; width:100%; height:76px; flex:0 0 auto; background:#fff;
  display:flex; align-items:center; padding:10px 30px 0; }}
.pg-hdr-logo {{ height:46px; width:46px; border-radius:50%; object-fit:contain; margin-right:10px; flex:0 0 auto; }}
.pg-hdr-t {{ font-family:Arial,sans-serif; font-size:21px; font-weight:800; letter-spacing:.3px;
  background:linear-gradient(90deg,#134f67 0%,#2f8f57 55%,#43a83a 100%);
  -webkit-background-clip:text; background-clip:text; color:transparent; }}
.pg-hdr-rule {{ position:absolute; left:86px; right:30px; bottom:12px; height:3px;
  background:linear-gradient(90deg,#134f67,#43a83a); }}
/* Mẫu KHÔNG có footer band — chỉ chừa lề đáy. */
.pg-ftr {{ height:16px; flex:0 0 auto; }}
/* Masthead đầu trang nội dung (1 lần): tiêu đề + Ban + kẻ ngang. */
.masthead {{ margin:2px 0 6px; }}
.mh-title {{ font-family:'Times New Roman',serif; font-weight:700; font-size:17px; color:#111; }}
.mh-sub {{ font-family:'Times New Roman',serif; font-weight:700; font-size:14px; color:#1a7a3a; margin-top:1px; }}
.mh-rule {{ border:0; border-top:2px solid #17667a; margin:7px 0 2px; }}

h2.section {{ font-size:15px; color:#0a9e48; margin:8px 0 6px; font-weight:700; }}
p.sub {{ font-weight:700; margin:8px 0 4px; line-height:1.45; }}
p.para {{ margin:6px 0; line-height:1.5; text-align:justify; text-indent:28px; }}
table {{ width:100%; border-collapse:collapse; margin:4px 0 8px; }}
thead {{ display:table-header-group; }}
th,td {{ border:1px solid #7f9c86; padding:7px 8px; font-size:13px; }}
th {{ background:#dbe7cf; color:#0a3d1e; text-align:center; font-weight:700; }}
td.r {{ text-align:right; }} td.c {{ text-align:center; }}
ul.blt {{ margin:3px 0 8px; padding-left:22px; }}
ul.blt li {{ margin:4px 0; line-height:1.5; text-align:justify; }}
ul.blt ul {{ list-style:circle; margin:2px 0; padding-left:22px; }}
ul.blt ul li {{ font-style:italic; }}
ol.disc {{ margin:4px 0; padding-left:22px; }} ol.disc li {{ margin:6px 0; line-height:1.5; text-align:justify; }}
.note {{ color:#999; font-style:italic; }}
"""


# ── Bảng III.1 — Giá sàn quốc tế ──
def _exchange_table(d: WeeklyReportData) -> str:
    m = {(r.exchange, r.grade): r for r in d.exchange_rows}
    head = (
        "<thead><tr><th>Sàn giao dịch</th><th>Sản phẩm</th>"
        f"<th>{d.prev_col_label}</th><th>{d.curr_col_label}</th>"
        "<th>+/-</th><th>% Thay đổi</th></tr></thead>"
    )
    body = ""
    for exc, grades in _EXCHANGE_GROUPS:
        for j, g in enumerate(grades):
            r = m.get((exc, g))
            lead = f"<td class='c' rowspan='{len(grades)}'>{exc}</td>" if j == 0 else ""
            body += (
                f"<tr>{lead}<td class='c'>{g}</td>"
                f"<td class='r'>{_price(r.prev if r else None)}</td>"
                f"<td class='r'>{_price(r.curr if r else None)}</td>"
                f"<td class='r'>{_acc(r.change_abs if r else None)}</td>"
                f"<td class='r'>{_pct(r.change_pct if r else None, 2)}</td></tr>"
            )
    return f"<table>{head}<tbody>{body}</tbody></table>"


# ── Bảng III.2 — Giá giao ngay ──
def _physical_table(d: WeeklyReportData) -> str:
    m = {r.grade: r for r in d.physical_rows}
    head = (
        "<thead><tr><th>Sản phẩm</th>"
        f"<th>{d.prev_col_label}</th><th>{d.curr_col_label}</th>"
        "<th>+/-</th><th>% Thay đổi</th></tr></thead>"
    )
    body = ""
    for g in _PHYS_ROWS:
        r = m.get(g)
        body += (
            f"<tr><td class='c'>{g}</td>"
            f"<td class='r'>{_price(r.prev if r else None, 0)}</td>"
            f"<td class='r'>{_price(r.curr if r else None, 0)}</td>"
            f"<td class='r'>{_acc(r.change_abs if r else None)}</td>"
            f"<td class='r'>{_pct(r.change_pct if r else None, 1)}</td></tr>"
        )
    return f"<table>{head}<tbody>{body}</tbody></table>"


# ── Bảng III.3 — Mủ nước ──
def _latex_table(d: WeeklyReportData) -> str:
    return (
        "<table><thead><tr><th>Sản phẩm</th>"
        f"<th>Tuần {d.prev_week_no}</th><th>Tuần {d.week_no}</th><th>Biến động</th></tr></thead>"
        f"<tbody><tr><td class='c'>Mủ nước</td><td class='c'>{d.latex_prev or 'N/A'}</td>"
        f"<td class='c'>{d.latex_curr or 'N/A'}</td><td class='c'>{d.latex_change or ''}</td></tr></tbody></table>"
    )


# ── Bullet 2 cấp: dòng bắt đầu '>' = gạch phụ (○, in nghiêng) ──
def _bullets(items: list[str]) -> str:
    out, sub = "", ""
    def flush():
        nonlocal sub
        s = f"<ul>{sub}</ul>" if sub else ""
        sub = ""
        return s
    for s in items:
        if not s:
            continue
        if s.startswith(">"):
            sub += f"<li>{s[1:].strip()}</li>"
        else:
            out += flush() + f"<li>{s}</li>"
    out += flush()
    return f"<ul class='blt'>{out}</ul>" if out else ""


def _paras(items: list[str]) -> str:
    return "".join(f"<p class='para'>{s}</p>" for s in items if s)


def _notes(label: str, items: list[str]) -> str:
    return (f"<p class='sub'>{label}</p>" + _bullets(items)) if items else ""


# ── Header/footer nướng mỗi trang ──
def _page_header(assets: dict[str, str]) -> str:
    logo = assets.get("logo-vrg")
    lg = f"<img class='pg-hdr-logo' src='{logo}'/>" if logo else ""
    return (f"<div class='pg-hdr'>{lg}"
            "<div class='pg-hdr-t'>BÁO CÁO PHÂN TÍCH VỀ THỊ TRƯỜNG CAO SU</div>"
            "<div class='pg-hdr-rule'></div></div>")


def _page_footer(assets: dict[str, str]) -> str:
    return "<div class='pg-ftr'></div>"  # mẫu không có footer band — chỉ lề đáy


_MASTHEAD = (
    "<div class='masthead'><div class='mh-title'>BÁO CÁO PHÂN TÍCH VỀ THỊ TRƯỜNG CAO SU</div>"
    "<div class='mh-sub'>Ban Thị trường - Kinh doanh</div><hr class='mh-rule'></div>"
)


# ── Các nhóm block ──
def content_groups(d: WeeklyReportData) -> list[list[str]]:
    # Nhóm 1 — masthead (1 lần) + I + II
    g1 = [
        _MASTHEAD + f'<h2 class="section">I. TÓM TẮT TUẦN {d.prev_week_no}/{d.prev_year}</h2>' + _paras(d.summary_prev),
        f'<h2 class="section">II. DIỄN BIẾN TUẦN {d.week_no}/{d.year}</h2>' + _paras(d.movement),
    ]
    # Nhóm 2 — III (3 bảng + nhận định)
    g3: list[str] = [
        '<h2 class="section">III. DIỄN BIẾN GIÁ</h2>'
        '<p class="sub">1. Giá trên các sàn giao dịch quốc tế (USD/tấn):</p>'
        + _exchange_table(d) + _notes("Nhận định:", d.exchange_notes),
        '<p class="sub">2. Giá thị trường giao ngay (USD/tấn):</p>'
        + _physical_table(d) + _notes("Nhận định:", d.physical_notes),
        '<p class="sub">3. Giá thu mua mủ nước (VNĐ/độ TSC):</p>'
        + _latex_table(d) + _notes("Nhận định:", d.latex_notes),
    ]
    # Nhóm 3 — IV (tiểu mục)
    g4 = [f'<h2 class="section">IV. CÁC YẾU TỐ VĨ MÔ</h2>']
    for sec in d.macro:
        g4.append(f'<p class="sub">{sec.title}</p>' + _bullets(sec.bullets))
    # gộp heading IV với tiểu mục đầu để không mồ côi
    if len(g4) > 1:
        g4 = [g4[0] + g4[1]] + g4[2:]
    # Nhóm 4 — V + VI
    g5 = [
        f'<h2 class="section">V. DỰ BÁO XU HƯỚNG TUẦN {d.next_week_no}/{d.next_year}</h2>' + _paras_or_bullets(d.forecast),
        '<h2 class="section">VI. KẾT LUẬN VÀ KHUYẾN NGHỊ</h2>' + _paras(d.conclusion),
    ]
    # Nhóm 5 — Lời cảm ơn + Khuyến cáo (boilerplate)
    g6 = [_acknowledgement(), _disclaimer()]
    return [g1, g3, g4, g5, g6]


def _paras_or_bullets(items: list[str]) -> str:
    """Dòng bắt đầu '-' → bullet; còn lại → đoạn văn (Phần V có cả 2)."""
    paras = [s for s in items if s and not s.startswith("-")]
    bl = [s[1:].strip() for s in items if s.startswith("-")]
    return _paras(paras) + _bullets(bl)


_ACK = [
    "Ban biên Tập bản tin thị trường của Ban Thị trường Kinh doanh chân thành cảm ơn Hiệp hội các "
    "quốc gia sản xuất cao su thiên nhiên (ANRPC) đã cung cấp thông tin cập nhật thường xuyên, kịp "
    "thời thông qua tổ thư ký thành viên ANRPC và Hiệp hội cao su Việt Nam.",
    "Cảm ơn các Công ty thành viên của Tập Đoàn cao su Việt Nam đã cung cấp thông tin thị trường và "
    "giao dịch trong nước góp phần phong phú thêm cho nội dung bản tin cũng như cổ vũ và ủng hộ bản "
    "tin ngày càng chất lượng hơn.",
]
_DISCLAIMER = [
    "Các thông tin, tuyên bố, dự đoán trong bản báo cáo này, bao gồm cả các nhận định cá nhân, là "
    "dựa trên các nguồn thông tin tin cậy, tuy nhiên VRG không đảm bảo sự chính xác và đầy đủ của các "
    "nguồn thông tin này. Các nhận định trong bản báo cáo này được đưa ra dựa trên cơ sở phân tích chi "
    "tiết và cẩn thận, theo đánh giá chủ quan của chúng tôi, là hợp lý trong thời điểm đưa ra báo cáo. "
    "Các nhận định trong báo cáo này có thể thay đổi bất kì lúc nào mà không báo trước. VRG sẽ không "
    "chịu trách nhiệm đối với tất cả hay bất kỳ thiệt hại nào hay sự kiện bị coi là thiệt hại đối với "
    "việc sử dụng toàn bộ hay bất kỳ thông tin hoặc ý kiến nào của báo cáo này.",
    "Bản tin chỉ cung cấp cho lãnh đạo Tập Đoàn và các đơn vị thành viên để theo dõi xu hướng của thị "
    "trường và chỉ được lưu hành nội bộ.",
    "VRG nghiêm cấm việc sử dụng, và mọi sự in ấn, sao chép hay xuất bản toàn bộ hay từng phần bản Báo "
    "cáo này vì bất kỳ mục đích gì mà không có sự chấp thuận của VRG.",
]


def _acknowledgement() -> str:
    return '<h2 class="section">LỜI CẢM ƠN</h2>' + _paras(_ACK)


def _disclaimer() -> str:
    lis = "".join(f"<li>{s}</li>" for s in _DISCLAIMER)
    return f'<h2 class="section">KHUYẾN CÁO</h2><ol class="disc">{lis}</ol>'


def measure_html(blocks: list[str]) -> str:
    inner = "".join(f"<div class='blk'>{b}</div>" for b in blocks)
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{_CSS}</style>"
            f"</head><body><div class='measure'>{inner}</div></body></html>")


def pages_html(pages: list[list[str]], assets: dict[str, str] | None = None) -> str:
    assets = assets or {}
    hdr, ftr = _page_header(assets), _page_footer(assets)

    def page(blocks: list[str]) -> str:
        inner = "".join(f"<div class='blk'>{b}</div>" for b in blocks)
        return f"<div class='pg'>{hdr}<div class='pg-body'>{inner}</div>{ftr}</div>"

    body = "".join(page(p) for p in pages if p)
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{_CSS}</style>"
            f"</head><body>{body}</body></html>")


# ── Bìa đầu / cuối ──
def cover_html(d: WeeklyReportData, assets: dict[str, str]) -> str:
    """Bìa collage; overlay nhãn tuần (band trắng) đè lên nhãn in sẵn ở mẫu."""
    img = assets.get("cover-front")
    bg = f"background-image:url('{img}');" if img else "background:#0b6b3a;"
    label = f"Tuần {d.week_no} năm {d.year} từ {d.date_range}"
    css = (
        f"@page{{size:{PAGE_W} {PAGE_H};margin:0;}}html,body{{margin:0;height:100%;}}"
        f".pg{{width:{PAGE_W};height:{PAGE_H};" + bg + "background-size:cover;background-position:center;"
        "position:relative;font-family:'Times New Roman',serif;}"
        # Band trắng phủ hẳn dải đáy (đè nhãn tuần in sẵn trong ảnh mẫu) rồi in lại nhãn động.
        ".wk{position:absolute;left:0;right:0;bottom:1.5%;height:9%;background:#fff;"
        "display:flex;align-items:flex-start;justify-content:center;padding-top:1.2%;color:#0a3d1e;"
        "font-weight:700;font-style:italic;font-size:18px;}"
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style>"
            f"</head><body><div class='pg'><div class='wk'>{label}</div></div></body></html>")


def back_html(assets: dict[str, str]) -> str:
    img = assets.get("cover-back")
    bg = f"background-image:url('{img}');" if img else "background:#0b6b3a;"
    css = (
        f"@page{{size:{PAGE_W} {PAGE_H};margin:0;}}html,body{{margin:0;height:100%;}}"
        f".pg{{width:{PAGE_W};height:{PAGE_H};" + bg + "background-size:cover;background-position:center;}"
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style>"
            f"</head><body><div class='pg'></div></body></html>")
