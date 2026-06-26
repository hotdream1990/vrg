"""Import giá sàn giao dịch (OSE/SHFE/SGX/MRB) + tỷ giá từ sheet '2025' vào fact_price.

Sheet '2025' (file 2021-2025): cột B = Ngày (date thật), mỗi sàn vài cột (nội tệ/tỷ giá/USD).
Map khớp apps/api market_meta.SHEET_GROUPS để hiển thị đúng grid "Bảng tính giá".

Chạy:
  uv run --with openpyxl --with "psycopg[binary]" python import_exchange.py [--file X] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime

import openpyxl

import _lib

DEFAULT_FILE = str(_lib.DOCS / "bieu-mau-bo-sung/Giá các sàn OSE,SHFE,SGX, MRB năm 2021-2025.xlsx")
DATE_COL = 2  # cột B

# (cột Excel 1-based, source, grade, price_type, currency, unit, scale) — scale: USD/T -> US cents/kg = *0.1
SERIES = [
    (3, "tocom", "RSS3", "settlement", "JPY", "JPY/kg", 1.0),
    (6, "shfe", "RU", "settlement", "CNY", "CNY/tonne", 1.0),
    (9, "sgx", "RSS3", "settlement", "USD", "US cents/kg", 0.1),
    (10, "sgx", "TSR20", "settlement", "USD", "US cents/kg", 0.1),
    (11, "lgm", "SMRCV", "physical", "USD", "US cents/kg", 0.1),
    (12, "lgm", "SMR20", "physical", "USD", "US cents/kg", 0.1),
    (13, "lgm", "LATEX", "physical", "USD", "US cents/kg", 1.0),
]
# (cột Excel, cặp, đơn vị tiền) — tỷ giá: native per USD
FX = [(4, "USD/JPY", "JPY"), (7, "USD/CNY", "CNY"), (14, "USD/MYR", "MYR")]


def run(path: str, sheet: str, from_year: int, dry: bool) -> int:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows: list[dict] = []
    for r in ws.iter_rows(min_row=5, values_only=True):
        d = r[DATE_COL - 1]
        if not isinstance(d, (datetime.datetime, datetime.date)):
            continue
        d = d.date() if isinstance(d, datetime.datetime) else d
        if d.year < from_year:
            continue
        myr = _lib.parse_number(r[14 - 1]) if 14 - 1 < len(r) else None  # USD/MYR cùng dòng
        for col, src, grade, pt, cur, unit, scale in SERIES:
            v = _lib.parse_number(r[col - 1]) if col - 1 < len(r) else None
            if v is None or v == 0:
                continue
            if grade == "LATEX":
                # LATEX trong Excel là Sen/kg → US cents/kg = Sen/kg ÷ tỷ giá MYR (khớp lgm crawler).
                if not myr:
                    continue
                price = round(v / myr, 2)
            else:
                price = round(v * scale, 6)
            rows.append(dict(as_of=d, source=src, grade=grade, contract="", price_type=pt,
                             price=price, currency=cur, unit=unit, source_ts=None))
        for col, pair, cur in FX:
            v = _lib.parse_number(r[col - 1]) if col - 1 < len(r) else None
            if v is None or v == 0:
                continue
            rows.append(dict(as_of=d, source="fx", grade=pair, contract="", price_type="fx",
                             price=v, currency=cur, unit=f"{cur} per USD", source_ts=None))
    wb.close()
    n = _lib.upsert(rows, dry_run=dry)
    tag = "(dry-run) " if dry else ""
    print(f"[exchange] sheet '{sheet}': {n} bản ghi {tag}(from_year={from_year})")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--sheet", default="2025")
    ap.add_argument("--from-year", type=int, default=_lib.MIN_YEAR)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.file, a.sheet, a.from_year, a.dry_run)
