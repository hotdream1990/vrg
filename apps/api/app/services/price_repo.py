"""Repository ghi/đọc giá quét (fact_price) + theo dõi lần quét (meta_crawl_run).

Upsert theo khóa (as_of, source, grade, price_type) — `contract` KHÔNG thuộc khóa
(bỏ từ 0.2.29), nó chỉ đi kèm để biết kỳ hạn nào. Quét lại cùng ngày
không tạo bản ghi trùng. Mọi query tham số hóa (tránh SQL injection).
"""

from __future__ import annotations

import sys
from typing import Any

from sqlalchemy import bindparam, text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import (
    PURCHASE_PRICE_TYPES,
    PURCHASE_SOURCE_HQ,
    PURCHASE_SOURCE_UNIT,
    PURCHASE_SOURCES,
)
from app.core.paths import bulletin_dir
from app.services import audit_repo

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import r1, r2  # noqa: E402 - 1 nguồn làm tròn dùng chung lưới giá/bản tin

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


# Chuẩn hoá số lẻ khi LƯU tỷ giá — theo đúng file gốc của Ban TTKD: USD/JPY 2 số lẻ (163,12
# chứ không phải 163,1222). Cặp không khai ở đây giữ nguyên số lẻ của nguồn (CNY 4 · MYR 3-4 ·
# THB 4). Áp cho MỌI đường ghi: crawler, backfill và sửa tay.
_FX_ROUND = {"USD/JPY": r2}


def _fx_rounded(rec: dict[str, Any]) -> Any:
    """Giá của 1 bản ghi, đã chuẩn hoá số lẻ nếu là cặp tỷ giá có quy ước riêng."""
    fn = _FX_ROUND.get(str(rec.get("grade"))) if rec.get("source") == "fx" else None
    if fn is None or rec.get("price") is None:
        return rec.get("price")
    return fn(float(rec["price"]))


# ── Nhật ký hoạt động ──
def _audit_entity(source: str, price_type: str) -> str:
    """Bản ghi giá thuộc nhóm số liệu nào (khớp quyền + đúng màn hình nhập liệu)."""
    if price_type in PURCHASE_PRICE_TYPES:
        return "raw_material"
    if price_type == "physical":
        return "physical"
    return "auto_data"


def _audit_key(as_of: str, source: str, grade: str, price_type: str) -> str:
    return f"{as_of}|{source}|{grade}|{price_type}"


def _audit_company(source: str, grade: str, price_type: str) -> str | None:
    """Giá mủ nguyên liệu của VRG: `grade` chính là TÊN ĐƠN VỊ → điền vào cột đơn vị để lọc.
    Áp cho CẢ hai lớp: chuyên viên (`vrg`) và đơn vị thành viên tự khai (`vrg_unit`)."""
    return (grade if source in PURCHASE_SOURCES and price_type in PURCHASE_PRICE_TYPES
            else None)


def _snapshot(db, as_of: str, source: str, grade: str,  # noqa: ANN001 - session nội bộ
              price_type: str) -> dict[str, Any] | None:
    """Ảnh chụp bản ghi giá hiện có (None nếu chưa có) — dùng làm giá trị TRƯỚC khi sửa."""
    row = db.execute(text(
        "SELECT price, currency, unit, contract FROM fact_price "
        "WHERE as_of = CAST(:a AS date) AND source = :s AND grade = :g AND price_type = :p"),
        {"a": as_of, "s": source, "g": grade, "p": price_type}).mappings().first()
    return {"price": float(row["price"]), "currency": row["currency"],
            "unit": row["unit"], "contract": row["contract"] or ""} if row else None


