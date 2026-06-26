"""Import lịch sử Giá sàn Tập đoàn ban hành (vrg_floor_price) từ sheet 'Bảng tính giá'.

Mỗi block 'Giá sàn lần X (dd/mm/yyyy)': cột Chủng Loại + (Giá XK FOB/FCA USD, Giá nội địa VNĐ/T).
- File 2021-2025: FOB lưu float NGHÌN-USD (1.57 = 1570), nội địa lưu TEXT '37.200.000'.
- File master:    FOB số USD đủ (2480), nội địa số.
"Lần" reset theo năm → đánh số `lan` TOÀN CỤC theo as_of (ngày là khóa thật). Gộp cả 2 file.

Chạy: uv run --with openpyxl --with "psycopg[binary]" python import_floor.py [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import re

import openpyxl

import _lib

FILES = [
    (str(_lib.DOCS / "bieu-mau-bo-sung/Giá các sàn OSE,SHFE,SGX, MRB năm 2021-2025.xlsx"), "Bảng tính giá"),
    (str(_lib.DOCS / "bieu-mau/Tâm/Mẫu file lấy giá các sàn, giá mủ nước...xlsx"), "Bảng tính giá"),
]
GRADES = {"SVR CV 50", "SVR CV60", "SVR L", "SVR 3L Mix", "SVR 3L", "SVR 5S", "SVR 5",
          "SVR 10 Mix", "SVR 10", "SVR 20", "RSS 3", "RSS 1", "LATEX"}
_LAN_RE = re.compile(r"lần\s*(\d+)\D*?(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})", re.I)


def _fob(v) -> int | None:
    if not isinstance(v, (int, float)):
        return None
    x = float(v)
    return round(x * 1000) if x < 100 else round(x)  # nghìn-USD -> USD/T


def _vnd(v) -> int | None:
    if isinstance(v, (int, float)):
        return int(v)
    if v is None:
        return None
    s = re.sub(r"[.,\s]", "", str(v))
    return int(s) if s.isdigit() else None


def parse_file(path: str, sheet: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    out: dict[tuple[str, str], tuple] = {}
    for ri, row in enumerate(rows):
        gc = next((i for i, c in enumerate(row)
                   if c and str(c).strip().lower() == "chủng loại"), None)
        lans = [(i, _LAN_RE.search(str(c).replace("\n", " ")))
                for i, c in enumerate(row) if c and "Giá sàn lần" in str(c)]
        lans = [(i, m) for i, m in lans if m]
        if gc is None or not lans:
            continue
        for rr in range(ri + 2, min(ri + 20, len(rows))):
            grow = rows[rr]
            grade = str(grow[gc]).strip() if gc < len(grow) and grow[gc] else ""
            if not grade:
                break
            if grade not in GRADES:
                continue
            for lc, m in lans:
                yy = int(m.group(4))
                yy = 2000 + yy if yy < 100 else yy
                try:
                    as_of = datetime.date(yy, int(m.group(3)), int(m.group(2))).isoformat()
                except ValueError:
                    continue
                fob = _fob(grow[lc]) if lc < len(grow) else None
                vnd = _vnd(grow[lc + 1]) if lc + 1 < len(grow) else None
                if fob is None and vnd is None:
                    continue
                out[(as_of, grade)] = (fob, vnd)
    return out


def run(from_year: int, dry: bool) -> int:
    merged: dict[tuple[str, str], tuple] = {}
    for path, sheet in FILES:
        merged.update(parse_file(path, sheet))
    merged = {k: v for k, v in merged.items() if int(k[0][:4]) >= from_year}  # chỉ >= from_year
    dates = sorted({k[0] for k in merged})
    lan_of = {d: i + 1 for i, d in enumerate(dates)}  # lan toàn cục theo ngày
    recs = [{"lan": lan_of[a], "as_of": a, "grade": g, "fob_usd": fob, "domestic_vnd": vnd}
            for (a, g), (fob, vnd) in merged.items()]
    print(f"[floor] {len(dates)} lần (biểu giá), {len(recs)} dòng | "
          f"{dates[0]} -> {dates[-1]} {'(dry-run)' if dry else ''}")
    if dry:
        for a in dates[:2] + dates[-2:]:
            sample = {g: merged[(a, g)] for (aa, g) in merged if aa == a}
            print(f"   {a}: {sample}")
        return len(recs)
    import psycopg
    with psycopg.connect(_lib.get_dsn()) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM vrg_floor_price")
        cur.executemany(
            "INSERT INTO vrg_floor_price (lan, as_of, grade, fob_usd, domestic_vnd) "
            "VALUES (%(lan)s, %(as_of)s, %(grade)s, %(fob_usd)s, %(domestic_vnd)s)", recs)
        conn.commit()
    print(f"[floor] đã ghi {len(recs)} dòng vào vrg_floor_price")
    return len(recs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=_lib.MIN_YEAR)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.from_year, a.dry_run)
