"""Dựng HTML ruột Báo cáo tuần → PDF (Chromium), bám mẫu 'BÁO CÁO PHÂN TÍCH THỊ TRƯỜNG CAO SU TUẦN'.

- Khổ A4 (595.32 x 842.04 pt). Mỗi trang = 1 `.pg` (header xanh + body + footer), header/footer
  nướng sẵn mỗi trang; ruột chia block NHỎ, measure-and-pack ở pdf_export → phần dài tự tràn,
  không block nào cao quá 1 trang (tránh bị overflow:hidden cắt chữ).
- Bảng III mọi kỳ (1–3 tuần) bám mẫu tuần 35–36; kỳ gộp đổi thêm nhãn — xem html_tables.py.
- Chữ narrative: escape + **đậm**/*nghiêng* + gạch 3 cấp — xem text_format.py.
- Bìa/back = ảnh collage + đường cây cao su (trích từ mẫu), full trang, không header/footer.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

from . import html_tables as TB
from . import text_format as TF
from .models import WeeklyReportData

PAGE_W, PAGE_H = "8.27in", "11.69in"  # A4

# ── Font NHÚNG (OFL/Apache-2.0) — làm PDF hiển thị GIỐNG NHAU trên mọi máy ──
# Tinos ~ Times New Roman, Arimo ~ Arial (cùng metric → không lệch bố cục), phủ đủ tiếng Việt.
# Nhúng qua data-URI để Chromium embed vào PDF, KHÔNG phụ thuộc font hệ thống của máy render.
# Không có file Tinos Bold Italic: họ 'TinosBI' = Tinos-Bold chỉ khai kiểu thẳng → Chromium tự NGHIÊNG
# (skew) nét đậm thật. Nếu để Chromium tự ĐẬM từ Tinos-Italic thì ra font Type 3, chữ Việt nhoè/lệch.
_FONTS_DIR = Path(__file__).parent / "fonts"
_FONT_FILES = [
    ("Tinos", 400, "normal", "Tinos-Regular.ttf"),
    ("Tinos", 700, "normal", "Tinos-Bold.ttf"),
    ("Tinos", 400, "italic", "Tinos-Italic.ttf"),
    ("TinosBI", 700, "normal", "Tinos-Bold.ttf"),
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
# Body dùng được/trang (px CSS): 11.69in*96(≈1122) − header 76 − footer 16 − padding ~20 ≈ 1010; chừa ~15 slack.
USABLE_PX = 995


_CSS = f"""
{_FONT_FACE_CSS}
* {{ box-sizing:border-box; }}
/* Lề văn bản chuẩn VN: trái 3cm, phải 2cm (bám mẫu). */
:root {{ --ml:3cm; --mr:2cm; }}
html,body {{ margin:0; }}
body {{ font-family:'Tinos','Times New Roman',serif; color:#111; font-size:13.5px; }}
.pg {{ width:{PAGE_W}; height:{PAGE_H}; display:flex; flex-direction:column; overflow:hidden; break-after:page; }}
.pg:last-child {{ break-after:auto; }}
.pg-body {{ flex:1; padding:14px var(--mr) 6px var(--ml); overflow:hidden; }}
.measure {{ width:{PAGE_W}; padding:0 var(--mr) 0 var(--ml); }}
.blk {{ display:flow-root; }}

/* Header = letterhead nền TRẮNG (như mẫu): logo nhỏ + tiêu đề + gạch chân gradient. */
.pg-hdr {{ position:relative; width:100%; height:76px; flex:0 0 auto; background:#fff;
  display:flex; align-items:center; padding:10px var(--mr) 0 var(--ml); }}
.pg-hdr-logo {{ height:46px; width:46px; border-radius:50%; object-fit:contain; margin-right:10px; flex:0 0 auto; }}
/* Màu XANH ĐẶC (không dùng background-clip:text — nhiều trình xem PDF, vd macOS Preview,
   render text-clip gradient thành khối đặc che chữ). Bám mẫu: tiêu đề xanh đậm. */
.pg-hdr-t {{ font-family:'Arimo',Arial,sans-serif; font-size:21px; font-weight:800; letter-spacing:.3px;
  color:#1a7a3a; }}
.pg-hdr-rule {{ position:absolute; left:calc(var(--ml) + 56px); right:var(--mr); bottom:12px; height:3px;
  background:linear-gradient(90deg,#134f67,#43a83a); }}
/* Mẫu KHÔNG có footer band — chỉ chừa lề đáy. */
.pg-ftr {{ height:16px; flex:0 0 auto; }}
/* Masthead đầu trang nội dung (1 lần): tiêu đề · kỳ · Ban · ghi chú kỳ · kẻ ngang. */
.masthead {{ margin:2px 0 6px; }}
.mh-title {{ font-weight:700; font-size:17px; color:#111; }}
.mh-period {{ font-weight:700; font-size:14.5px; color:#111; margin-top:2px; }}
.mh-sub {{ font-weight:700; font-size:14px; color:#1a7a3a; margin-top:1px; }}
.mh-note {{ margin:4px 0 0; line-height:1.4; text-align:justify; }}
.mh-rule {{ border:0; border-top:2px solid #17667a; margin:7px 0 2px; }}

h2.section {{ font-size:15px; color:#0a9e48; margin:6px 0 4px; font-weight:700; }}
p.sub {{ font-weight:700; margin:6px 0 3px; line-height:1.4; }}
p.para {{ margin:5px 0; line-height:1.45; text-align:justify; text-indent:28px; }}
table {{ width:100%; border-collapse:collapse; margin:3px 0 6px; }}
thead {{ display:table-header-group; }}
th,td {{ border:1px solid #7f9c86; padding:6px 8px; font-size:13px; }}
th {{ background:#dbe7cf; color:#0a3d1e; text-align:center; font-weight:700; line-height:1.25; }}
td.r {{ text-align:right; white-space:nowrap; }} td.c {{ text-align:center; white-space:nowrap; }}
th.nw {{ white-space:nowrap; }} td.b {{ font-weight:700; }}
/* Kỳ gộp: nhiều cột → co chữ + bớt đệm để vừa khổ A4 lề 3cm/2cm. */
table.tw3 th, table.tw3 td {{ font-size:12.5px; padding:5px 5px; }}
table.tw4 th, table.tw4 td {{ font-size:11.5px; padding:4px 3px; }}
.tnote {{ margin:-2px 0 6px; }}
.tnote p {{ margin:2px 0; line-height:1.4; text-align:justify; font-style:italic; }}
ul.blt {{ margin:2px 0 6px; padding-left:22px; list-style:disc; }}
ul.blt li {{ margin:3px 0; line-height:1.45; text-align:justify; }}
ul.blt ul {{ list-style:circle; margin:2px 0; padding-left:22px; }}
ul.blt ul ul {{ list-style:square; }}
ul.blt ul ul li::marker {{ font-size:.8em; }}
b i, i b {{ font-family:'TinosBI','Tinos','Times New Roman',serif; font-weight:700; font-style:italic; }}
ol.disc {{ margin:4px 0; padding-left:22px; }} ol.disc li {{ margin:6px 0; line-height:1.5; text-align:justify; }}
"""


# ── Header/footer nướng mỗi trang ──
def _page_header(assets: dict[str, str]) -> str:
    logo = assets.get("logo-vrg")
    lg = f"<img class='pg-hdr-logo' src='{logo}'/>" if logo else ""
    return (f"<div class='pg-hdr'>{lg}"
            "<div class='pg-hdr-t'>BÁO CÁO PHÂN TÍCH VỀ THỊ TRƯỜNG CAO SU</div>"
            "<div class='pg-hdr-rule'></div></div>")


def _page_footer(assets: dict[str, str]) -> str:
    return "<div class='pg-ftr'></div>"  # mẫu không có footer band — chỉ lề đáy


def _masthead(d: WeeklyReportData) -> str:
    note = [s for s in d.report_note if s and s.strip()]
    note_html = ""
    if note:
        note_html = (f"<p class='mh-note'><b><i>Ghi chú:</i></b> <i>{TF.fmt_inline(note[0])}</i></p>"
                     + "".join(f"<p class='mh-note'><i>{TF.fmt_inline(s)}</i></p>" for s in note[1:]))
    period = html.escape(f"{d.title_label}: {d.date_range}")
    return ("<div class='masthead'><div class='mh-title'>BÁO CÁO PHÂN TÍCH VỀ THỊ TRƯỜNG CAO SU</div>"
            f"<div class='mh-period'>{period}</div>"
            f"<div class='mh-sub'>Ban Thị trường - Kinh doanh</div>{note_html}<hr class='mh-rule'></div>")


def _section(title: str) -> str:
    return f'<h2 class="section">{html.escape(title)}</h2>'


def _with_head(head: str, blocks: list[str]) -> list[str]:
    """Gắn tiêu đề vào block đầu (tiêu đề không mồ côi cuối trang)."""
    return [head + blocks[0]] + blocks[1:] if blocks else [head]


# ── Các nhóm block ──
def content_groups(d: WeeklyReportData) -> list[list[str]]:
    label = "<p class='sub'>Nhận định:</p>"
    # Nhóm 1 — masthead (1 lần) + I + II (mỗi đoạn 1 block)
    g1 = _with_head(_masthead(d) + _section(f"I. TÓM TẮT {d.prev_label.upper()}"), TF.paras(d.summary_prev))
    g1 += _with_head(_section(f"II. DIỄN BIẾN {d.movement_label.upper()}"), TF.paras(d.movement))
    # Nhóm 2 — III: bảng (+ ghi chú dưới bảng) tách khỏi nhận định; nhận định chia theo cụm sàn.
    g3 = ['<h2 class="section">III. DIỄN BIẾN GIÁ</h2>'
          '<p class="sub">1. Giá trên các sàn giao dịch quốc tế (USD/tấn):</p>'
          + TB.exchange_table(d) + TB.table_notes(d.exchange_gaps, d.exchange_table_notes)]
    g3 += TF.note_blocks(label, d.exchange_notes)
    g3.append('<p class="sub">2. Giá thị trường giao ngay (USD/tấn):</p>'
              + TB.physical_table(d) + TB.table_notes(d.physical_gaps, d.physical_table_notes))
    g3 += TF.note_blocks(label, d.physical_notes)
    if TB.has_latex(d):
        g3.append('<p class="sub">3. Giá thu mua mủ nước (VNĐ/độ TSC):</p>' + TB.latex_table(d))
        g3 += TF.note_blocks(label, d.latex_notes)
    # Nhóm 3 — IV: mỗi tiểu mục chia cụm; tiêu đề IV dính tiểu mục đầu.
    g4: list[str] = []
    for sec in d.macro:
        title = f"<p class='sub'>{TF.fmt_inline(sec.title)}</p>"
        g4 += TF.note_blocks(title, sec.bullets) or [title]
    g4 = _with_head(_section("IV. CÁC YẾU TỐ VĨ MÔ ẢNH HƯỞNG"), g4)
    # Nhóm 4 — V + VI
    g5 = _with_head(_section(f"V. DỰ BÁO XU HƯỚNG {d.next_label.upper()}"), TF.paras_or_bullets(d.forecast))
    g5 += _with_head(_section("VI. KẾT LUẬN VÀ KHUYẾN NGHỊ"), TF.paras(d.conclusion))
    # Nhóm 5 — Lời cảm ơn + Khuyến cáo (boilerplate)
    g6 = [_acknowledgement(), _disclaimer()]
    return [g1, g3, g4, g5, g6]


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
    return '<h2 class="section">LỜI CẢM ƠN</h2>' + "".join(TF.paras(_ACK))


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
_COVER_FONT_PX = 18
_COVER_FIT_CHARS = 60  # quá số ký tự này thì co chữ tỉ lệ (kỳ gộp nhãn dài)


def cover_html(d: WeeklyReportData, assets: dict[str, str]) -> str:
    """Bìa collage; overlay nhãn kỳ (band trắng) đè lên nhãn in sẵn ở mẫu."""
    img = assets.get("cover-front")
    bg = f"background-image:url('{img}');" if img else "background:#0b6b3a;"
    label = f"{d.title_label} từ {d.date_range}"
    size = max(12.0, min(_COVER_FONT_PX, _COVER_FONT_PX * _COVER_FIT_CHARS / max(len(label), 1)))
    css = (
        _FONT_FACE_CSS
        + f"@page{{size:{PAGE_W} {PAGE_H};margin:0;}}html,body{{margin:0;height:100%;}}"
        f".pg{{width:{PAGE_W};height:{PAGE_H};" + bg + "background-size:cover;background-position:center;"
        "position:relative;font-family:'TinosBI','Tinos','Times New Roman',serif;}"
        # Band trắng phủ hẳn dải đáy (đè nhãn tuần in sẵn trong ảnh mẫu) rồi in lại nhãn động.
        ".wk{position:absolute;left:0;right:0;bottom:1.5%;height:9%;background:#fff;"
        "display:flex;align-items:flex-start;justify-content:center;padding:1.2% 6% 0;color:#0a3d1e;"
        f"font-weight:700;font-style:italic;font-size:{size:.1f}px;text-align:center;white-space:nowrap;}}"
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style>"
            f"</head><body><div class='pg'><div class='wk'>{html.escape(label)}</div></div></body></html>")


def back_html(assets: dict[str, str]) -> str:
    img = assets.get("cover-back")
    bg = f"background-image:url('{img}');" if img else "background:#0b6b3a;"
    css = (
        f"@page{{size:{PAGE_W} {PAGE_H};margin:0;}}html,body{{margin:0;height:100%;}}"
        f".pg{{width:{PAGE_W};height:{PAGE_H};" + bg + "background-size:cover;background-position:center;}"
    )
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style>"
            f"</head><body><div class='pg'></div></body></html>")
