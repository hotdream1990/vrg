"""Hàm thuần dùng cho `migrate-sales-contracts.py` — tách ra cho file chính gọn.

Không đụng database: chỉ đọc/nắn dữ liệu cũ thành hình dạng của bảng `sales_contract`.
"""
from __future__ import annotations

import math
import re
from typing import Any

MAX_DOCS = 20                       # trần số file mỗi ô — khớp `contract_docs.MAX_DOCS`
CCY = ("VND", "USD", "LAK", "KHR")
CONTRACT_TYPES = ("long_term", "spot")
# `channel` cũ chỉ có export | domestic; "internal" (tiêu thụ nội bộ) là khái niệm MỚI,
# dữ liệu cũ không có nên không được đoán.
CHANNELS = ("export", "domestic")


def num(v) -> float | None:
    """Số hợp lệ hoặc None. Loại NaN/Infinity (jsonb của Postgres từ chối, và `nan <= 0` là False
    nên lọt mọi kiểm tra lớn-hơn-0)."""
    try:
        f = None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
    return None if f is not None and not math.isfinite(f) else f


def norm_code(s: Any) -> str:
    """Số hợp đồng chuẩn hoá để so khớp: bỏ dấu cách, in hoa. "PL 02" và "PL02" là một."""
    return re.sub(r"\s+", "", str(s or "")).upper()


def docs(raw: Any, legacy_file: Any = None, legacy_name: Any = None) -> list[dict[str, str]]:
    """Một ô đính kèm → `[{"file","filename"}]`, lùi về cặp khoá cũ khi danh sách rỗng."""
    out: list[dict[str, str]] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict) and str(item.get("file") or "").strip():
            out.append({"file": str(item["file"]).strip()[:120],
                        "filename": str(item.get("filename") or item["file"]).strip()[:200]})
    if not out and str(legacy_file or "").strip():
        out.append({"file": str(legacy_file).strip()[:120],
                    "filename": str(legacy_name or legacy_file).strip()[:200]})
    return out


def merge_docs(*lists: list[dict[str, str]]) -> list[dict[str, str]]:
    """Gộp nhiều ô đính kèm, khử trùng theo tên lưu, cắt trần MAX_DOCS."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for lst in lists:
        for d in lst:
            if d["file"] not in seen:
                seen.add(d["file"])
                out.append(d)
    return out[:MAX_DOCS]


def line_docs(ln: dict) -> tuple[list, list]:
    """(bộ hợp đồng, chứng từ giao–thanh toán) của MỘT dòng bán cũ.

    Dòng cũ có 3 ô đính kèm: `files` (bộ HĐ) · `inv_files` (hoá đơn) · `wh_files` (phiếu xuất kho).
    Bảng mới chỉ có 2 ô (`files` = HĐ scan, `payment_docs` = chứng từ thanh toán) → dồn hoá đơn +
    phiếu xuất kho vào ô chứng từ. Bỏ 2 ô sau là mất hẳn ~2.600 file khách đã tải lên.
    """
    return (docs(ln.get("files"), ln.get("file"), ln.get("filename")),
            merge_docs(docs(ln.get("inv_files"), ln.get("inv_file"), ln.get("inv_filename")),
                       docs(ln.get("wh_files"), ln.get("wh_file"), ln.get("wh_filename"))))


def is_blank(ln: dict) -> bool:
    """Dòng TRỐNG do người dùng bấm thêm rồi bỏ dở: không số lượng, không giá, không số HĐ,
    không file. Chủng loại có sẵn (ô select mặc định) nên KHÔNG tính là dữ liệu."""
    if num(ln.get("qty")):
        return False
    f, p = line_docs(ln)
    return not (num(ln.get("price")) or norm_code(ln.get("code")) or f or p)


def problem(ln: dict) -> str | None:
    """Lý do dòng KHÔNG chuyển được (đã loại dòng trống trước đó) — None nghĩa là chuyển được."""
    if not str(ln.get("grade") or "").strip():
        return "thiếu chủng loại"
    q = num(ln.get("qty"))
    if q is None:
        return "thiếu số lượng"
    if q <= 0:
        return "số lượng bằng 0"
    return None


def sale_ccy(line_ccy, day_ccy, unit_ccy: str) -> str:
    """Loại tiền của 1 dòng bán CŨ — phải giữ ĐÚNG cách báo cáo cũ đọc, nếu không số lệch hẳn.

    Hệ thống cũ lấy loại tiền của dòng, thiếu thì lấy mức NGÀY (`sales_ccy`), thiếu nữa thì suy
    theo đơn vị. Mặc định cứng "VND" làm giá 1.610 USD/tấn bị đọc thành 1.610 triệu đ/tấn.
    """
    for c in (line_ccy, day_ccy):
        if c in CCY:
            return c
    return "VND" if (unit_ccy or "VND") == "VND" else "USD"


def build_line(ln: dict, ccy: str, day_fx) -> dict[str, Any]:
    """Một dòng chi tiết hợp đồng mới. `qty_dry` để None — dữ liệu cũ KHÔNG có, không bịa."""
    fx = num(ln.get("fx"))
    return {"grade": str(ln.get("grade") or "")[:80], "qty": num(ln.get("qty")), "qty_dry": None,
            "price": num(ln.get("price")), "ccy": ccy,
            "fx": fx if fx is not None else num(day_fx)}


def dmy(d) -> str:
    return d.strftime("%d/%m/%Y") if hasattr(d, "strftime") else str(d)


def note_dates(ln: dict) -> str:
    """Ghi lại ngày hoá đơn / ngày xuất kho của dòng cũ — bảng mới không có 2 ô này."""
    parts = []
    for key, label in (("invoice_date", "hoá đơn"), ("warehouse_date", "xuất kho")):
        v = str(ln.get(key) or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            parts.append(f"ngày {label} {v[8:10]}/{v[5:7]}/{v[:4]}")
    return " · ".join(parts)
