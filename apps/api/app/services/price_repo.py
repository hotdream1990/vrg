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
    ON CONFLICT (as_of, source, grade, price_type) DO UPDATE SET
        contract = EXCLUDED.contract,
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


def recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    """Lịch sử các lần quét gần nhất (manual + cron) — cho bảng Nhật ký quét trên UI."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("""
                SELECT id, started_at, finished_at, sources, status, rows, error
                FROM meta_crawl_run ORDER BY started_at DESC LIMIT :n
            """),
            {"n": limit},
        )
        return [dict(m) for m in rows.mappings().all()]


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
                ON CONFLICT (as_of, source, grade, price_type) DO UPDATE SET
                    contract = EXCLUDED.contract, price = EXCLUDED.price,
                    currency = EXCLUDED.currency, unit = EXCLUDED.unit, ingested_at = now()
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
    # ORDER BY ingested_at cuối cùng: khi 1 ngày có nhiều bản ghi (source,grade) do đổi kỳ hạn
    # hoặc quét lại/sửa tay → build_sheet giữ bản ghi CUỐI, nên bản nhập/ghi MỚI NHẤT thắng
    # (quét lại cập nhật đúng, và sửa tay override được giá quét sai).
    stmt = text(f"""
        SELECT as_of, source, grade, price, unit
        FROM fact_price
        WHERE {" AND ".join(where)}
        ORDER BY as_of, ingested_at
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


def purchase_recent_for(grade: str, limit: int = 10) -> list[dict[str, Any]]:
    """Vài giá thu mua mủ nước gần nhất của 1 đơn vị (source=vrg) — cho form công khai xem lại."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, price FROM fact_price "
                 "WHERE source = 'vrg' AND price_type = 'purchase' AND grade = :g "
                 "ORDER BY as_of DESC LIMIT :n"),
            {"g": grade, "n": limit},
        ).mappings().all()
        return [{"as_of": str(r["as_of"]), "price": float(r["price"])} for r in rows]


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


_PHYSICAL_SOURCES = ["reuters"]  # chuỗi Reuters physical: lịch sử Excel chuyên viên + nhập tay trên UI
_PHYSICAL_ORDER = ["RSS3", "STR20", "SMR20", "SIR20", "USS",
                   "Thai Latex 60% (Bulk)", "Thai Latex 60% (Drums)", "Thai Latex 60%"]


def _to_usd_tonne(price: float, unit: str, thb: float | None) -> int | None:
    """Quy đổi 1 giá physical → USD/tấn theo đơn vị gốc. baht/kg cần tỷ giá USD/THB."""
    if unit in ("USD/tonne", "USD/T"):
        return round(price)
    if unit == "US$/kg":
        return round(price * 1000)
    if unit == "US cents/kg":
        return round(price * 10)
    if unit == "baht/kg":
        return round(price * 1000 / thb) if thb else None
    return round(price)  # đơn vị lạ → giả định đã USD/tấn


def physical_sheet(date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
    """Lưới giá physical (giao ngay) đã quy đổi USD/tấn: grade × ngày.

    source = reuters, price_type='physical'. baht/kg quy đổi bằng USD/THB (kéo gần nhất);
    thiếu THB → ô để trống. Trả {grades, dates, values[grade][date] = USD/tấn}.
    """
    ensure_schema()
    where = ["price_type = 'physical'", "source IN :srcs"]
    params: dict[str, Any] = {"srcs": _PHYSICAL_SOURCES}
    if date_from:
        where.append("as_of >= CAST(:dfrom AS date)")
        params["dfrom"] = date_from
    if date_to:
        where.append("as_of <= CAST(:dto AS date)")
        params["dto"] = date_to
    stmt = text(
        f"SELECT as_of, grade, price, unit FROM fact_price WHERE {' AND '.join(where)} "
        "ORDER BY as_of DESC, source DESC"
    ).bindparams(bindparam("srcs", expanding=True))
    thb_stmt = text("SELECT as_of, price FROM fact_price WHERE source='fx' AND grade='USD/THB' ORDER BY as_of")
    with session_scope() as db:
        rows = db.execute(stmt, params).mappings().all()
        thb_rows = db.execute(thb_stmt).mappings().all()

    thb_series = [(str(t["as_of"]), float(t["price"])) for t in thb_rows]

    def thb_at(d: str) -> float | None:
        best = None
        for dd, rr in thb_series:  # mới nhất <= d
            if dd <= d:
                best = rr
            else:
                break
        return best

    values: dict[str, dict[str, int]] = {}
    for r in rows:
        d = str(r["as_of"])
        usd = _to_usd_tonne(float(r["price"]), r["unit"], thb_at(d))
        if usd is not None:
            values.setdefault(r["grade"], {}).setdefault(d, usd)

    present = set(values.keys())
    grades = [g for g in _PHYSICAL_ORDER if g in present]
    grades += sorted(present - set(grades))
    dates = sorted({d for m in values.values() for d in m}, reverse=True)
    return {"grades": grades, "dates": dates, "values": values}


def delete_physical_date(as_of: str) -> int:
    """Xoá toàn bộ giá physical (reuters) của 1 ngày. Trả số bản ghi đã xoá."""
    ensure_schema()
    stmt = text(
        "DELETE FROM fact_price WHERE price_type = 'physical' AND source IN :srcs "
        "AND as_of = CAST(:d AS date)"
    ).bindparams(bindparam("srcs", expanding=True))
    with session_scope() as db:
        res = db.execute(stmt, {"srcs": _PHYSICAL_SOURCES, "d": as_of})
        return res.rowcount


def purchase_by_company_on_date(as_of: str, price_type: str = "purchase") -> dict[str, float]:
    """Giá thu mua ĐÚNG NGÀY báo cáo, theo công ty VRG (source=vrg).

    `price_type` = 'purchase' (mủ nước) hoặc 'purchase_cup' (mủ chén). Trả {công ty: giá}.
    CHỈ lấy bản ghi as_of = ngày báo cáo (không carry giá cũ) — công ty không nhập giá đúng
    ngày đó sẽ không xuất hiện. Nếu 1 công ty có nhiều bản ghi cùng ngày (sửa lại) → lấy bản
    nhập sau cùng. Phục vụ mục 'Giá mủ nguyên liệu' của bản tin.
    """
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT DISTINCT ON (grade) grade, price
                FROM fact_price
                WHERE source = 'vrg' AND price_type = :pt
                  AND as_of = CAST(:d AS date)
                ORDER BY grade, ingested_at DESC
            """),
            {"d": as_of, "pt": price_type},
        )
        return {m["grade"]: float(m["price"]) for m in result.mappings().all()}


