"""Dựng danh sách phiếu từ các bản ghi chữ cũ: tách tự động + mục soạn tay + đánh dấu chỗ cần xem.

Hàm thuần (không đụng DB) để chạy được cả trên máy dev (từ file dump) lẫn trong container prod.
"""
from __future__ import annotations

from datetime import date

import legacy_manual as M
import legacy_parse as P

NOTE_MAX = 2000


def _dmy(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _note(extra: str, as_of: str, original: str) -> str:
    """Ghi chú = phần diễn giải (nếu có) + NGUYÊN VĂN cũ — chủ dự án chốt giữ lại để đối chiếu."""
    head = f"{extra}\n" if extra else ""
    tail = f"Nội dung gốc ({_dmy(as_of)}): {' '.join(original.split())}"
    room = NOTE_MAX - len(head)
    return head + (tail if len(tail) <= room else tail[: room - 1] + "…")


def build_items(rows: list[dict]) -> list[dict]:
    """rows: [{as_of, company, content}] → phiếu (theo DemandItemIn) kèm `source_key`, `method`,
    `flag`, `original`. Mục không khớp mẫu và không có trong MANUAL ⇒ ValueError (không đoán)."""
    out: list[dict] = []
    for r in rows:
        as_of = str(r["as_of"])[:10]
        d = date.fromisoformat(as_of)
        for idx, frag in enumerate(P.split_items(r["content"]), 1):
            auto = P.auto_item(frag, d)
            if auto is not None:
                extra = auto.pop("extra_note")
                drafts, method = [{**auto, "note": extra}], "Tự động"
            elif (key := (as_of, r["company"], idx)) in M.MANUAL:
                drafts, method = [dict(x) for x in M.MANUAL[key]], "Soạn tay"
            else:
                raise ValueError(f"Mục chưa xử lý: {as_of} · {r['company']} · mục {idx}: {frag[:80]!r}")
            for k, item in enumerate(drafts, 1):
                flag = item.pop("flag", "")
                item.setdefault("status", "open")
                item.setdefault("contract_no", "")
                item.setdefault("contract_date", None)
                out.append({
                    **item, "company": r["company"], "as_of": as_of,
                    "note": _note(item.get("note", ""), as_of, frag),
                    "source_key": f"legacy:{as_of}:{r['company']}:{idx}.{k}",
                    "method": method, "flag": flag, "original": frag,
                })
    _flag_duplicates(out)
    return out


def _flag_duplicates(items: list[dict]) -> None:
    """Cùng đơn vị · khách · loại · số lượng · giá mà CHƯA có số HĐ riêng → có thể là một nhu cầu
    được ghi lại nhiều ngày (mô hình cũ nhập theo ngày). Chỉ ĐÁNH DẤU, không tự gộp."""
    first: dict[tuple, str] = {}
    for it in sorted(items, key=lambda x: x["as_of"]):
        if it["status"] == "signed":
            continue                                   # số HĐ khác nhau = các hợp đồng thật khác nhau
        key = (it["company"], it["customer"].lower(), it["grade"], it["qty"], it["qty_unit"],
               it["price"], it["currency"])
        if key in first and first[key] != it["as_of"]:
            same_time = next((x for x in items if x["as_of"] == first[key] and _same(x, it)), None)
            hint = "cùng thời gian giao" if same_time else "khác thời gian giao"
            msg = f"Có thể trùng phiếu ngày {_dmy(first[key])} ({hint})"
            it["flag"] = f"{it['flag']} · {msg}" if it["flag"] else msg
        else:
            first.setdefault(key, it["as_of"])


def _same(a: dict, b: dict) -> bool:
    keys = ("company", "grade", "qty", "price", "delivery_from", "delivery_to")
    return a["customer"].lower() == b["customer"].lower() and all(a[k] == b[k] for k in keys)