def _rows_snapshot(db, sql: str, params: dict[str, Any],  # noqa: ANN001 - session nội bộ
                   expanding: str | None = None) -> list[dict[str, Any]]:
    """Ảnh chụp NHIỀU bản ghi (dùng cho thao tác xoá cả ngày) — để nhật ký giữ lại số đã xoá."""
    stmt = text(sql)
    if expanding:
        stmt = stmt.bindparams(bindparam(expanding, expanding=True))
    rows = db.execute(stmt, params).mappings().all()
    return [{k: (float(v) if k == "price" and v is not None else v) for k, v in r.items()}
            for r in rows]


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
            "price": _fx_rounded(r),
            "currency": r["currency"],
            "unit": r["unit"],
            "source_ts": r.get("source_ts"),
            "run_id": run_id,
        }
        for r in records
    ]
    with session_scope() as db:
        db.execute(_UPSERT, rows)
    # Máy quét ghi hàng loạt → nhật ký chỉ cần 1 dòng TỔNG HỢP (chi tiết đã có ở Bảng tính giá).
    dates = sorted({str(r["as_of"]) for r in rows})
    audit_repo.log(
        "auto_data", "scan", f"run:{run_id}",
        after={"rows": len(rows), "sources": sorted({str(r["source"]) for r in rows}),
               "dates": dates},
        as_of=dates[-1] if dates else None,
        note=f"Quét tự động — ghi {len(rows)} bản ghi",
    )
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
    """Chuỗi giá theo ngày cho 1 (source, grade) — phục vụ biểu đồ + trung bình tuần.

    BỎ các phiên giá 0 (No Trading — sàn nghỉ/không ra settlement): đó không phải mức giá,
    đưa vào chuỗi sẽ thành cú rơi thẳng đứng trên biểu đồ và kéo tụt trung bình tuần.
    """
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT as_of, price
                FROM fact_price
                WHERE source = :source AND grade = :grade
                  AND price <> 0
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


def is_purchase_zero(rec: dict[str, Any]) -> bool:
    """Bản ghi này là ĐƠN GIÁ THU MUA bằng 0 → coi như "không có giá" (xem market_meta).

    Chỉ áp cho mủ nước/mủ chén. Giá sàn 0 là phiên No Trading — dữ liệu thật, phải giữ.
    """
    price = rec.get("price")
    return rec.get("price_type") in PURCHASE_PRICE_TYPES and price is not None and float(price) == 0


def _mirror_to_hq(rec: dict[str, Any]) -> None:
    """Đơn vị vừa ghi giá mủ nguyên liệu → đẩy sang lớp chuyên viên nếu đơn vị đó bật tự động.

    Móc đặt ở ĐÂY vì mọi đường ghi đều đi qua `upsert_record`/`delete_record` (màn của đơn vị,
    link công khai, biểu Thu mua, nhập Excel, đổi ngày báo cáo) — gắn ở từng router là kiểu gì
    cũng sót một đường. Bản ghi lớp chuyên viên (`vrg`) KHÔNG kích hoạt gì → không có vòng lặp.
    """
    if rec.get("source") != PURCHASE_SOURCE_UNIT:
        return
    from app.services import purchase_price_sync  # import trong hàm: tránh vòng import

    purchase_price_sync.mirror_upsert(rec)


def upsert_record(rec: dict[str, Any], note: str | None = None) -> None:
    """Thêm/sửa 1 bản ghi giá thủ công. Khóa: (as_of, source, grade, price_type).

    Ghi Nhật ký hoạt động kèm giá trị trước/sau. `note` để nơi gọi ghi rõ nguồn thao tác
    (vd 'nhập từ text Reuters', 'từ Báo giá mủ — Mục 5').

    **Đơn giá thu mua = 0 → XOÁ bản ghi thay vì lưu số 0** (0 = "không có giá", xem
    `market_meta`). Đặt chặn ở đây vì mọi đường ghi giá đều đi qua hàm này — biểu Thu mua,
    lưới Giá mủ nguyên liệu, Báo giá mủ Mục 5, nhập Excel, link công khai.
    """
    ensure_schema()
    as_of, source = rec["as_of"], rec["source"]
    grade, price_type = rec["grade"], rec["price_type"]
    if is_purchase_zero(rec):
        delete_record(as_of, source, grade, rec.get("contract") or "", price_type)
        return
    with session_scope() as db:
        before = _snapshot(db, as_of, source, grade, price_type)
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
                "price": _fx_rounded(rec), "currency": rec["currency"], "unit": rec["unit"],
            },
        )
        after = _snapshot(db, as_of, source, grade, price_type)
    audit_repo.log(
        _audit_entity(source, price_type), "update" if before else "create",
        _audit_key(as_of, source, grade, price_type),
        before=before, after=after, as_of=as_of,
        company=_audit_company(source, grade, price_type), note=note,
    )
    _mirror_to_hq(rec)


