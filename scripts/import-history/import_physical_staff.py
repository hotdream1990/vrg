"""Import giá Physical (USD/tấn) từ sheet 'Lưu' — kho lưu hàng ngày của chuyên viên.

File 'Giá các sàn ...2021-2025.xlsx', sheet 'Lưu': mỗi block là 1 ngày so sánh; bảng PHẢI
(cột 10-13) là physical đã quy đổi sẵn USD/T. Header 'Chủng loại | Giá(d1) | Giá(d2)' rồi
các grade (RSS3/STR20/SMR20/SIR20/Thai Latex 60% Bulk·Drums). Ngày 'd/m' (2024) hoặc 'd/m/yy'.
Phủ ~13/05/2024 → 29/12/2025. Nạp source='reuters', unit='USD/tonne' (KHỎI quy đổi).

Chạy: uv run --with openpyxl --with "psycopg[binary]" python import_physical_staff.py [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import re

import openpyxl

import _lib

DEFAULT_FILE = str(_lib.DOCS / "bieu-mau-bo-sung/Giá các sàn OSE,SHFE,SGX, MRB năm 2021-2025.xlsx")
_PLAIN = {"RSS3", "STR20", "SMR20", "SIR20"}


def _norm_grade(s: str) -> str | None:
    s = s.strip()
    if s in _PLAIN:
        return s
    low = s.lower()
    if "latex" in low:
        return "Thai Latex 60% (Drums)" if "drum" in low else "Thai Latex 60% (Bulk)"
    return None


def _parse_date(s: str, state: dict) -> datetime.date | None:
    """Ngày từ 'Giá (13/5)' / 'Giá (22/12/25)'. Hậu tố năm nếu có; ngày trống năm dựng theo
    mốc đơn điệu (block xếp theo thời gian) — nếu lùi so với ngày trước thì sang năm mới."""
    m = re.search(r"(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?", s or "")
    if not m:
        return None
    d, mo, yy = int(m.group(1)), int(m.group(2)), m.group(3)
    prev = state.get("prev")
    if yy:
        y = int(yy)
        y = y + 2000 if y < 100 else y
    else:
        y = prev.year if prev else 2024
    try:
        cand = datetime.date(y, mo, d)
    except ValueError:
        return None
    if not yy and prev and cand < prev:  # ngày trống năm bị lùi → qua năm mới
        try:
            cand = datetime.date(y + 1, mo, d)
        except ValueError:
            return None
    if prev is None or cand > prev:
        state["prev"] = cand
    return cand


def run(path: str, from_year: int, dry: bool) -> int:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb["Lưu"]
    out: list[dict] = []
    state: dict = {"prev": None}
    cur_date: datetime.date | None = None
    gc: int | None = None  # cột 'Chủng loại' của block hiện tại (0-based); đổi layout giữa chừng
    for row in ws.iter_rows(values_only=True):
        # Header bảng physical = ô 'chủng loại' ở cột J (idx 9) trở đi (bỏ bảng sàn ở cột C).
        # Từ ~10/2025 layout đổi: header dời sang cột M + ghi 'Chủng Loại' (L hoa).
        hi = next((i for i in range(9, len(row))
                   if row[i] and str(row[i]).strip().lower() == "chủng loại"), None)
        if hi is not None:
            gc = hi
            d2 = str(row[gc + 2]) if len(row) > gc + 2 and row[gc + 2] else ""
            cur_date = _parse_date(d2, state)
            continue
        if cur_date is None or gc is None or len(row) <= gc + 2 or not row[gc]:
            continue
        grade = _norm_grade(str(row[gc]).strip())
        if not grade or cur_date.year < from_year:
            continue
        v = _lib.parse_number(row[gc + 2])
        if v is None or v == 0:
            continue
        out.append(dict(as_of=cur_date.isoformat(), source="reuters", grade=grade, contract="",
                        price_type="physical", price=v, currency="USD", unit="USD/tonne", source_ts=None))
    wb.close()
    n = _lib.upsert(out, dry_run=dry)
    days = len({r["as_of"] for r in out})
    print(f"[physical-staff] {n} bản ghi {'(dry-run) ' if dry else ''}| {days} ngày | từ {from_year}")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--from-year", type=int, default=_lib.MIN_YEAR)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.file, a.from_year, a.dry_run)
