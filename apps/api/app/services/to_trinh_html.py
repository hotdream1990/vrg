"""Render dữ liệu tờ trình (từ [to_trinh.build]) ra HTML chuẩn hành chính (A4, Times New Roman).

GIỮ NGUYÊN format + thứ tự bảng của mẫu `docs/ban hanh gia san/to-trinh-gia-san-mau.html`.
"""
from __future__ import annotations

from app.services.to_trinh import vn

_CSS = """
@page { size: A4 portrait; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: "Times New Roman", Times, serif; font-size: 13.5pt; color: #111; line-height: 1.45; margin: 0; background: #f3f4f6; }
.page { width: 210mm; min-height: 297mm; background: #fff; margin: 12px auto; padding: 18mm 16mm; box-shadow: 0 1px 6px rgba(0,0,0,.18); }
.hdr { width: 100%; border-collapse: collapse; }
.hdr td { vertical-align: top; text-align: center; width: 50%; }
.b { font-weight: bold; } .caps { text-transform: uppercase; } .it { font-style: italic; } .center { text-align: center; }
.u-sm { display: inline-block; border-bottom: 1.2px solid #111; width: 42%; margin-top: 2px; }
.u-wide { display: inline-block; border-bottom: 1.2px solid #111; width: 60%; margin: 1px 0 6px; }
.title .t1 { font-size: 16pt; font-weight: bold; letter-spacing: .5px; }
.sec { font-weight: bold; margin: 14px 0 6px; }
p.body { margin: 6px 0; text-align: justify; text-indent: 24px; }
table.data { width: 100%; border-collapse: collapse; margin: 4px 0 8px; font-size: 12pt; }
table.data th, table.data td { border: 1px solid #2a2a2a; padding: 4px 6px; text-align: center; }
table.data th { background: #eef0f7; font-weight: bold; }
table.data td.l { text-align: left; }
.neg { color: #b00; }
.signs { width: 100%; border-collapse: collapse; margin-top: 18px; text-align: center; }
.signs td { width: 50%; vertical-align: top; padding: 6px 4px 70px; }
.signs .role, .signs .name { font-weight: bold; }
"""

_MONTH = None


def _dmy(s: str | None) -> str:
    if not s:
        return "—"
    y, m, d = s.split("-")
    return f"{d}/{m}/{y[2:]}"


def _long_date(s: str) -> str:
    y, m, d = s.split("-")
    return f"ngày {int(d)} tháng {int(m)} năm {y}"


def _sgn(n) -> str:
    return "—" if n is None else (f"+{vn(n)}" if n > 0 else f"-{vn(abs(n))}" if n < 0 else "0")


def _sgn_pct(p) -> str:
    if p is None:
        return "—"
    s = f"{p:+}".replace(".", ",")
    return s


def _plain(n) -> str:
    return "" if n is None else (vn(n) if n >= 0 else f"-{vn(abs(n))}")


def _cell(v, cls=""):
    neg = isinstance(v, str) and v.startswith("-")
    return f'<td class="{cls}{" neg" if neg else ""}">{v}</td>'


def _settlement_table(rows: list[dict]) -> str:
    # gộp rowspan theo SÀN + đánh STT
    groups: list[tuple[str, list[dict]]] = []
    for r in rows:
        if groups and groups[-1][0] == r["san"]:
            groups[-1][1].append(r)
        else:
            groups.append((r["san"], [r]))
    body = []
    for i, (san, rs) in enumerate(groups, 1):
        for j, r in enumerate(rs):
            tds = []
            if j == 0:
                tds.append(f'<td rowspan="{len(rs)}">{i}</td><td rowspan="{len(rs)}">{san}</td>')
            tds.append(f'<td>{r["grade"]}</td><td>USD/T</td><td>{vn(r["prev"])}</td><td>{vn(r["curr"])}</td>')
            tds.append(_cell(_sgn(r["d_abs"])) + _cell(_sgn_pct(r["d_pct"])))
            body.append("<tr>" + "".join(tds) + "</tr>")
    return (
        '<table class="data"><thead><tr>'
        '<th rowspan="2">STT</th><th rowspan="2">SÀN</th><th rowspan="2">Chủng loại</th>'
        '<th rowspan="2">Đơn vị tính</th><th rowspan="2">Giá<br>({t2})</th><th rowspan="2">Giá<br>({t1})</th>'
        '<th colspan="2">Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead><tbody>'
        + "".join(body) + "</tbody></table>"
    )


