"""Hình DỰ THẢO GIÁ SÀN ĐIỀU CHỈNH — bảng giá cũ / điều chỉnh / chênh lệch (FOB + VNĐ) kèm tỷ giá VCB,
y như bảng Excel Ban TTKD vẫn chụp gửi lãnh đạo. HTML này được Chromium chụp thành PNG ([doc_render])
để người dùng chép thẳng vào Zalo/email. Thứ tự chủng loại = phương án (KHÔNG sort).
"""
from __future__ import annotations

from html import escape

from app.services.to_trinh import vn

#: Tên chủng loại trên hình dự thảo (theo bảng mẫu), khoá = khoá hệ thống của phương án.
SHEET_LABEL = {"SVR CV 50": "CV50", "SVR CV60": "CV60", "SVR L": "SVRL", "SVR 3L Mix": "SVR 3L Mix",
               "SVR 3L": "SVR 3L", "SVR 5S": "SVR 5S", "SVR 5": "SVR5", "SVR 10 Mix": "SVR10 Mix",
               "SVR 10 / CSR 10": "SVR10/CSR 10", "SVR 20 / CSR 20": "SVR20/CSR 20", "RSS 3": "RSS3",
               "RSS 1": "RSS1", "LATEX": "Latex", "Skim Block": "Skim Block"}
SELECTOR = "#du-thao"

_CSS = """
body { margin: 0; background: #fff; font-family: "Times New Roman", Tinos, Times, serif; color: #000; }
#du-thao { display: inline-block; padding: 10px 12px 12px; background: #fff; }
.t { text-align: center; font-weight: bold; font-size: 17px; margin-bottom: 2px; }
.s { text-align: center; font-style: italic; font-size: 14px; margin-bottom: 8px; }
table { border-collapse: collapse; font-size: 14.5px; }
th, td { border: 1px solid #000; padding: 2px 8px; }
th { font-weight: bold; text-align: center; }
th.cl { min-width: 128px; font-size: 15px; }
th.fob { background: #ddebf7; min-width: 86px; } th.vnd { background: #92d050; min-width: 112px; }
td.l { text-align: left; } td.r { text-align: right; }
td.foot { font-style: italic; border-left: none; border-right: none; border-bottom: none; padding-top: 4px; }
"""


def _num(n: float | None) -> str:
    return "" if n is None else (vn(n) if n >= 0 else f"-{vn(abs(n))}")


def _date(iso: str | None) -> str:
    """'2026-09-09' → '09/9/2026' (đúng kiểu ngày của bảng mẫu)."""
    if not iso:
        return "……"
    y, m, d = iso[:10].split("-")
    return f"{d}/{int(m)}/{y}"


def vcb_line(sheet: dict | None) -> str:
    s = sheet or {}
    rate = f"{vn(s['vcb_rate'])} đ" if s.get("vcb_rate") else "…… đ"
    at = f"lúc {s['vcb_time']} " if s.get("vcb_time") else ""
    return f"Tỷ giá VCB mua CK ngày lấy {at}ngày {_date(s.get('vcb_date'))}: {rate}"


def render(prop: dict, doc: dict, sheet: dict | None) -> str:
    """HTML hình dự thảo: lần thứ/ngày lấy từ ảnh chụp thị trường của bản nháp (`doc`)."""
    rows = []
    for r in prop.get("rows") or []:
        cells = [r.get("prev_fob"), r.get("fob"), r.get("fob_delta"), r.get("prev_vnd"), r.get("vnd"),
                 r.get("vnd_delta")]
        tds = "".join(f'<td class="r">{_num(v)}</td>' for v in cells)
        rows.append(f'<tr><td class="l">{escape(SHEET_LABEL.get(r["grade"], r.get("label") or r["grade"]))}</td>'
                    f"{tds}</tr>")
    sub = f'(Giá sàn lần thứ {doc["lan"]}/{doc["year"]} ngày {_date(doc["as_of"])})'
    return (f'<!doctype html><meta charset="utf-8"><style>{_CSS}</style><div id="du-thao">'
            '<div class="t">DỰ THẢO GIÁ SÀN ĐIỀU CHỈNH</div>'
            f'<div class="s">{sub}</div><table><thead>'
            '<tr><th rowspan="2" class="cl">CHỦNG<br>LOẠI</th><th colspan="3" class="fob">Giá FOB</th>'
            '<th colspan="3" class="vnd">Giá VNĐ</th></tr>'
            '<tr><th class="fob">GIÁ CŨ</th><th class="fob">ĐIỀU CHỈNH</th><th class="fob">+/-</th>'
            '<th class="vnd">GIÁ CŨ</th><th class="vnd">ĐIỀU CHỈNH</th><th class="vnd">+/-</th></tr></thead>'
            f'<tbody>{"".join(rows)}<tr><td colspan="7" class="foot">{escape(vcb_line(sheet))}</td></tr>'
            "</tbody></table></div>")
