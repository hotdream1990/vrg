"""Render TỜ TRÌNH giá sàn ra HTML (A4, Times New Roman) theo MẪU MỚI — Tờ trình 54/TTr-TTKD lần 22
ngày 24/9/2026. Bản này dùng để xem trước, in và xuất PDF; bản Word dựng cùng khung ([to_trinh_view]).

Mọi chữ người dùng sửa được (nội dung tờ trình) đều escape — HTML còn được nhúng vào iframe.
"""
from __future__ import annotations

from html import escape

from app.services import to_trinh_memo, to_trinh_view

_CSS = """
@page { size: A4 portrait; margin: 18mm 18mm 16mm 25mm; }
* { box-sizing: border-box; }
body { font-family: "Times New Roman", Tinos, Times, serif; font-size: 13pt; color: #111; line-height: 1.38;
       margin: 0; background: #f3f4f6; }
.page { width: 210mm; min-height: 297mm; background: #fff; margin: 12px auto; padding: 18mm 18mm 16mm 25mm;
        box-shadow: 0 1px 6px rgba(0,0,0,.18); }
/* In: lề do @page lo; chừa 2px để Chromium không xén mất viền phải của bảng (viền nằm đúng mép vùng in). */
@media print { body { background: #fff; } .page { margin: 0; padding: 0 2px; box-shadow: none; width: auto; min-height: 0; } }
.hdr { width: 100%; border-collapse: collapse; }
.hdr td { vertical-align: top; text-align: center; padding: 0; font-size: 12.5pt; }
.nowrap { white-space: nowrap; }
.b { font-weight: bold; } .it { font-style: italic; } .c { text-align: center; }
.rule { display: block; margin: 3px auto 4px; border-top: 1px solid #111; }
.title { font-weight: bold; font-size: 14pt; margin-top: 10px; }
.sec { font-weight: bold; margin: 8px 0 4px; text-indent: 1cm; text-align: justify; }
p.body { margin: 4px 0; text-align: justify; text-indent: 1cm; }
p.note { margin: 2px 0 6px; font-size: 10pt; font-style: italic; text-align: justify; }
.lead { font-weight: bold; font-style: italic; }
table.data { width: 100%; border-collapse: collapse; margin: 4px 0 6px; font-size: 11.5pt; table-layout: auto; }
table.data th, table.data td { border: 1px solid #222; padding: 2px 3px; text-align: center; vertical-align: middle; }
table.data th { background: #eaf1dd; font-weight: bold; }
table.data td.l { text-align: left; } table.data td.r { text-align: right; }
.daytag { font-size: 9pt; color: #555; }
.signs { width: 100%; border-collapse: collapse; margin-top: 10px; text-align: center; page-break-inside: avoid; }
.signs td { width: 50%; vertical-align: top; padding: 4px; font-weight: bold; }
.signs .name { margin-top: 84px; }
"""


def _e(s: str) -> str:
    return escape(s or "")


def _para(p: dict, lead_cls: str = "lead") -> str:
    lead = f'<span class="{lead_cls}">{_e(p["lead"])}</span> ' if p.get("lead") else ""
    return f'<p class="body">{lead}{_e(p.get("text", ""))}</p>' if (lead or p.get("text")) else ""


def _paras(items: list[dict]) -> str:
    return "".join(_para(p) for p in items)


def _price(v: str, tag: str) -> str:
    return _e(v) + (f' <span class="daytag">{tag}</span>' if tag else "")