def delete_record(as_of: str, source: str, grade: str, contract: str, price_type: str) -> bool:
    """Xóa 1 bản ghi theo khóa. Trả True nếu có xóa (ghi lại giá trị đã xoá vào nhật ký)."""
    ensure_schema()
    with session_scope() as db:
        before = _snapshot(db, as_of, source, grade, price_type)
        res = db.execute(
            text("""
                DELETE FROM fact_price
                WHERE as_of = CAST(:as_of AS date) AND source = :source AND grade = :grade
                  AND contract = :contract AND price_type = :price_type
            """),
            {"as_of": as_of, "source": source, "grade": grade,
             "contract": contract, "price_type": price_type},
        )
        deleted = res.rowcount > 0
    if deleted:
        audit_repo.log(
            _audit_entity(source, price_type), "delete",
            _audit_key(as_of, source, grade, price_type),
            before=before, as_of=as_of, company=_audit_company(source, grade, price_type),
        )
    # Chỉ khi ĐÚNG LÀ có xoá: đơn vị bấm xoá một ô vốn đã trống thì không được phép kéo theo
    # việc xoá ô của chuyên viên bên lớp `vrg`.
    if deleted and source == PURCHASE_SOURCE_UNIT:
        from app.services import purchase_price_sync  # import trong hàm: tránh vòng import

        purchase_price_sync.mirror_delete(as_of, grade, contract, price_type)
    return deleted


def move_purchase_prices(company: str, as_of: str, to_date: str, source: str) -> dict[str, list[str]]:
    """Chuyển đơn giá thu mua của 1 đơn vị sang ngày khác — đi kèm việc đổi ngày bản ghi báo cáo.

    Đơn giá nhập trong biểu Thu mua nhưng lưu ở kho "Giá mủ nguyên liệu" (khoá theo ngày), nên đổi
    ngày báo cáo mà bỏ lại đơn giá sẽ làm lệch giá bình quân gia quyền của báo cáo kỳ.
    Ngày đích ĐÃ có đơn giá thì GIỮ số của ngày đích (không ghi đè) và để nguyên số ngày cũ —
    trả về danh sách `kept` để nơi gọi báo lại cho người dùng.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("""
                SELECT as_of, price_type, contract, price, currency, unit
                FROM fact_price
                WHERE source = :src AND grade = :g AND price_type IN ('purchase', 'purchase_cup')
                  AND as_of IN (CAST(:d AS date), CAST(:new AS date))
            """),
            {"src": source, "g": company, "d": as_of, "new": to_date},
        ).mappings().all()
    src_rows = {r["price_type"]: r for r in rows if str(r["as_of"]) == as_of}
    taken = {r["price_type"] for r in rows if str(r["as_of"]) == to_date}

    moved, kept = [], []
    for price_type, r in sorted(src_rows.items()):
        if price_type in taken:
            kept.append(price_type)
            continue
        upsert_record({"as_of": to_date, "source": source, "grade": company,
                       "contract": r["contract"] or "", "price_type": price_type,
                       "price": float(r["price"]), "currency": r["currency"], "unit": r["unit"]},
                      note=f"đổi ngày báo cáo {as_of} → {to_date}")
        delete_record(as_of, source, company, r["contract"] or "", price_type)
        moved.append(price_type)
    return {"moved": moved, "kept": kept}


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


def purchase_sheet(date_from: str | None = None, date_to: str | None = None,
                   source: str = PURCHASE_SOURCE_HQ) -> dict[str, Any]:
    """Lưới giá thu mua mủ nước: công ty × ngày. Trả {companies, dates, values}.

    `source` chọn lớp giá: `vrg` (chuyên viên chốt — mặc định) hay `vrg_unit` (đơn vị tự khai).
    dates: mới nhất trước. values[company][date] = giá đồng/độ TSC.
    """
    ensure_schema()
    where = ["source = :src", "price_type = 'purchase'"]
    params: dict[str, Any] = {"src": source}
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


def purchase_recent_for(grade: str, limit: int = 10,
                        source: str = PURCHASE_SOURCE_HQ) -> list[dict[str, Any]]:
    """Vài giá thu mua mủ nước gần nhất của 1 đơn vị — cho form công khai xem lại."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, price FROM fact_price "
                 "WHERE source = :src AND price_type = 'purchase' AND grade = :g "
                 "ORDER BY as_of DESC LIMIT :n"),
            {"g": grade, "n": limit, "src": source},
        ).mappings().all()
        return [{"as_of": str(r["as_of"]), "price": float(r["price"])} for r in rows]


