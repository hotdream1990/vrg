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
    permissions   jsonb NOT NULL DEFAULT '[]'::jsonb,  -- quyền theo mục (editor); admin=tất cả
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

-- Nhu cầu thị trường: free text theo (đơn vị thành viên, ngày). Đơn vị tự nhập của mình;
-- chuyên viên có quyền market_demand xem/sửa mọi đơn vị. `company` khớp tên đơn vị (member_unit).
CREATE TABLE IF NOT EXISTS market_demand (
    as_of       date NOT NULL,
    company     text NOT NULL,
    content     text NOT NULL DEFAULT '',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text,
    PRIMARY KEY (as_of, company)
);

-- Báo cáo tiêu thụ – tồn kho của đơn vị thành viên (theo NGÀY) — 2 loại: thu mua ('purchase')
-- & tiêu thụ–tồn kho ('consumption'). Mỗi (ngày, đơn vị, loại) = 1 bản ghi, số liệu jsonb {field: number}.
-- Đơn vị tự nhập của mình; chuyên viên có quyền `unit_daily` xem/sửa mọi đơn vị (realtime).
CREATE TABLE IF NOT EXISTS unit_daily_report (
    as_of       date NOT NULL,         -- ngày báo cáo 'YYYY-MM-DD'
    company     text NOT NULL,         -- tên đơn vị (khớp member_unit)
    kind        text NOT NULL,         -- 'purchase' | 'consumption'
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text,
    PRIMARY KEY (as_of, company, kind)
);
CREATE INDEX IF NOT EXISTS ix_unit_daily_date ON unit_daily_report (kind, as_of DESC);

-- Tồn kho ĐÃ KÝ HỢP ĐỒNG chưa giao — KHÔNG nhập lại mỗi ngày (hợp đồng có file scan, nhập lại
-- hằng ngày sẽ phình dữ liệu). Mỗi hợp đồng là 1 BẢN GHI có vòng đời: tính vào tồn kho từ
-- `start_date` đến HẾT ngày TRƯỚC `delivered_date`; chưa giao (`delivered_date` NULL) thì còn tồn.
CREATE TABLE IF NOT EXISTS unit_stock_contract (
    id          bigserial PRIMARY KEY,
    company     text NOT NULL,          -- đơn vị (khớp member_unit)
    code        text,                   -- số Hợp đồng / Phụ lục
    grade       text NOT NULL,          -- chủng loại
    qty         double precision,       -- số lượng (tấn)
    price       double precision,       -- đơn giá (theo `ccy`)
    ccy         text NOT NULL DEFAULT 'VND',
    fx          double precision,       -- tỷ giá USD→VND (khi ccy = USD)
    start_date  date NOT NULL,          -- ngày bắt đầu tồn kho
    delivery_date  date,                -- lịch giao (dự kiến)
    delivered_date date,                -- ngày giao THỰC TẾ (trống = chưa giao, vẫn đang tồn)
    file        text,                   -- HĐ đã ký scan (tên file lưu server)
    filename    text,                   -- tên gốc để hiển thị
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text
);
CREATE INDEX IF NOT EXISTS ix_stock_contract_company ON unit_stock_contract (company, start_date);

-- Chỉ tiêu KẾ HOẠCH thu mua theo năm cho từng đơn vị (dùng tính % thực hiện kế hoạch).
CREATE TABLE IF NOT EXISTS unit_purchase_plan (
    year        integer NOT NULL,
    company     text NOT NULL,
    plan_tonnes double precision,       -- kế hoạch thu mua năm (tấn)
    signed_lt_tonnes double precision,  -- tổng SL đã ký HĐ dài hạn năm (tấn)
    carry_lt_tonnes  double precision,  -- SL tiêu thụ HĐ dài hạn năm trước chuyển sang (tấn)
    carry_spot_tonnes double precision, -- SL tiêu thụ HĐ chuyến năm trước chuyển sang (tấn)
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text,
    PRIMARY KEY (year, company)
);

