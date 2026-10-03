"""Khung TỜ TRÌNH giá sàn theo mẫu mới — chữ từng ô/dòng đã định dạng sẵn, dùng chung cho bản HTML/PDF
([to_trinh_html]) và bản Word ([to_trinh_docx]) để hai bản không bao giờ lệch nhau.

Mẫu: Tờ trình 54/TTr-TTKD "V/v giá sàn lần thứ 22 ngày 24/9/2026" (Ban TTKD gửi 24/9/2026).
GIỮ ĐÚNG THỨ TỰ chủng loại của phương án — KHÔNG sort.
"""
from __future__ import annotations

from typing import Any

from app.services.to_trinh import vn
from app.services.to_trinh_memo import dmy

#: Tên chủng loại trên tờ trình (theo mẫu), khoá = khoá hệ thống của phương án.
DOC_LABEL = {"SVR CV 50": "CV50", "SVR CV60": "CV60", "SVR L": "SVRL", "SVR 3L Mix": "SVR 3L Mix",
             "SVR 3L": "SVR 3L", "SVR 5S": "SVR 5S", "SVR 5": "SVR 5", "SVR 10 Mix": "SVR10 Mix",
             "SVR 10 / CSR 10": "SVR 10", "SVR 20 / CSR 20": "SVR 20", "RSS 3": "RSS 3", "RSS 1": "RSS 1",
             "LATEX": "Latex", "Skim Block": "Skim Block"}
HOLIDAY = "Holiday"


def num(n: float | int | None) -> str:
    """Số kiểu VN, giữ dấu trừ; trống → ''."""
    return "" if n is None else (vn(n) if n >= 0 else f"-{vn(abs(n))}")


def signed(n: float | int | None) -> str:
    return "" if n is None else (f"+{vn(n)}" if n > 0 else num(n))


def pct(p: float | None) -> str:
    return "" if p is None else f"{p:+.1f}".replace(".", ",")


def short(iso: str | None) -> str:
    """'2026-09-22' → '22/09/26' (tiêu đề cột giá)."""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[2:4]}" if iso else "—"


def long_date(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"ngày {int(d)} tháng {int(m)} năm {y}"


def _tag(iso: str | None, ref: str | None) -> str:
    """'(22/09)' khi ô lấy từ phiên KHÁC ngày tiêu đề cột (sàn nghỉ lễ lệch nhau)."""
    return f"({iso[8:10]}/{iso[5:7]})" if iso and ref and iso != ref else ""


def _settlement(rows: list[dict], t1: str | None, t2: str | None) -> list[dict]:
    out, stt, prev_san = [], 0, None
    for i, r in enumerate(rows):
        first = r["san"] != prev_san
        if first:
            stt += 1
            span = 1
            while i + span < len(rows) and rows[i + span]["san"] == r["san"]:
                span += 1
        prev_san = r["san"]
        closed = r.get("curr") is None and r.get("prev") is None
        out.append({"stt": str(stt), "san": r["san"], "span": span if first else 0, "grade": r["grade"],
                    "unit": "USD/T",
                    "prev": HOLIDAY if closed else num(r.get("prev")) or "—",
                    "prev_tag": _tag(r.get("prev_as_of"), t2) if r.get("prev") is not None else "",
                    "curr": HOLIDAY if r.get("curr") is None else num(r["curr"]),
                    "curr_tag": _tag(r.get("curr_as_of"), t1) if r.get("curr") is not None else "",
                    "d": signed(r.get("d_abs")), "pct": pct(r.get("d_pct"))})
    return out


def _physical(rows: list[dict]) -> list[dict]:
    return [{"grade": r["grade"], "prev": num(r.get("prev")) or "No trading",
             "curr": num(r.get("curr")) or "No trading", "d": signed(r.get("d_abs")), "pct": pct(r.get("d_pct"))}
            for r in rows]


def _proposal(rows: list[dict]) -> list[dict]:
    return [{"grade": DOC_LABEL.get(r.get("key") or "", r["grade"]),
             "fob": num(r.get("fob")), "fob_d": num(r.get("fob_delta")),
             "vnd": num(r.get("vnd")), "vnd_d": num(r.get("vnd_delta"))} for r in rows]


def build(d: dict[str, Any], memo: dict[str, Any], rows: list[dict]) -> dict[str, Any]:
    """`d` = ảnh chụp thị trường (to_trinh.build_market), `memo` = nội dung tờ trình đã làm sạch,
    `rows` = dòng khối 3 (floor_proposal.to_trinh_rows: khoá hệ thống ở `key`)."""
    t1, t2, lan, year = d.get("t1"), d.get("t2"), d["lan"], d["year"]
    return {
        "org": ["TẬP ĐOÀN CÔNG NGHIỆP", "CAO SU VIỆT NAM"], "dept": "Ban Thị trường Kinh doanh",
        "so": f"Số: {memo['so'] or '……/TTr-TTKD'}",
        "nation": ["CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Độc lập - Tự do - Hạnh phúc"],
        "place_date": f"Tp. Hồ Chí Minh, {long_date(memo['sign_date'])}",
        "subject": f"V/v giá sàn lần thứ {lan} ngày {dmy(d['as_of'])}.",
        "to": "Kính gửi: Tổng Giám đốc Tập đoàn",
        "sec1": f"I. So sánh giá cao su của các thị trường ngày {dmy(t2)} và {dmy(t1)}:",
        "d1": short(t1), "d2": short(t2),
        "sett": _settlement(d.get("settlement") or [], t1, t2),
        "futures_note": memo["futures_note"], "futures": memo["futures"],
        "sec2": ("II. So sánh giá cao su của các sàn cao su vật chất Thái Lan, Mã Lai, Indonesia"
                 + (f": {memo['physical_title'].rstrip(':')}:" if memo["physical_title"] else ":")),
        "phys": _physical(d.get("physical") or []),
        "physical_note": memo["physical_note"], "physical": memo["physical"], "outlook": memo["outlook"],
        "inventory": memo["inventory"], "intro": memo["intro"],
        "prop_lan": f"lần {lan}/{year}", "prop_prev": f"lần {d['prev_lan']}/{year}",
        "prop": _proposal(rows),
        "closing": "Ban Thị trường Kinh doanh kính trình Tổng giám đốc./.",
        "signers": memo["signers"],
    }
