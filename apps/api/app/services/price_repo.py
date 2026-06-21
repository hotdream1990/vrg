"""Repository ghi/đọc giá quét (fact_price) + theo dõi lần quét (meta_crawl_run).

Upsert theo khóa (as_of, source, grade, contract, price_type) — quét lại cùng ngày
không tạo bản ghi trùng. Mọi query tham số hóa (tránh SQL injection).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text

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


def list_records(source: str | None = None, grade: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Bản ghi giá để quản lý: lọc nguồn/chỉ số/khoảng ngày + phân trang. Trả {records, total}."""
    ensure_schema()
    where: list[str] = []
    params: dict[str, Any] = {}
    if source:
        where.append("source = :source")
        params["source"] = source
    if grade:
        where.append("grade ILIKE :grade")
        params["grade"] = f"%{grade}%"
    if date_from:
        where.append("as_of >= CAST(:dfrom AS date)")
        params["dfrom"] = date_from
    if date_to:
        where.append("as_of <= CAST(:dto AS date)")
        params["dto"] = date_to
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with session_scope() as db:
        total = db.execute(text(f"SELECT count(*) FROM fact_price {clause}"), params).scalar() or 0
        rows = db.execute(
            text(f"""
                SELECT as_of, source, grade, contract, price_type, price, currency, unit, ingested_at
                FROM fact_price
                {clause}
                ORDER BY as_of DESC, source, grade, contract, price_type
                LIMIT :lim OFFSET :off
            """),
            {**params, "lim": limit, "off": offset},
        ).mappings().all()
        return {"records": [dict(m) for m in rows], "total": int(total)}


def upsert_record(rec: dict[str, Any]) -> None:
    """Thêm/sửa 1 bản ghi giá thủ công. Khóa: (as_of, source, grade, contract, price_type)."""
    ensure_schema()
    with session_scope() as db:
        db.execute(
            text("""
                INSERT INTO fact_price
                    (as_of, source, grade, contract, price_type, price, currency, unit, run_id)
                VALUES
                    (:as_of, :source, :grade, :contract, :price_type, :price, :currency, :unit, NULL)
                ON CONFLICT (as_of, source, grade, contract, price_type) DO UPDATE SET
                    price = EXCLUDED.price, currency = EXCLUDED.currency,
                    unit = EXCLUDED.unit, ingested_at = now()
            """),
            {
                "as_of": rec["as_of"], "source": rec["source"], "grade": rec["grade"],
                "contract": rec.get("contract") or "", "price_type": rec["price_type"],
                "price": rec["price"], "currency": rec["currency"], "unit": rec["unit"],
            },
        )


def delete_record(as_of: str, source: str, grade: str, contract: str, price_type: str) -> bool:
    """Xóa 1 bản ghi theo khóa. Trả True nếu có xóa."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(
            text("""
                DELETE FROM fact_price
                WHERE as_of = CAST(:as_of AS date) AND source = :source AND grade = :grade
                  AND contract = :contract AND price_type = :price_type
            """),
            {"as_of": as_of, "source": source, "grade": grade,
             "contract": contract, "price_type": price_type},
        )
        return res.rowcount > 0


def prices_since(
    sources: list[str], days: int = 30,
    date_from: str | None = None, date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Bản ghi các nguồn cho lưới Bảng tính giá. Có date_from/date_to thì lọc khoảng;
    ngược lại lấy `days` ngày gần nhất."""
    ensure_schema()
    if not sources:
        return []
    where = ["source IN :srcs"]
    params: dict[str, Any] = {"srcs": sources}
    if date_from or date_to:
        if date_from:
            where.append("as_of >= CAST(:dfrom AS date)")
            params["dfrom"] = date_from
        if date_to:
            where.append("as_of <= CAST(:dto AS date)")
            params["dto"] = date_to
    else:
        where.append("as_of >= current_date - CAST(:days AS integer)")
        params["days"] = days
    stmt = text(f"""
        SELECT as_of, source, grade, price, unit
        FROM fact_price
        WHERE {" AND ".join(where)}
        ORDER BY as_of
    """).bindparams(bindparam("srcs", expanding=True))
    with session_scope() as db:
        result = db.execute(stmt, params)
        return [dict(m) for m in result.mappings().all()]


def purchase_sheet(date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    """Lưới giá thu mua mủ nước (source=vrg): công ty × ngày. Trả {companies, dates, values}.

    dates: mới nhất trước. values[company][date] = giá đồng/độ TSC.
    """
    ensure_schema()
    where = ["source = 'vrg'", "price_type = 'purchase'"]
    params: dict[str, Any] = {}
    if date_from:
        where.append("as_of >= CAST(:dfrom AS date)")
        params["dfrom"] = date_from
    if date_to:
        where.append("as_of <= CAST(:dto AS date)")
        params["dto"] = date_to
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT as_of, grade, price FROM fact_price "
                 f"WHERE {' AND '.join(where)} ORDER BY as_of DESC"),
            params,
        ).mappings().all()

    dates: list[str] = []
    seen: set[str] = set()
    values: dict[str, dict[str, float]] = {}
    for r in rows:
        d = str(r["as_of"])
        if d not in seen:
            seen.add(d)
            dates.append(d)
        values.setdefault(r["grade"], {})[d] = float(r["price"])

    from app.services import member_unit_repo

    return {"companies": member_unit_repo.active_names(), "dates": dates, "values": values}


def delete_purchase_date(as_of: str) -> int:
    """Xoá toàn bộ giá thu mua mủ nước của 1 ngày (source=vrg). Trả số bản ghi đã xoá."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(
            text("DELETE FROM fact_price WHERE source = 'vrg' AND price_type = 'purchase' "
                 "AND as_of = CAST(:d AS date)"),
            {"d": as_of},
        )
        return res.rowcount


def latest_purchase_by_company(as_of_max: str) -> dict[str, float]:
    """Giá thu mua mủ nước mới nhất (<= ngày) theo công ty VRG (source=vrg).

    Trả {công ty: giá đồng/độ TSC}. Phục vụ mục 'Giá mủ nguyên liệu' của bản tin.
    """
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT DISTINCT ON (grade) grade, price
                FROM fact_price
                WHERE source = 'vrg' AND price_type = 'purchase'
                  AND as_of <= CAST(:d AS date)
                ORDER BY grade, as_of DESC, ingested_at DESC
            """),
            {"d": as_of_max},
        )
        return {m["grade"]: float(m["price"]) for m in result.mappings().all()}


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
