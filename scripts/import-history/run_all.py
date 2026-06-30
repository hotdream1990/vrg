"""Triển khai TOÀN BỘ dữ liệu lịch sử vào DB đích (idempotent) — chỉ từ 2024.

- Đặt DATABASE_URL trỏ tới DB cần nạp (vd production) TRƯỚC khi chạy; mặc định DB dev local.
- File biểu mẫu lấy theo BIEU_MAU_DOCS (mặc định <repo>/docs).
- Chạy lại an toàn: exchange/latex/physical = upsert; floor = ghi đè toàn bộ.

Chạy:
  DATABASE_URL=postgresql://user:pass@host:5432/db \\
  uv run --with openpyxl --with "psycopg[binary]" python run_all.py [--from-year 2024]
"""
from __future__ import annotations

import argparse

import _lib
import coverage_report
import import_exchange
import import_floor_table
import import_latex
import import_physical_staff

MASTER = str(_lib.DOCS / "bieu-mau/Tâm/Mẫu file lấy giá các sàn, giá mủ nước...xlsx")


def main(from_year: int) -> None:
    target = _lib.get_dsn().rsplit("@", 1)[-1]
    print(f"=== TRIỂN KHAI IMPORT (>= {from_year}) → {target} ===")
    print("[1/5] Giá sàn giao dịch + tỷ giá (sheet '2025')")
    import_exchange.run(import_exchange.DEFAULT_FILE, "2025", from_year, dry=False)
    print("[2/5] Giá sàn giao dịch 2026 (master, sheet '2026')")
    import_exchange.run(MASTER, "2026", from_year, dry=False)
    print("[3/5] Giá mủ nước (thu mua theo cty + theo khu vực)")
    import_latex.run(import_latex.DEFAULT_FILE, from_year, dry=False)
    print("[4/5] Giá physical USD/tấn (sheet 'Lưu')")
    import_physical_staff.run(import_physical_staff.DEFAULT_FILE, from_year, dry=False)
    print("[5/5] Giá sàn Tập đoàn ban hành (file 'Giá sàn 2024-2026.xlsx')")
    import_floor_table.run(from_year, dry=False)
    print("=== Báo cáo độ phủ ===")
    coverage_report.main(coverage_report.DEFAULT_OUT)
    print("=== HOÀN TẤT ===")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-year", type=int, default=_lib.MIN_YEAR)
    main(ap.parse_args().from_year)
