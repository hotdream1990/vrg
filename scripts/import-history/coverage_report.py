"""Báo cáo độ phủ fact_price: mỗi (source, grade, price_type) đã fill tới đâu.

Xuất Excel + in bảng. Giúp biết chuỗi nào đủ, chuỗi nào còn trống để bổ sung.
Cột: source, grade, price_type, currency, unit, từ ngày, đến ngày, số ngày,
     số ngày làm việc kỳ vọng, % phủ, ngày gần nhất.

Chạy:
  uv run --with openpyxl --with "psycopg[binary]" python coverage_report.py [--out X]
"""
from __future__ import annotations

import argparse
import datetime

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import _lib

DEFAULT_OUT = str(_lib.DOCS / "bieu-mau-bo-sung/coverage-fact_price.xlsx")

_SQL = """
SELECT source, grade, price_type, min(currency) currency, min(unit) unit,
       min(as_of) d0, max(as_of) d1, count(DISTINCT as_of) ndays, count(*) nrows
FROM fact_price
GROUP BY source, grade, price_type
ORDER BY source, price_type, grade;
"""


def _weekdays(d0: datetime.date, d1: datetime.date) -> int:
    days = (d1 - d0).days + 1
    full, rem = divmod(days, 7)
    wd = full * 5
    start = d0.weekday()
    for k in range(rem):
        if (start + k) % 7 < 5:
            wd += 1
    return max(wd, 1)


def fetch() -> list[dict]:
    import psycopg

    with psycopg.connect(_lib.get_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(_SQL)
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


HEADERS = ["source", "grade", "price_type", "currency", "unit",
           "Từ ngày", "Đến ngày", "Số ngày", "Ngày làm việc KV", "% phủ", "Số bản ghi"]


def write_xlsx(data: list[dict], out: str) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Coverage"
    hfill, hfont = PatternFill("solid", fgColor="2E7D32"), Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="BBBBBB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for j, h in enumerate(HEADERS, 1):
        c = ws.cell(1, j, h)
        c.fill, c.font = hfill, hfont
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.border = border
    for i, row in enumerate(data, 2):
        d0, d1 = row["d0"], row["d1"]
        wd = _weekdays(d0, d1)
        pct = round(100 * row["ndays"] / wd, 1)
        vals = [row["source"], row["grade"], row["price_type"], row["currency"], row["unit"],
                d0.isoformat(), d1.isoformat(), row["ndays"], wd, pct, row["nrows"]]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j, v)
            c.border = border
            if j == 10:  # % phủ
                c.fill = PatternFill("solid", fgColor="C8E6C9" if pct >= 85 else
                                     ("FFF9C4" if pct >= 60 else "FFCDD2"))
    widths = [10, 12, 11, 9, 16, 12, 12, 9, 14, 8, 11]
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{len(data) + 1}"
    wb.save(out)


def main(out: str) -> None:
    data = fetch()
    if not data:
        print("fact_price trống (chưa import hoặc DB chưa chạy).")
        return
    print(f"{'source':8} {'grade':10} {'type':11} {'from':11} {'to':11} {'days':>5} {'rows':>6}")
    for r in data:
        print(f"{r['source']:8} {r['grade']:10} {r['price_type']:11} "
              f"{r['d0'].isoformat():11} {r['d1'].isoformat():11} {r['ndays']:5} {r['nrows']:6}")
    write_xlsx(data, out)
    print(f"\nĐã ghi báo cáo: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT)
    main(ap.parse_args().out)
