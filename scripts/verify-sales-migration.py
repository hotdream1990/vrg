#!/usr/bin/env python3
"""Đối chiếu SỐ LIỆU TRƯỚC và SAU khi chuyển sang hợp đồng 2 cấp — chạy sau `migrate-sales-contracts.py`.

Tính lại ĐỘC LẬP (đọc thẳng database, không qua mã của ứng dụng) rồi so từng đơn vị × tháng:
  - Sản lượng tiêu thụ (tấn) và doanh thu (đồng) của các dòng bán cũ ĐÃ chuyển  ↔  hợp đồng mới.
  - Sản lượng "đã ký chưa giao" tại một ngày mốc: bảng hợp đồng tồn kho cũ  ↔  hợp đồng mới.
Phần CHƯA chuyển (ngày bị bỏ qua vì thiếu số liệu) được liệt kê riêng, không trộn vào chênh lệch.

Chạy:  uv run python scripts/verify-sales-migration.py [--on 2026-08-01] [--csv FILE.csv]
Trả mã 1 nếu có chênh lệch vượt ngưỡng (mặc định 0,001 tấn / 1 đồng).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict

import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from migrate_sales_parts import is_blank, num, sale_ccy  # noqa: E402

DEFAULT_DSN = "postgresql://vrg:changeme@localhost:5433/vrg_caosu"
TRIEU = 1_000_000
TOL_QTY, TOL_MONEY = 0.001, 1.0


def _revenue(qty, price, ccy, fx) -> float | None:
    """Doanh thu 1 dòng quy về ĐỒNG — đúng quy ước dùng chung: VNĐ tính bằng triệu đ/tấn."""
    if qty is None or price is None:
        return None
    if (ccy or "VND") == "VND":
        return qty * price * TRIEU
    return None if not fx else qty * price * fx


def old_side(cur) -> tuple[dict, dict, list[str]]:
    """(đã chuyển, chưa chuyển, cảnh báo) — mỗi cái {(đơn vị, tháng): [tấn, đồng]}."""
    cur.execute("SELECT name, COALESCE(currency,'VND') FROM member_unit")
    unit_ccy = dict(cur.fetchall())
    cur.execute("SELECT as_of, company, payload FROM unit_daily_report WHERE kind = 'consumption'")
    moved: dict = defaultdict(lambda: [0.0, 0.0])
    left: dict = defaultdict(lambda: [0.0, 0.0])
    warn: list[str] = []
    for as_of, company, payload in cur.fetchall():
        data = payload or {}
        bucket = moved if data.get("sales_migrated") is True else left
        key = (company, as_of.strftime("%Y-%m"))
        for table in ("sales", "sales_own"):
            for ln in data.get(table) or []:
                if not isinstance(ln, dict) or is_blank(ln):
                    continue
                qty = num(ln.get("qty"))
                if qty is None or qty <= 0:
                    continue
                ccy = sale_ccy(ln.get("ccy"), data.get("sales_ccy"), unit_ccy.get(company, "VND"))
                fx = num(ln.get("fx")) if num(ln.get("fx")) is not None else num(data.get("fx_revenue"))
                rev = _revenue(qty, num(ln.get("price")), ccy, fx)
                if rev is None:
                    warn.append(f"{as_of} · {company} · {ln.get('grade')}: không tính được doanh thu "
                                "(thiếu đơn giá hoặc tỷ giá) — cả hai bên đều bỏ qua")
                bucket[key][0] += qty
                bucket[key][1] += rev or 0.0
    return moved, left, warn


def new_side(cur) -> tuple[dict, dict]:
    """Hợp đồng do script tạo, ĐÃ GIAO → hai rổ {(đơn vị, tháng): [tấn, đồng]}.

    Tách theo NGUỒN: hợp đồng dựng từ dòng tiêu thụ cũ (so 1-1 với số cũ) và hợp đồng dựng từ
    bảng hợp đồng tồn kho cũ (lần giao chỉ ghi ở bảng đó, dòng tiêu thụ KHÔNG có → là phần TĂNG
    THÊM hợp lệ, không phải chênh lệch).
    """
    cur.execute("SELECT company, delivered_at, lines, note FROM sales_contract "
                "WHERE updated_by = 'migration' AND delivered_at IS NOT NULL")
    from_sale: dict = defaultdict(lambda: [0.0, 0.0])
    from_stock: dict = defaultdict(lambda: [0.0, 0.0])
    for company, at, lines, note in cur.fetchall():
        bucket = from_sale if "[migrate:sale:" in (note or "") else from_stock
        key = (company, at.strftime("%Y-%m"))
        for ln in lines or []:
            qty = num(ln.get("qty"))
            if qty is None:
                continue
            bucket[key][0] += qty
            bucket[key][1] += _revenue(qty, num(ln.get("price")), ln.get("ccy"),
                                       num(ln.get("fx"))) or 0.0
    return from_sale, from_stock


def signed_undelivered(cur, on: str) -> tuple[dict, dict]:
    """Khối "đã ký chưa giao" tại ngày mốc — bảng cũ (chưa chuyển + đã chuyển) và bảng mới."""
    cur.execute("SELECT company, sum(qty) FROM unit_stock_contract "
                "WHERE start_date <= %s AND (delivered_date IS NULL OR delivered_date > %s) "
                "GROUP BY 1", (on, on))
    old = {c: float(q or 0) for c, q in cur.fetchall()}
    cur.execute("SELECT company, lines FROM sales_contract WHERE updated_by = 'migration' "
                " AND start_date <= %s AND (delivered_at IS NULL OR delivered_at > %s)", (on, on))
    new: dict = defaultdict(float)
    for company, lines in cur.fetchall():
        new[company] += sum(num(ln.get("qty")) or 0.0 for ln in lines or [])
    return old, dict(new)


def _diff_rows(old: dict, new: dict) -> list[tuple]:
    rows = []
    for key in sorted(set(old) | set(new)):
        o, n = old.get(key, [0.0, 0.0]), new.get(key, [0.0, 0.0])
        rows.append((*key, o[0], n[0], n[0] - o[0], o[1], n[1], n[1] - o[1]))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--on", default=None, help="Ngày mốc so khối đã-ký-chưa-giao (mặc định hôm nay)")
    ap.add_argument("--csv", help="Ghi bảng đối chiếu đơn vị × tháng ra file CSV")
    args = ap.parse_args()
    on = args.on or __import__("datetime").date.today().isoformat()

    with psycopg.connect(os.environ.get("DATABASE_URL", DEFAULT_DSN)) as conn, conn.cursor() as cur:
        moved, left, warn = old_side(cur)
        new, extra = new_side(cur)
        old_blk, new_blk = signed_undelivered(cur, on)

    rows = _diff_rows(moved, new)
    bad = [r for r in rows if abs(r[4]) > TOL_QTY or abs(r[7]) > TOL_MONEY]
    print("=== Đối chiếu tiêu thụ: dòng bán cũ ĐÃ chuyển  ↔  hợp đồng mới ===")
    print(f"  Ô đơn vị × tháng: {len(rows)} — lệch: {len(bad)}")
    print(f"  Tổng tấn  : cũ {sum(r[2] for r in rows):,.3f}  |  mới {sum(r[3] for r in rows):,.3f}")
    print(f"  Tổng đồng : cũ {sum(r[5] for r in rows):,.0f}  |  mới {sum(r[6] for r in rows):,.0f}")
    for r in bad[:30]:
        print(f"    ✗ {r[0]} · {r[1]}: tấn {r[2]:,.3f} → {r[3]:,.3f} ({r[4]:+,.3f}) · "
              f"đồng {r[5]:,.0f} → {r[6]:,.0f} ({r[7]:+,.0f})")

    if extra:
        print(f"\nℹ TĂNG THÊM từ bảng hợp đồng tồn kho cũ (lần giao dòng tiêu thụ không có): "
              f"{sum(v[0] for v in extra.values()):,.3f} tấn — {len(extra)} ô đơn vị × tháng")
        for (company, month), v in sorted(extra.items())[:20]:
            print(f"    + {company} · {month}: {v[0]:,.3f} tấn")

    if left:
        print(f"\n⚠ CHƯA chuyển (ngày bị bỏ qua vì thiếu số liệu): {len(left)} ô đơn vị × tháng, "
              f"{sum(v[0] for v in left.values()):,.3f} tấn")
        for (company, month), v in sorted(left.items()):
            print(f"    - {company} · {month}: {v[0]:,.3f} tấn")

    keys = sorted(set(old_blk) | set(new_blk))
    blk_bad = [k for k in keys if abs(new_blk.get(k, 0) - old_blk.get(k, 0)) > TOL_QTY]
    print(f"\n=== Đối chiếu 'đã ký chưa giao' tại {on} ===")
    print(f"  Cũ {sum(old_blk.values()):,.3f} tấn  |  mới {sum(new_blk.values()):,.3f} tấn  "
          f"— đơn vị lệch: {len(blk_bad)}")
    for k in blk_bad[:30]:
        print(f"    ✗ {k}: {old_blk.get(k, 0):,.3f} → {new_blk.get(k, 0):,.3f}")

    if warn:
        print(f"\nℹ {len(warn)} dòng không tính được doanh thu (thiếu đơn giá/tỷ giá) — "
              "hai bên đều bỏ qua nên không gây lệch:")
        for w in warn[:10]:
            print(f"    - {w}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Đơn vị", "Tháng", "Tấn (cũ)", "Tấn (mới)", "Lệch tấn",
                        "Đồng (cũ)", "Đồng (mới)", "Lệch đồng"])
            w.writerows(rows)
        print(f"\nĐã ghi bảng đối chiếu: {args.csv}")
    return 1 if bad or blk_bad else 0


if __name__ == "__main__":
    sys.exit(main())
