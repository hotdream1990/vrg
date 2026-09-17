#!/usr/bin/env python3
"""Chuyển Nhu cầu thị trường CŨ (ô chữ `market_demand`) sang phiếu có trường (`market_demand_item`).

Mặc định CHẠY THỬ: tách + kiểm từng phiếu bằng đúng luật của hệ thống (`policy.clean`), in tổng kết.
    --review FILE.xlsx   ghi bảng đối chiếu cho chủ dự án duyệt
    --commit             ghi thật (bỏ qua phiếu đã có `source_key` → chạy lại không nhân đôi)
    --refresh            như --commit, nhưng phiếu đã chuyển thì GHI ĐÈ theo cách tách hiện tại —
                         trừ phiếu người dùng đã tự sửa (updated_by khác tài khoản chuyển đổi)
    --undo               xoá mọi phiếu chuyển đổi (`source_key` bắt đầu bằng "legacy:")
    --dump FILE.json     đọc bản chữ cũ từ file thay vì DB (chạy thử trên máy dev)

Bảng chữ cũ KHÔNG bị sửa/xoá. Ghi qua `market_demand_item_repo.save` để có Nhật ký hoạt động.

Máy dev:  cd apps/api && uv run python ../../scripts/migrate-market-demand/convert.py [--commit]
Prod:     chép thư mục vào container rồi chạy bằng /app/.venv/bin/python với APP_ROOT=/app
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, os.environ.get("APP_ROOT", str(HERE.parents[1] / "apps" / "api")))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core import request_ctx  # noqa: E402
from app.core.db import ensure_schema, session_scope  # noqa: E402
from app.core.market_demand_meta import DATA_FIELDS  # noqa: E402
from app.services import market_demand_item_policy as policy  # noqa: E402
from app.services import market_demand_item_repo as repo  # noqa: E402
from legacy_build import build_items  # noqa: E402

ACTOR = "chuyen-doi-du-lieu"
AUDIT_NOTE = "Chuyển từ Nhu cầu thị trường dạng chữ (17/09/2026)"
REFRESH_NOTE = "Cập nhật phiếu chuyển đổi theo mẫu rút gọn (17/09/2026)"


def load_rows(dump: str | None) -> list[dict]:
    if dump:
        return json.loads(Path(dump).read_text(encoding="utf-8"))
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT as_of, company, content FROM market_demand "
                               "WHERE content <> '' ORDER BY as_of, company")).mappings().all()
    return [{**r, "as_of": r["as_of"].isoformat()} for r in rows]


def validate(items: list[dict]) -> list[tuple[dict, dict]]:
    """Mọi phiếu phải qua đúng luật lưu của hệ thống — sai 1 phiếu là dừng, không ghi nửa vời."""
    out, errors = [], []
    for it in items:
        try:
            out.append((it, policy.clean(it)))
        except HTTPException as exc:
            errors.append(f"{it['source_key']}: {exc.detail}")
    if errors:
        raise SystemExit("Phiếu không hợp lệ:\n  " + "\n  ".join(errors))
    return out


def existing_rows() -> dict[str, dict]:
    with session_scope() as db:
        rows = db.execute(text("SELECT id, source_key, updated_by FROM market_demand_item "
                               "WHERE source_key LIKE 'legacy:%'")).mappings().all()
    return {r["source_key"]: dict(r) for r in rows}


def _unchanged(item_id: int, clean: dict) -> bool:
    current = repo.get(item_id) or {}
    return all(current.get(f) == clean[f] for f in DATA_FIELDS)


def commit(pairs: list[tuple[dict, dict]], refresh: bool = False) -> Counter:
    done = existing_rows()
    stats: Counter = Counter()
    with request_ctx.use_note(REFRESH_NOTE if refresh else AUDIT_NOTE):
        for it, clean in pairs:
            row = done.get(it["source_key"])
            if row is None:
                repo.save({**clean, "id": None}, ACTOR, source_key=it["source_key"])
                stats["đã ghi"] += 1
            elif not refresh:
                stats["đã có, bỏ qua"] += 1
            elif row["updated_by"] != ACTOR:
                stats["người dùng đã sửa, giữ nguyên"] += 1   # không đè lên việc của đơn vị
            elif _unchanged(row["id"], clean):
                stats["không đổi"] += 1
            else:
                repo.save({**clean, "id": row["id"]}, ACTOR)
                stats["đã cập nhật"] += 1
    return stats


def undo() -> int:
    with session_scope() as db:
        ids = list(db.execute(text("SELECT id FROM market_demand_item "
                                   "WHERE source_key LIKE 'legacy:%'")).scalars())
    with request_ctx.use_note("Gỡ phiếu chuyển đổi Nhu cầu thị trường"):
        return sum(repo.delete(i, None) for i in ids)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dump")
    ap.add_argument("--review")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--commit", action="store_true")
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--undo", action="store_true")
    args = ap.parse_args()
    request_ctx.set_request(ACTOR, "")

    if args.undo:
        print(f"Đã xoá {undo()} phiếu chuyển đổi.")
        return
    rows = load_rows(args.dump)
    items = build_items(rows)
    pairs = validate(items)
    print(f"{len(rows)} bản chữ cũ → {len(items)} phiếu · "
          f"{dict(Counter(i['method'] for i in items))} · cần xem: {sum(bool(i['flag']) for i in items)}")
    if args.review:
        from review_xlsx import write_review
        write_review(items, args.review)
        print(f"Đã ghi bảng đối chiếu: {args.review}")
    if args.commit or args.refresh:
        print(f"Kết quả ghi: {dict(commit(pairs, refresh=args.refresh))}")
    else:
        print("Chạy thử — chưa ghi gì. Thêm --commit (hoặc --refresh) để ghi thật.")


if __name__ == "__main__":
    main()
