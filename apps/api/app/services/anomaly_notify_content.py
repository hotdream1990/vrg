"""Soạn NỘI DUNG tin "Cảnh báo số liệu" gửi tự động cho MỘT đơn vị sau giờ chốt nhập liệu.

Hàm thuần (không đọc/ghi DB) — kiểm được bằng test và in mẫu từ dữ liệu thật mà không tạo luồng.
Đầu vào là kết quả quét ĐÃ thu hẹp về đơn vị (`anomaly_scope.for_units`), tức đúng bộ dòng lãnh
đạo đơn vị thấy ở màn Cảnh báo bất thường khi bấm link trong tin (link mang theo đúng khoảng ngày).

Người đọc là lãnh đạo đơn vị: không tên luật, không mã kỹ thuật; mỗi nhóm tối đa vài dòng, phần
còn lại dẫn sang trang Cảnh báo bất thường.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.services.anomaly_rules import STOCK_START
from app.services.anomaly_scope import GROUP_WIDE_RULES
from app.services.anomaly_types import vn_date, vn_day_runs, vn_num

#: Số dòng tối đa mỗi nhóm; dư thì gộp thành "và N … khác".
MAX_LINES = 3
#: Số đoạn ngày thiếu liệt kê (gần nhất); dư thì mời xem đủ trên trang.
MAX_RUNS = 6
PAGE_PATH = "/canh-bao-bat-thuong"
PAGE_NAME = "Cảnh báo bất thường"
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class AlertContext:
    unit: str             # đơn vị nhận tin
    d0: date              # ngày số liệu VỪA hết hạn nhập
    deadline: datetime    # giờ chốt vừa qua (= hạn của d0)
    today: date           # ngày chạy (để nói "hôm nay" hay ghi rõ ngày)
    date_from: str        # khoảng đã quét — trùng khoảng link mở trên trang
    date_to: str


def page_link(date_from: str, date_to: str) -> str:
    """Đường dẫn NỘI BỘ tới trang Cảnh báo bất thường, mở đúng khoảng đã quét."""
    return f"{PAGE_PATH}?date_from={date_from}&date_to={date_to}"


def _dec(v: Any) -> str:
    """12.5 → '12,5' · 1234.25 → '1.234,25' (dấu chấm ngăn nghìn, dấu phẩy thập phân)."""
    s = f"{float(v or 0):,.2f}".rstrip("0").rstrip(".")
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _cap(lines: list[str], noun: str) -> list[str]:
    if len(lines) <= MAX_LINES:
        return lines
    return [*lines[:MAX_LINES], f"và {len(lines) - MAX_LINES} {noun} khác."]


def _owner(ctx: AlertContext, row: dict[str, Any]) -> str:
    """Dòng của đơn vị đã sáp nhập vào đơn vị nhận → ghi rõ số liệu của ai."""
    who = row.get("don_vi")
    return f" (số liệu của {who})" if who and who != ctx.unit else ""


def _runs(runs: str) -> str:
    parts = [p for p in (runs or "").split(", ") if p]
    if len(parts) <= MAX_RUNS:
        return ", ".join(parts)
    return f"gần nhất {', '.join(parts[-MAX_RUNS:])} (xem đủ trên trang {PAGE_NAME})"


def _form_line(ctx: AlertContext, form: str, label: str, runs: str, start: str,
               owner: str) -> str | None:
    """Một biểu còn thiếu ngày → câu nêu ngày vừa hết hạn (nếu thiếu) + tổng từ đầu kỳ."""
    if not runs:
        return None
    with_year = date.fromisoformat(ctx.date_from).year != date.fromisoformat(ctx.date_to).year
    # Ngày thiếu xếp tăng dần và d0 là ngày CUỐI khoảng quét ⇒ d0 thiếu khi đoạn cuối kết thúc ở d0.
    last_missing = runs.split(", ")[-1].split("–")[-1]
    head = f"Biểu {form}{owner}: "
    if last_missing == vn_day_runs([ctx.d0], with_year):
        head += f"chưa nộp ngày {vn_date(ctx.d0.isoformat())} (vừa hết hạn). "
    return (f"{head}Từ {vn_date(start)} đến {vn_date(ctx.date_to)} {label.lower()}: "
            f"{_runs(runs)}.")


def _submission(ctx: AlertContext, ns: dict | None, silent: dict | None) -> list[str]:
    lines: list[str] = []
    stock_from = max(ctx.date_from, STOCK_START)
    for r in (ns or {}).get("rows") or []:
        owner = _owner(ctx, r)
        for line in (_form_line(ctx, "Thu mua", r.get("thu_mua", ""), r.get("ngay_thieu_thu_mua"),
                                ctx.date_from, owner),
                     _form_line(ctx, "Tiêu thụ – Tồn kho", r.get("ton_kho", ""),
                                r.get("ngay_thieu_ton_kho"), stock_from, owner)):
            if line:
                lines.append(line)
    for r in (silent or {}).get("rows") or []:
        last = str(r.get("ngay_nop_gan_nhat") or "")
        lines.append(f"Đã {r.get('so_ngay_ngung_nop')} ngày không nộp biểu nào (lần nộp gần nhất "
                     f"{vn_date(last)})." if _ISO.match(last) else
                     f"Chưa nộp biểu nào từ {vn_date(ctx.date_from)} đến {vn_date(ctx.date_to)}.")
    return lines


def _raw_price(ctx: AlertContext, g: dict) -> list[str]:
    def one(r: dict) -> str:
        price = f"{vn_num(r['gia_lon_nhat_dong_do'])} đồng/độ"
        cells = "1 ô giá" if r["so_o_sai"] == 1 else f"{r['so_o_sai']} ô, cao nhất"
        return f"{r['loai_mu']}: {cells} {price}{_owner(ctx, r)}."
    return _cap([one(r) for r in g["rows"]], "mục")


def _sale_price(ctx: AlertContext, g: dict) -> list[str]:
    out = []
    for r in g["rows"]:
        codes = [c for c in str(r.get("ma_hop_dong") or "").split(", ") if c]
        code_txt = ", ".join(codes[:MAX_LINES]) + (
            f" và {len(codes) - MAX_LINES} hợp đồng khác" if len(codes) > MAX_LINES else "")
        fx = "; có dòng ngoại tệ chưa khai tỷ giá" if r.get("thieu_ty_gia") else ""
        out.append(f"{r['so_dong']} dòng giá bán, cao nhất {vn_num(r['gia_lon_nhat'])} "
                   f"({r.get('loai_tien') or 'VND'}), hợp đồng: {code_txt or 'chưa có mã'}{fx}"
                   f"{_owner(ctx, r)}.")
    return _cap(out, "mục")


def _missing_price(ctx: AlertContext, g: dict) -> list[str]:
    rows = sorted(g["rows"], key=lambda r: r["ngay"], reverse=True)   # ngày gần nhất lên đầu
    return _cap([f"Ngày {vn_date(r['ngay'])}: {r['loai_mu']} ({_dec(r['san_luong_tan'])} tấn)"
                 f"{_owner(ctx, r)}." for r in rows], "ngày")


def _plan(ctx: AlertContext, g: dict) -> list[str]:
    return [f"Còn trống: {r['o_con_thieu']}{_owner(ctx, r)}." for r in g["rows"]]


def _merge_stock(ctx: AlertContext, g: dict) -> list[str]:
    return [f"Sau khi nhận {r['doi_tac_sap_nhap']} (từ {vn_date(r['ngay_sap_nhap'])}), tồn kho khai "
            f"{_dec(r['ton_sau_gop_tan'])} tấn — thấp hơn {_dec(r['hut_phan_tram'])}% so với tổng hai "
            f"đơn vị trước sáp nhập ({_dec(r['ton_truoc_gop_tan'])} tấn)." for r in g["rows"]]


def sections(ctx: AlertContext, result: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """[(tiêu đề nhóm, các dòng)] theo thứ tự người đọc cần xử lý; nhóm rỗng bị bỏ.

    Luật tính trên số gộp toàn Tập đoàn (`GROUP_WIDE_RULES`) KHÔNG bao giờ vào tin của đơn vị,
    kể cả khi người gọi quên thu hẹp. Luật mới chưa có câu riêng vẫn hiện dạng "N mục".
    """
    groups = {g["key"]: g for g in result.get("groups") or []
              if g.get("count") and g["key"] not in GROUP_WIDE_RULES}
    year = date.fromisoformat(ctx.date_to).year
    out: list[tuple[str, list[str]]] = []
    sub = _submission(ctx, groups.pop("not_submitted", None), groups.pop("silent_unit", None))
    if sub:
        out.append(("Chưa nộp đủ báo cáo ngày", sub))
    specs = (
        ("wrong_raw_price", "Giá mủ nguyên liệu nghi nhập sai đơn vị tính "
                            "(mức thường gặp 100–1.500 đồng/độ)", _raw_price),
        ("wrong_sale_price", "Giá bán trong hợp đồng nghi nhập sai đơn vị tính "
                             "(mức thường gặp 40–70 triệu đồng/tấn)", _sale_price),
        ("missing_price", "Có sản lượng thu mua nhưng chưa nhập đơn giá", _missing_price),
        ("plan_missing", f"Chưa khai đủ Kế hoạch năm {year}", _plan),
        ("missing_merge_stock", "Chưa gộp tồn kho sau sáp nhập", _merge_stock),
    )
    for key, heading, build in specs:
        if g := groups.pop(key, None):
            out.append((heading, build(ctx, g)))
    for g in groups.values():
        out.append((g["label"], [f"{g['count']} mục — xem chi tiết trên trang {PAGE_NAME}."]))
    return [(h, lines) for h, lines in out if lines]


def compose(ctx: AlertContext, result: dict[str, Any]) -> dict[str, str] | None:
    """Tiêu đề + nội dung trong app + bản tóm tắt cho email. None = đơn vị không có cảnh báo."""
    secs = sections(ctx, result)
    if not secs:
        return None
    hh = f"{ctx.deadline:%H:%M}"
    when = "hôm nay" if ctx.deadline.date() == ctx.today else f"ngày {ctx.deadline:%d/%m/%Y}"
    intro = (f"Tính đến {hh} {when} (hết hạn nhập số liệu ngày {vn_date(ctx.d0.isoformat())}), "
             f"đơn vị {ctx.unit} còn các vấn đề sau:")
    blocks = [intro]
    for i, (heading, lines) in enumerate(secs, 1):
        blocks.append("\n".join([f"{i}. {heading}", *(f"- {ln}" for ln in lines)]))
    link = page_link(ctx.date_from, ctx.date_to)
    blocks.append("Mục nào thuộc ngày đã quá hạn nhập, đơn vị gửi \"Đề nghị sửa số liệu\" ngay tại "
                  f"màn nhập liệu để Tập đoàn duyệt.\nXem chi tiết tại {PAGE_NAME}: {link}")
    blocks.append("Tin gửi tự động sau giờ chốt nhập liệu. Đơn vị cần hỗ trợ thì trả lời ngay "
                  "trong tin này.")
    email = "\n".join([intro, *(f"{i}. {h}" for i, (h, _) in enumerate(secs, 1))])
    return {"subject": f"Cảnh báo số liệu — tính đến {hh} ngày {ctx.deadline:%d/%m/%Y}",
            "body": "\n\n".join(blocks), "email": email, "link": link}
