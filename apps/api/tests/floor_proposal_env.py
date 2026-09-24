"""Dữ liệu nền cho test phương án giá sàn nháp: 1 lần ban hành GIẢ ở năm 1990 (không đụng số thật).

Phương án của test đặt ngày 02/01/1990 ⇒ "lần ban hành trước" chỉ có thể là lần giả này, nên kết quả
không phụ thuộc DB đang chứa số liệu thật hay trống.
"""
from __future__ import annotations

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import floor_proposal as fp

LAN = -424242
PREV_DAY = "1990-01-01"
AS_OF = "1990-01-02"
SKIM = "Skim Block"


def prev_fob(i: int) -> float:
    return 2000.0 + 10 * i


def prev_vnd(i: int) -> float:
    return 51_000_000.0 + 250_000 * i


def seed() -> None:
    ensure_schema()
    with session_scope() as db:
        db.execute(text("DELETE FROM vrg_floor_price WHERE lan = :l"), {"l": LAN})
        for i, (_, g) in enumerate(fp.TT_GRADES):
            db.execute(text("INSERT INTO vrg_floor_price (lan, as_of, grade, fob_usd, domestic_vnd) "
                            "VALUES (:l, CAST(:d AS date), :g, :f, :v)"),
                       {"l": LAN, "d": PREV_DAY, "g": g, "f": None if g == SKIM else prev_fob(i),
                        "v": prev_vnd(i)})


def clear() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM vrg_floor_price WHERE lan = :l"), {"l": LAN})


def proposal() -> dict:
    """Phương án 'mức mô hình' giả: mô hình = lần trước + 1 bước (5 USD) cho mọi dòng FOB."""
    rows = []
    for i, (_, g) in enumerate(fp.TT_GRADES):
        if g == SKIM:
            rows.append({"grade": g, "model_vnd": prev_vnd(i) + 50_000, "vnd": prev_vnd(i) + 50_000,
                         "origin": "model"})
            continue
        row = {"prev_fob": prev_fob(i), "prev_vnd": prev_vnd(i)}
        m = prev_fob(i) + 5
        rows.append({"grade": g, "model_fob": m, "fob": m, "model_vnd": fp.vnd_from_fob(row, m),
                     "vnd": fp.vnd_from_fob(row, m), "origin": "model"})
    return fp.sanitize({"as_of": AS_OF, "model": "v2", "base": "model", "rows": rows, "log": []})