def member_price_history(company: str, days: int = 30) -> dict[str, Any]:
    """Lịch sử giá mủ nước + mủ chén của ĐÚNG 1 công ty (source=vrg) trong `days` ngày gần nhất.

    Trả {purchase: {date: giá}, purchase_cup: {date: giá}, dates: [mới→cũ]} — cho tài khoản
    đơn vị thành viên tự xem/nhập giá của chính họ.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("""
                SELECT DISTINCT ON (as_of, price_type) as_of, price_type, price
                FROM fact_price
                WHERE source = 'vrg' AND grade = :g
                  AND price_type IN ('purchase', 'purchase_cup')
                  AND as_of >= CURRENT_DATE - CAST(:d AS integer)
                ORDER BY as_of DESC, price_type, ingested_at DESC
            """),
            {"g": company, "d": days},
        ).mappings().all()
    purchase: dict[str, float] = {}
    purchase_cup: dict[str, float] = {}
    dates: list[str] = []
    seen: set[str] = set()
    for r in rows:
        d = str(r["as_of"])
        if d not in seen:
            seen.add(d)
            dates.append(d)
        (purchase if r["price_type"] == "purchase" else purchase_cup)[d] = float(r["price"])
    return {"purchase": purchase, "purchase_cup": purchase_cup, "dates": dates}


def latest_two_for_bulletin(as_of_max: str) -> list[dict[str, Any]]:
    """Cho mỗi (source, grade): 2 bản ghi as_of mới nhất <= as_of_max — phục vụ bản tin.

    curr = mới nhất, prev = liền trước (để tính chênh lệch). Từ 0.2.29 mỗi
    (as_of, source, grade, price_type) chỉ CÒN 1 dòng (đã bỏ `contract` khỏi PK) → "2 bản ghi
    mới nhất" = **2 NGÀY gần nhất**, không còn dính nhiều-hợp-đồng-cùng-ngày.
    (Trước 0.2.29 phải chốt-hợp-đồng-chuẩn, nhưng cách đó lại LOẠI prev khi hợp đồng đổi giữa
    2 ngày → mất ô, vd SGX TSR20 kỳ 09 hôm trước vs kỳ 08 hôm sau. Nay bỏ, so đúng 2 ngày kề.)
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