def _physical_table(rows: list[dict]) -> str:
    body = []
    for r in rows:
        if r["curr"] is None and r["prev"] is None:
            cells = '<td>No trading</td><td>No trading</td><td>No trading</td><td>No trading</td>'
        else:
            cells = (f'<td>{vn(r["prev"])}</td><td>{vn(r["curr"])}</td>'
                     + _cell(_sgn(r["d_abs"])) + _cell(_sgn_pct(r["d_pct"])))
        body.append(f'<tr><td class="l">{r["grade"]}</td>{cells}</tr>')
    return (
        '<table class="data"><thead><tr><th rowspan="2">Chủng Loại</th>'
        '<th rowspan="2">Giá<br>({t2})</th><th rowspan="2">Giá<br>({t1})</th>'
        '<th colspan="2">Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead><tbody>'
        + "".join(body) + "</tbody></table>"
    )


def _proposal_table(rows: list[dict], lan: int, prev_lan: int, year: int) -> str:
    body = []
    for r in rows:
        body.append(
            f'<tr><td class="l">{r["grade"]}</td>'
            f'<td>{vn(r["fob"]) if r["fob"] is not None else ""}</td>'
            f'<td>{_plain(r["fob_delta"])}</td>'
            f'<td>{vn(r["vnd"]) if r["vnd"] is not None else ""}</td>'
            f'<td>{_plain(r["vnd_delta"])}</td></tr>'
        )
    return (
        '<table class="data"><thead><tr><th>Chủng Loại</th>'
        f'<th>Giá dự kiến<br>lần {lan}/{year}<br>(USD/T)</th>'
        f'<th>(+/-) (usd/tấn)<br>so với lần {prev_lan}/{year}</th>'
        f'<th>Giá dự kiến<br>lần {lan}/{year}<br>(đồng/tấn)</th>'
        f'<th>(+/-) (đ/tấn)<br>so với lần {prev_lan}/{year}</th></tr></thead><tbody>'
        + "".join(body) + "</tbody></table>"
    )


def render(d: dict) -> str:
    if d.get("error"):
        return f'<div style="padding:24px;font-family:sans-serif;color:#b00">Lỗi: {d["error"]}</div>'
    t1, t2, lan, plan, year = _dmy(d["t1"]), _dmy(d["t2"]), d["lan"], d["prev_lan"], d["year"]
    sett = _settlement_table(d["settlement"]).replace("{t1}", t1).replace("{t2}", t2)
    phys = _physical_table(d["physical"]).replace("{t1}", t1).replace("{t2}", t2)
    prop = _proposal_table(d["proposal"], lan, plan, year)
    narr1 = "".join(f'<p class="body">{x}</p>' for x in d["n1"])
    narr2 = "".join(f'<p class="body">{x}</p>' for x in d["n2"])
    return f"""<!doctype html><meta charset="utf-8"><style>{_CSS}</style><div class="page">
<table class="hdr"><tr>
  <td><div class="b caps">Tập đoàn công nghiệp</div><div class="b caps">Cao su Việt Nam</div>
      <span class="u-sm"></span><div class="b" style="margin-top:8px">Ban Thị trường Kinh doanh</div></td>
  <td><div class="b caps">Cộng hòa xã hội chủ nghĩa Việt Nam</div><div class="b">Độc lập - Tự do - Hạnh phúc</div>
      <span class="u-wide"></span><div class="it">Tp. Hồ Chí Minh, {_long_date(d["as_of"])}</div></td>
</tr></table>
<div class="title center"><div class="t1">TỜ TRÌNH</div>
  <div class="it">V/v: giá sàn lần thứ {lan} {_dmy(d["as_of"])}.</div></div>
<div class="center" style="margin:8px 0 2px">Kính gửi: Tổng Giám đốc Tập đoàn</div>
<div class="sec">1. So sánh giá cao su của các thị trường ngày {t2} và {t1}:</div>
{sett}{narr1}
<div class="sec">2. So sánh giá cao su của các sàn cao su vật chất Thái Lan, Mã Lai, Indonesia:</div>
{phys}{narr2}
<p class="body">Ban TTKD xin trình Tổng giám đốc phê duyệt điều chỉnh giá sàn lần thứ {lan} năm {year} như sau: Giá xuất khẩu FOB cảng TP Hồ Chí Minh hàng có palét cho các chủng loại SVR (USD/T) và Giá hàng rời, bán nội địa (giao hàng tại kho):</p>
{prop}
<p class="body" style="text-indent:24px">Ban Thị trường Kinh doanh kính trình Tổng giám đốc./.</p>
<table class="signs">
  <tr><td><div class="role">PHÓ TỔNG GIÁM ĐỐC PHỤ TRÁCH</div><div class="name" style="margin-top:64px">Trần Thanh Phụng</div></td>
      <td><div class="role">KT. TRƯỞNG BAN TTKD</div><div class="role">PHÓ TRƯỞNG BAN</div><div class="name" style="margin-top:46px">Dương Tuấn Anh</div></td></tr>
  <tr><td colspan="2"><div class="role">TỔNG GIÁM ĐỐC DUYỆT</div><div class="name" style="margin-top:64px">Lê Thanh Hưng</div></td></tr>
</table></div>"""