def delete_purchase_date(as_of: str) -> int:
    """Xoá toàn bộ giá thu mua mủ nước của 1 ngày (source=vrg). Trả số bản ghi đã xoá."""
    ensure_schema()
    with session_scope() as db:
        before = _rows_snapshot(db, "SELECT grade, price FROM fact_price WHERE source = 'vrg' "
                                    "AND price_type = 'purchase' AND as_of = CAST(:d AS date)",
                                {"d": as_of})
        res = db.execute(
            text("DELETE FROM fact_price WHERE source = 'vrg' AND price_type = 'purchase' "
                 "AND as_of = CAST(:d AS date)"),
            {"d": as_of},
        )
        removed = res.rowcount
    if removed:
        audit_repo.log("raw_material", "delete", f"{as_of}|vrg|*|purchase",
                       before=before, as_of=as_of,
                       note=f"Xoá cả ngày — {removed} đơn vị")
    return removed


_PHYSICAL_SOURCES = ["reuters"]  # chuỗi Reuters physical: lịch sử Excel chuyên viên + nhập tay trên UI
_PHYSICAL_ORDER = ["RSS3", "STR20", "SMR20", "SIR20", "USS",
                   "Thai Latex 60% (Bulk)", "Thai Latex 60% (Drums)", "Thai Latex 60%"]


def _to_usd_tonne(price: float, unit: str, thb: float | None) -> float | None:
    """Quy đổi 1 giá physical → USD/tấn theo đơn vị gốc. baht/kg cần tỷ giá USD/THB.

    Giữ 1 số lẻ (`r1`): nguồn yết 2 số lẻ ở cents/kg nên số nguyên làm mất đúng 0,5
    (vd MRB SMR20 223,85 → 2238,5 chứ không phải 2238).
    """
    if unit in ("USD/tonne", "USD/T"):
        return r1(price)
    if unit == "US$/kg":
        return r1(price * 1000)
    if unit == "US cents/kg":
        return r1(price * 10)
    if unit == "baht/kg":
        return r1(price * 1000 / thb) if thb else None
    return r1(price)  # đơn vị lạ → giả định đã USD/tấn


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
    select_stmt = (
        "SELECT grade, price, unit FROM fact_price WHERE price_type = 'physical' "
        "AND source IN :srcs AND as_of = CAST(:d AS date)"
    )
    with session_scope() as db:
        before = _rows_snapshot(db, select_stmt, {"srcs": _PHYSICAL_SOURCES, "d": as_of},
                                expanding="srcs")
        res = db.execute(stmt, {"srcs": _PHYSICAL_SOURCES, "d": as_of})
        removed = res.rowcount
    if removed:
        audit_repo.log("physical", "delete", f"{as_of}|reuters|*|physical",
                       before=before, as_of=as_of,
                       note=f"Xoá cả ngày — {removed} chủng loại")
    return removed


