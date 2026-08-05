#!/usr/bin/env python3
"""Chuyển dữ liệu CŨ sang cấu trúc HỢP ĐỒNG 2 CẤP (`sales_contract`) — chốt 30/07/2026.

Hai nguồn dữ liệu cũ:
  1. Mảng `sales` / `sales_own` trong payload `unit_daily_report` (kind='consumption') — mỗi ngày
     một nhóm dòng bán → **gộp theo số hợp đồng** thành hợp đồng "giao 1 lần" ĐÃ GIAO đúng ngày đó.
  2. `unit_stock_contract` — hợp đồng đã ký chưa giao (nhập rời, có vòng đời) → hợp đồng mẹ
     "giao 1 lần"; đã có `delivered_date` thì đánh dấu ĐÃ GIAO đúng ngày đó.

NGUYÊN TẮC:
  - KHÔNG xoá, KHÔNG sửa dữ liệu cũ — chỉ đọc và tạo bản ghi mới.
  - KHÔNG suy diễn dữ liệu: thiếu ngày/số lượng thì BỎ QUA và ghi vào danh sách cần rà tay,
    tuyệt đối không lấy số của ngày khác điền vào.
  - KHÔNG ĐẾM HAI LẦN: một lần giao mà đơn vị vừa ghi ở bảng hợp đồng tồn kho vừa ghi ở dòng
    tiêu thụ thì chỉ tạo MỘT hợp đồng (gộp ngày mở đợt + file của bảng tồn kho vào dòng tiêu thụ).
  - Chạy lại nhiều lần không nhân đôi: mỗi bản ghi mới mang `note` chứa khoá nguồn duy nhất
    (`[migrate:sale:…]` / `[migrate:stock#<id>]`) và được kiểm trước khi chèn.

Chạy:  uv run python scripts/migrate-sales-contracts.py [--commit] [--report FILE.md]
Hoàn tác:  uv run python scripts/migrate-sales-contracts.py --undo [--commit]
Mặc định chạy THỬ (dry-run), chỉ in ra sẽ tạo/gộp/bỏ qua bao nhiêu bản ghi.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from migrate_sales_parts import (  # noqa: E402
    CHANNELS, CONTRACT_TYPES, build_line, dmy, is_blank, line_docs, merge_docs, norm_code,
    note_dates, num, problem, sale_ccy)

DEFAULT_DSN = "postgresql://vrg:changeme@localhost:5433/vrg_caosu"
TAG_STOCK = "[migrate:stock#{id}]"
TAG_SALE = "[migrate:sale:{as_of}|{company}|{key}]"
SOURCES = {"sales": "mủ thu mua", "sales_own": "mủ khai thác"}

_INSERT = (
    "INSERT INTO sales_contract (company, parent_id, code, customer_id, delivery_type, "
    " contract_type, sign_date, expiry_date, start_date, lines, delivered, delivered_at, "
    " channel, to_company, files, payment_docs, note, updated_by) "
    "VALUES (%(company)s, NULL, %(code)s, NULL, 'single', %(contract_type)s, %(sign_date)s, "
    " NULL, %(start_date)s, %(lines)s::jsonb, %(delivered)s, %(delivered_at)s, %(channel)s, NULL, "
    " %(files)s::jsonb, %(payment_docs)s::jsonb, %(note)s, 'migration')")


def _done_tags(cur) -> set[str]:
    """Khoá nguồn đã chuyển ở lần chạy trước — chống nhân đôi khi chạy lại."""
    cur.execute("SELECT note FROM sales_contract WHERE updated_by = 'migration' AND note IS NOT NULL")
    return {t for (note,) in cur.fetchall() for t in note.split() if t.startswith("[migrate:")}


def _unit_currencies(cur) -> dict[str, str]:
    cur.execute("SELECT name, COALESCE(currency, 'VND') FROM member_unit")
    return dict(cur.fetchall())


# ---------------------------------------------------------------- dòng tiêu thụ cũ → hợp đồng

def plan_sales(cur, done: set[str]) -> tuple[list[dict], list[tuple], list[str], int]:
    """Dựng danh sách hợp đồng sẽ tạo từ hai mảng `sales`/`sales_own`.

    Gộp các dòng CÙNG (số hợp đồng, loại hợp đồng, hình thức tiêu thụ) trong một ngày thành MỘT
    hợp đồng nhiều dòng — đúng thực tế "một hợp đồng bán vài chủng loại", thay vì mỗi dòng một
    hợp đồng. Dòng không có số hợp đồng thì đứng riêng (không dám gộp theo phỏng đoán).
    """
    unit_ccy = _unit_currencies(cur)
    cur.execute("SELECT as_of, company, payload FROM unit_daily_report "
                "WHERE kind = 'consumption' ORDER BY as_of, company")
    plans: list[dict] = []
    day_flags: list[tuple] = []      # ngày đã xử lý trọn vẹn → bật cờ `sales_migrated`
    skipped: list[str] = []
    blanks = 0
    for as_of, company, payload in cur.fetchall():
        data = payload or {}
        day_ccy, day_fx = data.get("sales_ccy"), data.get("fx_revenue")
        rows, bad = [], []
        for table in ("sales", "sales_own"):
            for idx, ln in enumerate(data.get(table) or []):
                if not isinstance(ln, dict):
                    continue
                if is_blank(ln):
                    blanks += 1
                    continue
                why = problem(ln)
                if why:
                    bad.append(f"{as_of} · {company} · {table}[{idx}] ({ln.get('grade') or '—'}): {why}")
                else:
                    rows.append((table, idx, ln))
        # CẢ NGÀY hoặc KHÔNG: chuyển được một phần rồi bật cờ `sales_migrated` sẽ làm các dòng
        # bị bỏ qua BIẾN MẤT khỏi mọi báo cáo (mảng cũ hết được tính, mà cũng chưa có hợp đồng).
        if bad:
            skipped.extend(bad + [f"→ BỎ QUA CẢ NGÀY {as_of} · {company} (bổ sung số liệu rồi chạy lại)"])
            continue
        day_flags.append((as_of, company))
        groups: dict[tuple, dict] = {}
        for table, idx, ln in rows:
            code = norm_code(ln.get("code"))
            ct = ln.get("contract") if ln.get("contract") in CONTRACT_TYPES else None
            ch = ln.get("channel") if ln.get("channel") in CHANNELS else None
            key = (code or f"{table}#{idx}", ct, ch)
            g = groups.get(key)
            if g is None:
                tag = TAG_SALE.format(as_of=as_of, company=company,
                                      key="|".join(str(x or "") for x in key))
                g = groups[key] = {
                    "tag": tag, "company": company, "code": (ln.get("code") or f"{as_of}-{idx + 1}")[:80],
                    # Dòng bán cũ CÓ sẵn loại hợp đồng + hình thức tiêu thụ → chuyển thẳng, không
                    # để mất chỉ tiêu "HĐ dài hạn / HĐ chuyến" và "Xuất khẩu / trong nước".
                    "contract_type": ct, "channel": ch,
                    # Dữ liệu cũ không có ngày ký; lấy ngày giao làm ngày ký (ghi rõ trong ghi chú).
                    "sign_date": as_of, "start_date": as_of,
                    "delivered": True, "delivered_at": as_of,
                    "lines": [], "files": [], "payment_docs": [], "srcs": set(), "dates": set(),
                }
            f, p = line_docs(ln)
            g["lines"].append(build_line(ln, sale_ccy(ln.get("ccy"), day_ccy,
                                                      unit_ccy.get(company, "VND")), day_fx))
            g["files"] = merge_docs(g["files"], f)
            g["payment_docs"] = merge_docs(g["payment_docs"], p)
            g["srcs"].add(SOURCES[table])
            if note_dates(ln):
                g["dates"].add(note_dates(ln))
        for g in groups.values():
            if g["tag"] in done:
                continue
            extra = (" · " + " · ".join(sorted(g["dates"]))) if g["dates"] else ""
            g["note"] = (f"Chuyển từ dòng tiêu thụ cũ ({'/'.join(sorted(g['srcs']))}) — ngày ký lấy "
                         f"theo ngày giao {dmy(as_of)}{extra} {g['tag']}")
            plans.append(g)
    return plans, day_flags, skipped, blanks


# ---------------------------------------------------------------- hợp đồng tồn kho cũ → hợp đồng

def plan_stock(cur, sale_index: dict, done: set[str], today: date
               ) -> tuple[list[dict], list[dict], list[str], list[str]]:
    """Dựng danh sách hợp đồng tồn kho cũ sẽ TẠO MỚI và những cái sẽ GỘP vào hợp đồng đã có.

    Hợp đồng tồn kho ĐÃ GIAO thường là **cùng một lần giao** đã ghi ở dòng tiêu thụ (khớp số hợp
    đồng + ngày giao) → tạo thêm là cộng đôi sản lượng. Gặp trường hợp đó thì gộp: lấy `start_date`
    (ngày mở đợt, dòng tiêu thụ không có) và file của bảng tồn kho ghép vào hợp đồng đã tạo.
    """
    cur.execute("SELECT id, company, code, grade, qty, price, ccy, fx, start_date, delivery_date, "
                "delivered_date, files, file, filename FROM unit_stock_contract "
                "WHERE NOT migrated ORDER BY id")
    creates, merges, skipped, review = [], [], [], []
    for r in cur.fetchall():
        (cid, company, code, grade, qty, price, ccy, fx, start, sched, delivered, files,
         file_one, name_one) = r
        tag = TAG_STOCK.format(id=cid)
        if tag in done:
            continue
        if not grade or num(qty) is None or num(qty) <= 0:
            skipped.append(f"unit_stock_contract#{cid} · {company} · {code or '—'}: "
                           "thiếu chủng loại hoặc số lượng")
            continue
        docs_hd = merge_docs([{"file": f["file"], "filename": f.get("filename") or f["file"]}
                              for f in (files or []) if isinstance(f, dict) and f.get("file")]
                             or ([{"file": file_one, "filename": name_one or file_one}]
                                 if file_one else []))
        # Ô "Ngày giao" của bảng cũ được vài đơn vị dùng để ghi LỊCH GIAO DỰ KIẾN (cột lịch giao và
        # ngày giao trùng nhau, đều ở tương lai). Bảng cũ vẫn coi hàng NẰM TRONG tồn kho tới hết
        # ngày trước đó, nên chuyển thành "đã giao" là ghi tiêu thụ cho ngày CHƯA XẢY RA — và khoá
        # luôn bản ghi (cửa sổ sửa chặn ngày tương lai). Ngày giao ở tương lai ⇒ để ĐANG CHỜ GIAO.
        planned = delivered if delivered and delivered > today else None
        if planned:
            delivered = None
            review.append(f"{company} · HĐ {code or f'HĐ-{cid}'}: bảng cũ ghi ngày giao "
                          f"{dmy(planned)} (chưa tới) → để ĐANG CHỜ GIAO, đơn vị điền ngày giao "
                          "thật khi giao xong")
        twins = sale_index.get((company, norm_code(code)), []) if code else []
        if delivered and twins:
            same_day = [t for t in twins if t["delivered_at"] == delivered]
            # Cùng số hợp đồng + cùng số lượng nhưng lệch ngày = vẫn MỘT lần giao, đơn vị ghi hai
            # nơi lệch ngày nhau. Gộp theo số lượng, và ghi ra danh sách rà để đơn vị xác nhận ngày.
            same_qty = [t for t in twins
                        if abs(sum(num(ln["qty"]) or 0 for ln in t["lines"]) - num(qty)) < 0.001]
            pick = (same_day or same_qty)
            if pick:
                merges.append({"tag": tag, "into": pick[0]["tag"], "start_date": start,
                               "files": docs_hd, "id": cid})
                if not same_day:
                    review.append(f"{company} · HĐ {code} ({num(qty):g} tấn): bảng tồn kho ghi giao "
                                  f"{dmy(delivered)}, dòng tiêu thụ ghi {dmy(pick[0]['delivered_at'])} "
                                  "— đã gộp làm một, đơn vị xác nhận lại ngày giao đúng")
                continue
            # Trùng số hợp đồng nhưng khác cả ngày giao lẫn số lượng: không dám tạo (rủi ro cộng
            # đôi) và cũng không dám gộp (không biết vào lần giao nào) → để đơn vị rà.
            review.append(f"{company} · HĐ {code} (giao {dmy(delivered)}, {num(qty):g} tấn): trùng số "
                          "hợp đồng với dòng tiêu thụ cũ nhưng khác ngày giao — cần rà tay, "
                          "CHƯA đưa vào báo cáo")
            continue
        creates.append({
            "tag": tag, "company": company, "code": code or f"HĐ-{cid}",
            # Bảng cũ KHÔNG ghi dài hạn/chuyến, cũng không ghi hình thức tiêu thụ → để trống,
            # đơn vị bổ sung khi rà. Đoán một loại là làm sai luôn chỉ tiêu của báo cáo.
            "contract_type": None, "channel": None,
            "sign_date": start, "start_date": start,
            "delivered": delivered is not None, "delivered_at": delivered,
            "lines": [{"grade": str(grade)[:80], "qty": num(qty), "qty_dry": None,
                       "price": num(price), "ccy": ccy if ccy in ("VND", "USD", "LAK", "KHR") else "VND",
                       "fx": num(fx)}],
            "files": docs_hd, "payment_docs": [],
            "note": ("Chuyển từ hợp đồng tồn kho cũ"
                     + (f" · lịch giao {dmy(sched)}" if sched else "")
                     + (f" · bảng cũ ghi ngày giao {dmy(planned)} nhưng chưa tới nên để chờ giao"
                        if planned else "") + f" {tag}"),
        })
        review.append(f"{company} · HĐ {code or f'HĐ-{cid}'}: bổ sung LOẠI HỢP ĐỒNG (dài hạn/chuyến)"
                      + ("" if delivered is None else " và HÌNH THỨC TIÊU THỤ"))
    return creates, merges, skipped, review


def clash_with_manual(cur, sale_index: dict) -> list[str]:
    """Hợp đồng đơn vị ĐÃ TỰ NHẬP trên web trùng số với dòng tiêu thụ cũ.

    Không gộp tự động: hợp đồng tự nhập là CAM KẾT (có khách hàng, có thể giao nhiều lần), còn
    dòng cũ là LẦN GIAO. Để nguyên hai bên thì cam kết không bị trừ đi phần đã giao → khối "đã ký
    chưa giao" phồng lên. Đơn vị phải tự nối: chuyển lần giao thành phụ lục của hợp đồng đó.
    """
    cur.execute("SELECT company, code, sign_date FROM sales_contract "
                "WHERE COALESCE(updated_by, '') <> 'migration'")
    out = []
    for company, code, sign in cur.fetchall():
        twins = sale_index.get((company, norm_code(code)), [])
        if twins:
            out.append(f"{company} · HĐ {code} (đơn vị tự nhập, ký {dmy(sign)}): có {len(twins)} lần "
                       "giao cũ cùng số hợp đồng — cần nối lại thành phụ lục, nếu không phần cam kết "
                       "sẽ không bị trừ đi phần đã giao")
    return out


# ---------------------------------------------------------------- ghi xuống database

def _insert(cur, row: dict) -> None:
    cur.execute(_INSERT, {**row, "lines": json.dumps(row["lines"]),
                          "files": json.dumps(row["files"]),
                          "payment_docs": json.dumps(row["payment_docs"])})


def apply_plan(cur, sales: list[dict], stock: list[dict], merges: list[dict],
               day_flags: list[tuple]) -> None:
    for row in sales + stock:
        _insert(cur, row)
    for m in merges:
        # Ngày mở đợt của bảng tồn kho SỚM hơn ngày giao → giữ để khối "đã ký chưa giao" của
        # những ngày trước đó vẫn đúng như hệ thống cũ.
        cur.execute("SELECT id, files FROM sales_contract "
                    "WHERE updated_by = 'migration' AND strpos(note, %s) > 0", (m["into"],))
        for cid, files in cur.fetchall():
            merged = merge_docs([f for f in (files or []) if isinstance(f, dict) and f.get("file")],
                                m["files"])
            cur.execute(
                "UPDATE sales_contract SET start_date = LEAST(start_date, %s), files = %s::jsonb, "
                "  note = note || %s WHERE id = %s",
                (m["start_date"], json.dumps(merged),
                 f" · gộp hợp đồng tồn kho cũ {m['tag']}", cid))
        cur.execute("UPDATE unit_stock_contract SET migrated = true WHERE id = %s", (m["id"],))
    for row in stock:
        cur.execute("UPDATE unit_stock_contract SET migrated = true WHERE id = %s",
                    (int(row["tag"].split("#")[1].rstrip("]")),))
    for as_of, company in day_flags:
        # Mảng cũ VẪN GIỮ NGUYÊN để tra cứu; cờ này để báo cáo bỏ qua nó, nếu không sản lượng
        # bị đếm hai lần (mảng cũ + hợp đồng).
        cur.execute("UPDATE unit_daily_report SET payload = payload || '{\"sales_migrated\": true}'::jsonb "
                    "WHERE kind = 'consumption' AND as_of = %s AND company = %s", (as_of, company))


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


# ---------------------------------------------------------------- in ra & báo cáo

def _lines_block(title: str, items: list[str], limit: int = 40) -> list[str]:
    if not items:
        return []
    out = [f"\n{title}"] + [f"    - {s}" for s in items[:limit]]
    if len(items) > limit:
        out.append(f"    … còn {len(items) - limit} dòng nữa (xem file báo cáo --report)")
    return out


def _report(path: str, summary: list[str], skipped: list[str], review: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Báo cáo chuyển dữ liệu sang hợp đồng 2 cấp\n\n")
        f.write("\n".join(summary) + "\n")
        for title, items in (("## Bản ghi BỎ QUA (thiếu số liệu — cần bổ sung rồi chạy lại)", skipped),
                             ("## Cần rà tay trên web sau khi chuyển", review)):
            f.write(f"\n{title}\n\n")
            f.write("\n".join(f"- {s}" for s in items) + ("\n" if items else "_Không có._\n"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="Ghi thật (mặc định chỉ chạy thử)")
    ap.add_argument("--undo", action="store_true",
                    help="Hoàn tác: xoá bản sao đã tạo + gỡ cờ đã-chuyển (để chạy lại từ đầu)")
    ap.add_argument("--report", help="Ghi danh sách bỏ qua / cần rà tay ra file Markdown")
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
        done = _done_tags(cur)
        sales, day_flags, skip_sale, blanks = plan_sales(cur, done)
        index: dict[tuple, list] = defaultdict(list)
        for g in sales:
            index[(g["company"], norm_code(g["code"]))].append(g)
        today = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        stock, merges, skip_stock, review = plan_stock(cur, index, done, today)
        review = clash_with_manual(cur, index) + review
        if args.commit:
            apply_plan(cur, sales, stock, merges, day_flags)
            conn.commit()

    tonnes = sum(num(ln["qty"]) or 0 for g in sales + stock for ln in g["lines"])
    summary = [
        f"=== Chuyển dữ liệu sang hợp đồng 2 cấp — {mode} ===",
        f"  Dòng tiêu thụ cũ     → {len(sales)} hợp đồng "
        f"({sum(len(g['lines']) for g in sales)} dòng chi tiết)",
        f"  Hợp đồng tồn kho cũ  → {len(stock)} hợp đồng, {len(merges)} cái GỘP vào hợp đồng đã có "
        "(cùng số HĐ + cùng ngày giao — tránh đếm hai lần)",
        f"  Tổng sản lượng chuyển: {tonnes:,.3f} tấn",
        f"  Dòng trống bỏ qua (không có số liệu): {blanks}",
        f"  Ngày bật cờ đã-chuyển: {len(day_flags)}",
    ]
    print("\n".join(summary))
    skipped = skip_stock + skip_sale
    print("\n".join(_lines_block(
        f"⚠ {len(skipped)} dòng BỎ QUA (thiếu số liệu, KHÔNG suy diễn) — cần rà tay:", skipped)))
    print("\n".join(_lines_block(
        f"ℹ {len(review)} hợp đồng cần bổ sung thông tin bảng cũ không có:", review)))
    if args.report:
        _report(args.report, summary, skipped, review)
        print(f"\nĐã ghi báo cáo chi tiết: {args.report}")
    if not args.commit:
        print("\nChạy lại với --commit để ghi thật. Dữ liệu cũ KHÔNG bị xoá hay sửa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