def _settlement(v: dict) -> str:
    body = []
    for r in v["sett"]:
        lead = (f'<td rowspan="{r["span"]}">{r["stt"]}</td><td rowspan="{r["span"]}">{_e(r["san"])}</td>'
                if r["span"] else "")
        body.append(f'<tr>{lead}<td>{_e(r["grade"])}</td><td>{r["unit"]}</td>'
                    f'<td>{_price(r["prev"], r["prev_tag"])}</td><td>{_price(r["curr"], r["curr_tag"])}</td>'
                    f'<td>{r["d"]}</td><td>{r["pct"]}</td></tr>')
    return ('<table class="data"><thead><tr><th rowspan="2">STT</th><th rowspan="2">SÀN<br>FUTURES</th>'
            '<th rowspan="2">Chủng loại</th><th rowspan="2">Đơn vị<br>tính</th>'
            f'<th rowspan="2">Giá<br>({v["d2"]})</th><th rowspan="2">Giá<br>({v["d1"]})</th>'
            '<th colspan="2">Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table>")


def _physical(v: dict) -> str:
    body = "".join(f'<tr><td class="l">{_e(r["grade"])}</td><td>{r["prev"]}</td><td>{r["curr"]}</td>'
                   f'<td>{r["d"]}</td><td>{r["pct"]}</td></tr>' for r in v["phys"])
    return ('<table class="data"><thead><tr><th rowspan="2">SÀN<br>PHYSICAL</th>'
            f'<th rowspan="2">Giá<br>({v["d2"]})</th><th rowspan="2">Giá<br>({v["d1"]})</th>'
            '<th colspan="2">Thay đổi</th></tr><tr><th>USD/T</th><th>%</th></tr></thead><tbody>'
            + body + "</tbody></table>")


def _proposal(v: dict) -> str:
    body = "".join(f'<tr><td class="l">{_e(r["grade"])}</td><td class="r">{r["fob"]}</td>'
                   f'<td class="r">{r["fob_d"]}</td><td class="r">{r["vnd"]}</td><td class="r">{r["vnd_d"]}</td></tr>'
                   for r in v["prop"])
    lan, prev = v["prop_lan"], v["prop_prev"]
    return ('<table class="data"><thead><tr><th>Chủng Loại</th>'
            f'<th>Giá dự kiến<br>{lan}</th><th>(+/-)<br>(usd/tấn)<br>so với<br>{prev}</th>'
            f'<th>Giá dự kiến<br>{lan}</th><th>(+/-)<br>(đ/tấn)<br>so với<br>{prev}</th></tr></thead><tbody>'
            + body + "</tbody></table>")


def _signers(s: dict) -> str:
    def role(text: str) -> str:
        return "<br>".join(_e(x) for x in (text or "").splitlines())
    return (f'<table class="signs"><tr><td>{role(s["left_role"])}<div class="name">{_e(s["left_name"])}</div></td>'
            f'<td>{role(s["right_role"])}<div class="name">{_e(s["right_name"])}</div></td></tr>'
            f'<tr><td colspan="2">{role(s["approver_role"])}<div class="name">{_e(s["approver_name"])}</div>'
            "</td></tr></table>")


def render(d: dict) -> str:
    """`d` = ảnh chụp thị trường + `proposal` (dòng khối 3) + `memo` (thiếu → mặc định dựng từ số)."""
    if d.get("error"):
        return f'<div style="padding:24px;font-family:sans-serif;color:#b00">Lỗi: {escape(str(d["error"]))}</div>'
    memo = d.get("memo") or to_trinh_memo.defaults(d)
    v = to_trinh_view.build(d, memo, d["proposal"])
    inv = _para(v["inventory"], "b")
    phys_note = f'<p class="body">{_e(v["physical_note"])}</p>' if v["physical_note"] else ""
    fut_note = f'<p class="note">{_e(v["futures_note"])}</p>' if v["futures_note"] else ""
    return f"""<!doctype html><meta charset="utf-8"><title>Tờ trình giá sàn</title><style>{_CSS}</style><div class="page">
<table class="hdr"><tr>
  <td style="width:40%"><div class="b">{v["org"][0]}</div><div class="b">{v["org"][1]}</div>
      <span class="rule" style="width:30%"></span></td>
  <td><div class="b nowrap">{v["nation"][0]}</div><div class="b">{v["nation"][1]}</div>
      <span class="rule" style="width:62%"></span></td></tr>
  <tr><td><div class="b">{v["dept"]}</div><div>{_e(v["so"])}</div></td>
      <td><div class="it">{v["place_date"]}</div></td></tr></table>
<div class="c title">TỜ TRÌNH</div>
<div class="c">{v["subject"]}</div><span class="rule" style="width:28%"></span>
<div class="c" style="margin:4px 0 6px">{v["to"]}</div>
<div class="sec">{v["sec1"]}</div>
{_settlement(v)}{fut_note}{_paras(v["futures"])}
<div class="sec">{_e(v["sec2"])}</div>
{_physical(v)}{phys_note}{_paras(v["physical"])}{_paras(v["outlook"])}
{inv}<p class="body">{_e(v["intro"])}</p>
{_proposal(v)}
<p class="body">{v["closing"]}</p>
{_signers(v["signers"])}</div>"""