def purchase_by_company_on_date(as_of: str, price_type: str = "purchase",
                                source: str = PURCHASE_SOURCE_HQ) -> dict[str, float]:
    """Giá thu mua ĐÚNG NGÀY báo cáo, theo công ty VRG.

    `price_type` = 'purchase' (mủ nước) hoặc 'purchase_cup' (mủ chén). Trả {công ty: giá}.
    CHỈ lấy bản ghi as_of = ngày báo cáo (không carry giá cũ) — công ty không nhập giá đúng
    ngày đó sẽ không xuất hiện. Nếu 1 công ty có nhiều bản ghi cùng ngày (sửa lại) → lấy bản
    nhập sau cùng. Phục vụ mục 'Giá mủ nguyên liệu' của bản tin.

    Bỏ qua giá 0: đơn giá thu mua 0 = "không có giá" (xem `market_meta`). Tầng ghi đã chặn,
    nhưng script import lịch sử ghi thẳng SQL nên vẫn lọc ở đây — lọt một số 0 là bản tin in
    ra khoảng "0-550 đồng/độ" cho cả khu vực.
    """
    ensure_schema()
    with session_scope() as db:
        result = db.execute(
            text("""
                SELECT DISTINCT ON (grade) grade, price
                FROM fact_price
                WHERE source = :src AND price_type = :pt
                  AND as_of = CAST(:d AS date) AND price <> 0
                ORDER BY grade, ingested_at DESC
            """),
            {"d": as_of, "pt": price_type, "src": source},
        )
        return {m["grade"]: float(m["price"]) for m in result.mappings().all()}


def purchase_prices_in_range(date_from: str, date_to: str,
                             source: str = PURCHASE_SOURCE_HQ) -> dict[tuple[str, str], dict[str, float]]:
    """Đơn giá thu mua trong khoảng → {(công ty, ngày): {latex, cup}}.

    Dùng tính GIÁ BÌNH QUÂN GIA QUYỀN theo sản lượng cho báo cáo kỳ (1 query cho cả khoảng).
    Bỏ giá 0 ("không có giá") — tính vào bình quân là kéo tụt giá của cả kỳ.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("""
                SELECT DISTINCT ON (as_of, grade, price_type) as_of, grade, price_type, price
                FROM fact_price
                WHERE source = :src AND price_type IN ('purchase', 'purchase_cup')
                  AND as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date) AND price <> 0
                ORDER BY as_of, grade, price_type, ingested_at DESC
            """),
            {"a": date_from, "b": date_to, "src": source},
        ).mappings().all()
    out: dict[tuple[str, str], dict[str, float]] = {}
    for r in rows:
        key = (r["grade"], str(r["as_of"]))
        slot = out.setdefault(key, {})
        slot["latex" if r["price_type"] == "purchase" else "cup"] = float(r["price"])
    return out


def member_price_history(company: str, days: int = 30,
                         source: str = PURCHASE_SOURCE_UNIT) -> dict[str, Any]:
    """Lịch sử giá mủ nước + mủ chén của ĐÚNG 1 công ty trong `days` ngày gần nhất (lớp đơn vị tự khai).

    Trả {purchase: {date: giá}, purchase_cup: {date: giá}, dates: [mới→cũ]} — cho tài khoản
    đơn vị thành viên tự xem/nhập giá của chính họ.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("""
                SELECT DISTINCT ON (as_of, price_type) as_of, price_type, price
                FROM fact_price
                WHERE source = :src AND grade = :g
                  AND price_type IN ('purchase', 'purchase_cup')
                  AND as_of >= CURRENT_DATE - CAST(:d AS integer)
                ORDER BY as_of DESC, price_type, ingested_at DESC
            """),
            {"g": company, "d": days, "src": source},
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
