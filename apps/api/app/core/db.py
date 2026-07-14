"""Kết nối DB (SQLAlchemy 2 + psycopg3) cho persistence giá quét.

Engine khởi tạo lười (lazy) để API vẫn chạy khi DB tạm thời down — endpoint quét
sẽ degrade gracefully thay vì sập. `ensure_schema()` tạo bảng idempotent (phòng khi
init SQL chưa chạy do volume cũ).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None
_schema_ready = False

# DDL idempotent — khớp infra/db/init/02-schema.sql. Nguồn ghi giá đã chuẩn hóa.
_DDL_TABLES = """
CREATE TABLE IF NOT EXISTS meta_crawl_run (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    sources     text,
    status      text NOT NULL DEFAULT 'running',
    rows        integer NOT NULL DEFAULT 0,
    error       text
);

CREATE TABLE IF NOT EXISTS fact_price (
    as_of       date NOT NULL,
    source      text NOT NULL,
    grade       text NOT NULL,
    contract    text NOT NULL DEFAULT '',
    price_type  text NOT NULL,
    price       double precision NOT NULL,
    currency    text NOT NULL,
    unit        text NOT NULL,
    source_ts   timestamptz,
    run_id      bigint,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (as_of, source, grade, price_type)  -- contract KHÔNG trong PK: mỗi (ngày,sàn,grade) 1 dòng, upsert ghi đè
);

CREATE INDEX IF NOT EXISTS ix_fact_price_latest
    ON fact_price (source, grade, as_of DESC);

CREATE TABLE IF NOT EXISTS vrg_floor_price (
    lan          integer NOT NULL,
    as_of        date NOT NULL,
    grade        text NOT NULL,
    fob_usd      double precision,
    domestic_vnd double precision,
    title        text,
    dispatch_no      text,                 -- số công văn (theo lần)
    dispatch_summary text,                 -- trích yếu nội dung công văn (theo lần)
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lan, grade)
);

CREATE INDEX IF NOT EXISTS ix_vrg_floor_asof ON vrg_floor_price (as_of DESC, lan DESC);

CREATE TABLE IF NOT EXISTS fact_inventory (
    as_of       date PRIMARY KEY,
    ton_kho     double precision,
    ton_kho_hd  double precision,
    note        text,
    source      text NOT NULL DEFAULT 'hanh_weekly',
    ingested_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS member_unit (
    name        text PRIMARY KEY,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Khu vực (nhóm các đơn vị thành viên) — dùng gom giá mủ nguyên liệu theo khu vực trong bản tin.
CREATE TABLE IF NOT EXISTS member_region (
    name        text PRIMARY KEY,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_user (
    username      text PRIMARY KEY,
    password_hash text NOT NULL,
    full_name     text,
    role          text NOT NULL DEFAULT 'admin',
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_config (
    key         text PRIMARY KEY,
    value       text,
    is_secret   boolean NOT NULL DEFAULT false,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text
);

CREATE TABLE IF NOT EXISTS schedule_job (
    name        text PRIMARY KEY,
    hour        integer NOT NULL,
    minute      integer NOT NULL,
    enabled     boolean NOT NULL DEFAULT true,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bulletin_draft (
    report_date  date PRIMARY KEY,
    payload      jsonb NOT NULL,
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS market_quote (
    as_of       date PRIMARY KEY,
    payload     jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS weekly_report (
    week_key    text PRIMARY KEY,          -- ngày Thứ 2 ISO của tuần, 'YYYY-MM-DD'
    payload     jsonb NOT NULL,            -- narrative (các phần viết) + override bảng III.3
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Migration idempotent cho DB đã tồn tại (CREATE IF NOT EXISTS không thêm cột mới).
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS dispatch_no text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS dispatch_summary text;
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS region text;
"""

# Hypertable tách riêng: cần extension timescaledb; nếu thiếu, bảng vẫn dùng được.
_DDL_HYPERTABLE = (
    "SELECT create_hypertable('fact_price', 'as_of', "
    "if_not_exists => TRUE, migrate_data => TRUE);"
)


def _normalized_url() -> str:
    """Ép driver psycopg3 cho SQLAlchemy."""
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine() -> Engine:
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(
            _normalized_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            future=True,
        )
        _Session = sessionmaker(bind=_engine, future=True)
    return _engine


def ensure_schema() -> None:
    """Tạo bảng + hypertable nếu chưa có (idempotent). Gọi trước khi ghi."""
    global _schema_ready
    if _schema_ready:
        return
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(_DDL_TABLES))
        try:
            conn.execute(text(_DDL_HYPERTABLE))
        except Exception:  # noqa: BLE001 - thiếu timescaledb thì bỏ qua, bảng thường vẫn chạy
            pass
    _schema_ready = True


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session có commit/rollback tự động."""
    get_engine()
    assert _Session is not None
    db = _Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def db_healthy() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