-- Nhật ký hoạt động (audit log): MỖI lần ghi/xoá số liệu = 1 DÒNG MỚI, không ghi đè.
-- Truy vết được ai · lúc nào · sửa ô nào · từ giá trị nào sang giá trị nào (data_before/data_after).
-- Bảng độc lập với bảng nghiệp vụ — xoá bản ghi nghiệp vụ vẫn còn nguyên vết ở đây.
CREATE TABLE IF NOT EXISTS audit_log (
    id          bigserial PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    actor       text NOT NULL,              -- username; 'system' = job tự chạy; 'public:<đơn vị>' = link công khai
    actor_role  text,                       -- admin | editor | member (rỗng nếu không phải tài khoản)
    on_behalf   text,                       -- admin đang "đăng nhập hộ" (nếu có) — vẫn truy ra người thật
    entity      text NOT NULL,              -- nhóm số liệu: raw_material | physical | floor | inventory | ...
    action      text NOT NULL,              -- create | update | delete | scan | import
    entity_key  text NOT NULL DEFAULT '',   -- khoá bản ghi, vd '2026-07-23|sgx|TSR20|settle'
    as_of       date,                       -- ngày số liệu (để lọc "mọi thay đổi của ngày X")
    company     text,                       -- đơn vị thành viên (nếu có) — để lọc theo đơn vị
    data_before jsonb,                      -- giá trị TRƯỚC khi sửa (NULL khi thêm mới)
    data_after  jsonb,                      -- giá trị SAU khi sửa (NULL khi xoá)
    ip          text,
    note        text                        -- diễn giải ngắn (vd 'nhập từ file', 'xoá cả ngày')
);
CREATE INDEX IF NOT EXISTS ix_audit_at ON audit_log (at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log (entity, at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_log (actor, at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_key ON audit_log (entity, entity_key, at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_asof ON audit_log (as_of);

-- Migration idempotent cho DB đã tồn tại (CREATE IF NOT EXISTS không thêm cột mới).
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS dispatch_no text;
ALTER TABLE vrg_floor_price ADD COLUMN IF NOT EXISTS dispatch_summary text;
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS region text;
-- Quốc gia + loại tiền của đơn vị (đơn vị nước ngoài Lào/Campuchia cần tỷ giá khi thu mua).
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS country text NOT NULL DEFAULT 'VN';
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS currency text NOT NULL DEFAULT 'VND';
-- Đơn vị có nhà máy chế biến không (đơn vị KHÔNG có nhà máy mới nhập tồn kho nguyên liệu).
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS has_factory boolean NOT NULL DEFAULT true;
-- Đơn vị có được giao KẾ HOẠCH thu mua năm không — chỉ đơn vị bật cờ này mới hiện ở "Kế hoạch năm".
ALTER TABLE member_unit ADD COLUMN IF NOT EXISTS has_purchase_plan boolean NOT NULL DEFAULT true;
-- Số liệu năm nhập 1 lần (không theo ngày): tổng SL đã ký HĐ dài hạn của năm.
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS signed_lt_tonnes double precision;
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS carry_lt_tonnes double precision;
ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS carry_spot_tonnes double precision;
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS permissions jsonb NOT NULL DEFAULT '[]'::jsonb;
-- Các đơn vị gắn với tài khoản (chỉ dùng cho role=member) — 1 tài khoản có thể gán NHIỀU đơn vị.
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS member_units jsonb NOT NULL DEFAULT '[]'::jsonb;
-- Migrate cột đơn cũ member_unit → mảng member_units rồi bỏ cột cũ (idempotent).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'app_user' AND column_name = 'member_unit') THEN
    UPDATE app_user SET member_units = jsonb_build_array(member_unit)
      WHERE member_unit IS NOT NULL AND member_unit <> ''
        AND (member_units IS NULL OR member_units = '[]'::jsonb);
    ALTER TABLE app_user DROP COLUMN member_unit;
  END IF;
END $$;
-- Đổi tên quyền cũ 'corridor_info' → 'market_demand' (Thông tin hành lang → Nhu cầu thị trường).
UPDATE app_user SET permissions = REPLACE(permissions::text, 'corridor_info', 'market_demand')::jsonb
    WHERE permissions::text LIKE '%corridor_info%';
-- Báo cáo tiêu thụ–tồn kho chuyển từ TUẦN → NGÀY: gỡ bảng tuần cũ (chưa có dữ liệu thật) + đổi tên quyền.
DROP TABLE IF EXISTS unit_weekly_report;
UPDATE app_user SET permissions = REPLACE(permissions::text, 'unit_weekly', 'unit_daily')::jsonb
    WHERE permissions::text LIKE '%unit_weekly%';
-- Đổi tên chủng loại giá sàn cho khớp báo cáo (idempotent).
UPDATE vrg_floor_price SET grade = 'SVR 10 / CSR 10' WHERE grade = 'SVR 10';
UPDATE vrg_floor_price SET grade = 'SVR 20 / CSR 20' WHERE grade = 'SVR 20';
UPDATE vrg_floor_price SET grade = 'Skim Block' WHERE grade = 'SkimBlock';
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
