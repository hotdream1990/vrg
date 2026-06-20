"""Repository ghi/đọc giá quét (fact_price) + theo dõi lần quét (meta_crawl_run).

Upsert theo khóa (as_of, source, grade, contract, price_type) — quét lại cùng ngày
không tạo bản ghi trùng. Mọi query tham số hóa (tránh SQL injection).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

_UPSERT = text("""
    INSERT INTO fact_price
        (as_of, source, grade, contract, price_type, price, currency, unit, source_ts, run_id)
    VALUES
        (:as_of, :source, :grade, :contract, :price_type, :price, :currency, :unit, :source_ts, :run_id)
    ON CONFLICT (as_of, source, grade, contract, price_type) DO UPDATE SET
        price = EXCLUDED.price,
        currency = EXCLUDED.currency,
        unit = EXCLUDED.unit,
        source_ts = EXCLUDED.source_ts,
        run_id = EXCLUDED.run_id,
        ingested_at = now()
""")


def create_run(sources: str) -> int:
    """Mở 1 lần quét, trả run_id."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("INSERT INTO meta_crawl_run (sources) VALUES (:s) RETURNING id"),
            {"s": sources},
        ).one()
        return int(row[0])


def finish_run(run_id: int, status: str, rows: int, error: str | None = None) -> None:
    with session_scope() as db:
        db.execute(
            text("""
                UPDATE meta_crawl_run
                SET finished_at = now(), status = :st, rows = :rows, error = :err
                WHERE id = :id
            """),
            {"st": status, "rows": rows, "err": error, "id": run_id},
        )


def upsert_prices(records: list[dict[str, Any]], run_id: int) -> int:
    """Ghi danh sách bản ghi giá (đã chuẩn hóa từ crawler). Trả số bản ghi ghi được."""
    if not records:
        return 0
    rows = [
        {
            "as_of": r["as_of"],
            "source": r["source"],
            "grade": r["grade"],
            "contract": r.get("contract") or "",
            "price_type": r["price_type"],
            "price": r["price"],
            "currency": r["currency"],
            "unit": r["unit"],
            "source_ts": r.get("source_ts"),
            "run_id": run_id,
        }
        for r in records
    ]
    with session_scope() as db:
        db.execute(_UPSERT, rows)
    return len(rows)


def latest() -> list[dict[str, Any]]:
    """Giá mới nhất mỗi (source, grade) — phục vụ KPI/bảng dashboard."""
    ensure_schema()
    with session_scope() as db:
        result = db.execute(text("""
            SELECT DISTINCT ON (source, grade)
                source, grade, price, currency, unit, price_type, as_of, contract, ingested_at
            FROM fact_price
            ORDER BY source, grade, as_of DESC, ingested_at DESC
        """))
        return [dict(m) for m in result.mappings().all()]


def history(source: str, grade: str, days: int = 30) -> list[dict[str, Any]]:
    """Chuỗi giá theo ngày cho 1 (source, grade) — phục vụ biểu đồ lịch sử."""
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT as_of, price
                FROM fact_price
                WHERE source = :source AND grade = :grade
                  AND as_of >= current_date - CAST(:days AS integer)
                ORDER BY as_of
            """),
            {"source": source, "grade": grade, "days": days},
        )
        return [dict(m) for m in result.mappings().all()]


def prices_for_dates(target_date: str, prev_date: str) -> list[dict[str, Any]]:
    """Lấy giá đã quét đúng 2 ngày (T và T-1).

    Giữ cho mục đích khác; BẢN TIN dùng latest_two_for_bulletin() để mỗi chỉ số
    luôn lấy giá thật mới nhất, không phụ thuộc các sàn có cùng ngày hay không.
    """
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT source, grade, price, currency, unit, price_type, as_of, contract
                FROM fact_price
                WHERE as_of IN (:d1, :d2)
                ORDER BY source, grade, as_of
            """),
            {"d1": target_date, "d2": prev_date},
        )
        return [dict(m) for m in result.mappings().all()]


def latest_two_for_bulletin(as_of_max: str) -> list[dict[str, Any]]:
    """Cho mỗi (source, grade): 2 bản ghi as_of mới nhất <= as_of_max — phục vụ bản tin.

    curr = bản ghi mới nhất, prev = liền trước (để tính chênh lệch). Nhờ vậy mỗi chỉ số
    luôn dùng giá THẬT mới nhất sẵn có, không phụ thuộc các sàn có cùng ngày hay không
    (FX cập nhật T+0, sàn T-1/T-2, ANRPC trễ hơn...).
    """
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT source, grade, price, currency, unit, price_type, as_of, contract
                FROM (
                    SELECT source, grade, price, currency, unit, price_type, as_of, contract,
                           ROW_NUMBER() OVER (
                               PARTITION BY source, grade ORDER BY as_of DESC
                           ) AS rn
                    FROM fact_price
                    WHERE as_of <= CAST(:d AS date)
                ) t
                WHERE rn <= 2
                ORDER BY source, grade, as_of
            """),
            {"d": as_of_max},
        )
        return [dict(m) for m in result.mappings().all()]
