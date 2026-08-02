#!/usr/bin/env python3
"""Chuyển dữ liệu CŨ sang cấu trúc HỢP ĐỒNG 2 CẤP (`sales_contract`) — chốt 30/07/2026.

Hai nguồn dữ liệu cũ:
  1. `unit_stock_contract` — hợp đồng đã ký chưa giao (nhập rời, có vòng đời) →
     hợp đồng mẹ loại "giao 1 lần"; đã có `delivered_date` thì đánh dấu ĐÃ GIAO đúng ngày đó.
  2. Mảng `sales` / `sales_own` trong payload `unit_daily_report` (kind='consumption') →
     mỗi DÒNG BÁN thành một hợp đồng "giao 1 lần" ĐÃ GIAO vào ĐÚNG NGÀY của bản ghi.

NGUYÊN TẮC:
  - KHÔNG xoá, KHÔNG sửa dữ liệu cũ — chỉ đọc và tạo bản ghi mới.
  - KHÔNG suy diễn dữ liệu: thiếu ngày/số lượng thì BỎ QUA và ghi vào danh sách cần rà tay,
    tuyệt đối không lấy số của ngày khác điền vào.
  - Chạy lại nhiều lần không nhân đôi: mỗi bản ghi mới mang `note` chứa khoá nguồn duy nhất
    (`[migrate:stock#<id>]` / `[migrate:sale:<ngày>|<đơn vị>|<bảng>|<thứ tự>]`) và được kiểm trước khi chèn.

Chạy:  uv run python scripts/migrate-sales-contracts.py [--commit]
Hoàn tác:  uv run python scripts/migrate-sales-contracts.py --undo [--commit]
Mặc định chạy THỬ (dry-run), chỉ in ra sẽ tạo/xoá bao nhiêu bản ghi.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg

DEFAULT_DSN = "postgresql://vrg:changeme@localhost:5433/vrg_caosu"
TAG_STOCK = "[migrate:stock#{id}]"
TAG_SALE = "[migrate:sale:{as_of}|{company}|{table}|{idx}]"

# `channel` cũ chỉ có export | domestic; "internal" (tiêu thụ nội bộ) là khái niệm MỚI,
# dữ liệu cũ không có nên không được đoán — giữ nguyên giá trị cũ.
_CHANNELS = {"export", "domestic"}

# Loại HỢP ĐỒNG của dòng bán cũ — chuyển thẳng sang cột `contract_type` của bảng mới.
_CONTRACT_TYPES = {"long_term", "spot"}


def _num(v):
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _line(grade, qty, price, ccy, fx):
    """Một dòng chi tiết hợp đồng. `qty_dry`/`cost` để None — dữ liệu cũ KHÔNG có, không bịa."""
    return {"grade": str(grade or "")[:80], "qty": _num(qty), "qty_dry": None,
            "price": _num(price), "ccy": ccy if ccy in ("VND", "USD", "LAK", "KHR") else "VND",
            "fx": _num(fx), "cost": None}


def _sale_ccy(line_ccy, day_ccy, unit_ccy: str) -> str:
    """Loại tiền của 1 dòng bán CŨ — phải giữ ĐÚNG cách báo cáo cũ đọc, nếu không số lệch hẳn.

    Dòng cũ hiếm khi ghi loại tiền riêng: hệ thống cũ lấy loại tiền mức NGÀY (`sales_ccy`), thiếu
    nữa thì suy theo đơn vị — trong nước VNĐ, đơn vị nước ngoài USD. Mặc định cứng "VND" ở đây làm
    giá 1.610 USD/tấn bị đọc thành 1.610 triệu đ/tấn (doanh thu phồng ~38 lần).
    """
    for c in (line_ccy, day_ccy):
        if c in ("VND", "USD", "LAK", "KHR"):
            return c
    return "VND" if (unit_ccy or "VND") == "VND" else "USD"


def _unit_currencies(cur) -> dict[str, str]:
    cur.execute("SELECT name, COALESCE(currency, 'VND') FROM member_unit")
    return dict(cur.fetchall())


def _exists(cur, tag: str) -> bool:
    cur.execute("SELECT 1 FROM sales_contract WHERE note LIKE %s LIMIT 1", (f"%{tag}%",))
    return cur.fetchone() is not None


def _insert(cur, row: dict) -> None:
    cur.execute(
        "INSERT INTO sales_contract (company, parent_id, code, customer_id, delivery_type, "
        " contract_type, sign_date, expiry_date, start_date, lines, delivered, delivered_at, "
        " channel, to_company, files, note, updated_by) "
        "VALUES (%(company)s, NULL, %(code)s, NULL, 'single', %(contract_type)s, %(sign_date)s, "
        " NULL, %(start_date)s, "
        " %(lines)s::jsonb, %(delivered)s, %(delivered_at)s, %(channel)s, NULL, "
        " %(files)s::jsonb, %(note)s, 'migration')",
        row)


def migrate_stock_contracts(cur, commit: bool) -> tuple[int, list[str], list[str]]:
    """`unit_stock_contract` → hợp đồng mẹ giao-1-lần (giữ nguyên ngày ký & ngày giao thực tế)."""
    cur.execute("SELECT id, company, code, grade, qty, price, ccy, fx, start_date, "
                "delivered_date, files FROM unit_stock_contract ORDER BY id")
    made, skipped, review = 0, [], []
    for r in cur.fetchall():
        cid, company, code, grade, qty, price, ccy, fx, start, delivered, files = r
        tag = TAG_STOCK.format(id=cid)
        if _exists(cur, tag):
            continue
        if not grade or _num(qty) is None:
            skipped.append(f"unit_stock_contract#{cid} ({company}): thiếu chủng loại hoặc số lượng")
            continue
        row = {
            "company": company, "code": code or f"HĐ-{cid}", "sign_date": start,
            # Hợp đồng tồn kho cũ đã có sẵn vòng đời (bắt đầu → giao) → giữ nguyên sang đợt mới.
            "start_date": start,
            # Bảng cũ KHÔNG ghi dài hạn/chuyến → để trống, đơn vị bổ sung khi rà (xem danh sách
            # in ra cuối script). Đoán một loại là làm sai luôn chỉ tiêu của báo cáo.
            "contract_type": None,
            "lines": json.dumps([_line(grade, qty, price, ccy, fx)]),
            "delivered": delivered is not None,
            "delivered_at": delivered,
            # Hợp đồng tồn kho cũ KHÔNG ghi hình thức tiêu thụ → để trống, đơn vị bổ sung khi rà.
            "channel": None,
            "files": json.dumps(files or []),
            "note": f"Chuyển từ hợp đồng tồn kho cũ {tag}",
        }
        if commit:
            _insert(cur, row)
            # Đánh dấu bản ghi CŨ đã chuyển: giữ nguyên để tra cứu nhưng báo cáo bỏ qua.
            cur.execute("UPDATE unit_stock_contract SET migrated = true WHERE id = %s", (cid,))
        made += 1
        review.append(f"{company} · {code or f'HĐ-{cid}'}: bổ sung LOẠI HỢP ĐỒNG (dài hạn/chuyến)")
    return made, skipped, review


def migrate_sale_lines(cur, commit: bool) -> tuple[int, list[str]]:
    """Mỗi dòng bán trong payload ngày → 1 hợp đồng giao-1-lần ĐÃ GIAO vào đúng ngày đó.

    Sau khi chuyển xong một ngày, bật cờ `sales_migrated` trong payload: mảng cũ VẪN GIỮ NGUYÊN
    để tra cứu, nhưng báo cáo sẽ bỏ qua nó — nếu không sản lượng bị đếm hai lần (mảng cũ + hợp đồng).
    """
    unit_ccy = _unit_currencies(cur)
    cur.execute("SELECT as_of, company, payload FROM unit_daily_report "
                "WHERE kind = 'consumption' ORDER BY as_of, company")
    made, skipped = 0, []
    for as_of, company, payload in cur.fetchall():
        data = payload or {}
        # Loại tiền & tỷ giá mức NGÀY — dùng làm mức dự phòng cho dòng không ghi riêng.
        day_ccy, day_fx = data.get("sales_ccy"), data.get("fx_revenue")
        # CẢ NGÀY hoặc KHÔNG: chuyển được một phần rồi bật cờ `sales_migrated` sẽ làm các dòng
        # bị bỏ qua BIẾN MẤT khỏi mọi báo cáo (mảng cũ hết được tính, mà cũng chưa có hợp đồng).
        bad = [f"{as_of} {company} {t}[{i}]: thiếu chủng loại hoặc số lượng"
               for t in ("sales", "sales_own")
               for i, row in enumerate(data.get(t) or [])
               if isinstance(row, dict) and (_num(row.get("qty")) is None or not row.get("grade"))]
        if bad:
            skipped.extend(bad + [f"→ BỎ QUA CẢ NGÀY {as_of} · {company} (sửa dữ liệu rồi chạy lại)"])
            continue
        moved_this_day = 0
        for table in ("sales", "sales_own"):
            for idx, ln in enumerate(data.get(table) or []):
                if not isinstance(ln, dict):
                    continue
                tag = TAG_SALE.format(as_of=as_of, company=company, table=table, idx=idx)
                if _exists(cur, tag):
                    continue
                ch = ln.get("channel")
                src = "mủ thu mua" if table == "sales" else "mủ khai thác"
                row = {
                    "company": company,
                    "code": (ln.get("code") or f"{as_of}-{idx + 1}")[:80],
                    # Dòng bán cũ CÓ sẵn loại hợp đồng → chuyển thẳng, không để mất chỉ tiêu
                    # "HĐ dài hạn / HĐ chuyến". Giá trị lạ thì để trống chứ không quy về một loại.
                    "contract_type": (ln.get("contract")
                                      if ln.get("contract") in _CONTRACT_TYPES else None),
                    "sign_date": as_of, "start_date": as_of,
                    "lines": json.dumps([_line(
                        ln.get("grade"), ln.get("qty"), ln.get("price"),
                        _sale_ccy(ln.get("ccy"), day_ccy, unit_ccy.get(company, "VND")),
                        ln.get("fx") if ln.get("fx") is not None else day_fx)]),
                    "delivered": True, "delivered_at": as_of,
                    "channel": ch if ch in _CHANNELS else None,
                    "files": json.dumps(ln.get("files") or []),
                    "note": f"Chuyển từ dòng tiêu thụ cũ ({src}) {tag}",
                }
                if commit:
                    _insert(cur, row)
                made += 1
                moved_this_day += 1
        if moved_this_day and commit:
            cur.execute(
                "UPDATE unit_daily_report SET payload = payload || '{\"sales_migrated\": true}'::jsonb "
                "WHERE kind = 'consumption' AND as_of = %s AND company = %s", (as_of, company))
    return made, skipped


def undo(cur, commit: bool) -> dict[str, int]:
    """Xoá bản sao đã tạo VÀ gỡ cờ đã-chuyển — hai việc phải đi cùng nhau.

    Chỉ xoá mà quên gỡ cờ thì bản gốc cũ vẫn bị báo cáo bỏ qua → số biến mất khỏi cả hai nguồn.
    Chỉ đụng vào bản ghi do script tạo (`updated_by = 'migration'`), không chạm hợp đồng nhập tay.
    """
    cur.execute("SELECT count(*) FROM sales_contract WHERE updated_by = 'migration'")
    n_copies = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM unit_stock_contract WHERE migrated")
    n_flags = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM unit_daily_report WHERE kind = 'consumption' "
                " AND COALESCE((payload->>'sales_migrated')::boolean, false)")
    n_days = cur.fetchone()[0]
    if commit:
        cur.execute("DELETE FROM sales_contract WHERE updated_by = 'migration'")
        cur.execute("UPDATE unit_stock_contract SET migrated = false WHERE migrated")
        cur.execute("UPDATE unit_daily_report SET payload = payload - 'sales_migrated' "
                    " WHERE kind = 'consumption' "
                    "   AND COALESCE((payload->>'sales_migrated')::boolean, false)")
    return {"copies": n_copies, "contract_flags": n_flags, "day_flags": n_days}


def _print_list(title: str, items: list[str], limit: int = 50) -> None:
    if not items:
        return
    print(f"\n{title}")
    for s in items[:limit]:
        print(f"    - {s}")
    if len(items) > limit:
        print(f"    … còn {len(items) - limit} dòng nữa")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="Ghi thật (mặc định chỉ chạy thử)")
    ap.add_argument("--undo", action="store_true",
                    help="Hoàn tác: xoá bản sao đã tạo + gỡ cờ đã-chuyển (để chạy lại từ đầu)")
    args = ap.parse_args()
    dsn = os.environ.get("DATABASE_URL", DEFAULT_DSN)
    mode = "ĐÃ GHI" if args.commit else "CHẠY THỬ (chưa ghi)"

    if args.undo:
        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            n = undo(cur, args.commit)
            if args.commit:
                conn.commit()
        print(f"=== HOÀN TÁC chuyển đổi — {mode} ===")
        print(f"  Xoá bản sao ở sales_contract   : {n['copies']}")
        print(f"  Gỡ cờ migrated (hợp đồng cũ)   : {n['contract_flags']}")
        print(f"  Gỡ cờ sales_migrated (ngày)    : {n['day_flags']}")
        if not args.commit:
            print("\nChạy lại với --undo --commit để hoàn tác thật.")
        return 0

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        n_stock, skip_stock, review = migrate_stock_contracts(cur, args.commit)
        n_sale, skip_sale = migrate_sale_lines(cur, args.commit)
        if args.commit:
            conn.commit()

    print(f"=== Chuyển dữ liệu sang hợp đồng 2 cấp — {mode} ===")
    print(f"  Hợp đồng tồn kho cũ  → {n_stock} hợp đồng")
    print(f"  Dòng tiêu thụ cũ     → {n_sale} hợp đồng")
    skipped = skip_stock + skip_sale
    _print_list(f"⚠ {len(skipped)} bản ghi BỎ QUA (thiếu dữ liệu, KHÔNG suy diễn) — cần rà tay:",
                skipped)
    _print_list(f"ℹ {len(review)} hợp đồng chuyển được nhưng THIẾU trường bảng cũ không có "
                "— cần bổ sung trên web:", review)
    if not args.commit:
        print("\nChạy lại với --commit để ghi thật. Dữ liệu cũ KHÔNG bị xoá hay sửa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
