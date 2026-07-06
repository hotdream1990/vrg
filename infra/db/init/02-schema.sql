-- Schema time-series cho giá quét (chạy tự động lần đầu tạo container).
-- App cũng tự đảm bảo schema này (idempotent) qua app/core/db.py — DRY về cấu trúc.

-- Mỗi lần bấm "Quét giá" = 1 run (theo dõi số bản ghi, lỗi, thời gian).
CREATE TABLE IF NOT EXISTS meta_crawl_run (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    sources     text,
    status      text NOT NULL DEFAULT 'running',
    rows        integer NOT NULL DEFAULT 0,
    error       text
);

-- Bản ghi giá đã chuẩn hóa từ crawler (1 grade / 1 ngày / 1 kỳ hạn / 1 loại giá).
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
    PRIMARY KEY (as_of, source, grade, contract, price_type)
);

-- Hypertable theo thời gian (partition theo as_of); index truy vấn giá mới nhất.
SELECT create_hypertable('fact_price', 'as_of', if_not_exists => TRUE, migrate_data => TRUE);
CREATE INDEX IF NOT EXISTS ix_fact_price_latest ON fact_price (source, grade, as_of DESC);

-- Giá sàn Tập đoàn (VRG floor) — biểu giá theo "lần" (nhập tay, không hàng ngày).
-- Mỗi lần = 1 ngày áp dụng + bảng giá theo chủng loại (FOB USD/T + Nội địa VNĐ/T).
CREATE TABLE IF NOT EXISTS vrg_floor_price (
    lan          integer NOT NULL,
    as_of        date NOT NULL,
    grade        text NOT NULL,
    fob_usd      double precision,
    domestic_vnd double precision,
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lan, grade)
);
CREATE INDEX IF NOT EXISTS ix_vrg_floor_asof ON vrg_floor_price (as_of DESC, lan DESC);

-- Đơn vị thành viên VRG (cho Giá mủ nguyên liệu) — quản lý động (thêm/sửa/sắp xếp/ẩn).
-- Lazy-seed từ market_meta.VRG_COMPANIES nếu trống (xem member_unit_repo).
CREATE TABLE IF NOT EXISTS member_unit (
    name        text PRIMARY KEY,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    note        text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Tài khoản đăng nhập admin nội bộ (JWT). Seed admin từ env (xem user_repo).
CREATE TABLE IF NOT EXISTS app_user (
    username      text PRIMARY KEY,
    password_hash text NOT NULL,
    full_name     text,
    role          text NOT NULL DEFAULT 'admin',
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Báo giá mủ thị trường — 1 phiếu/ngày (tỷ giá VCB + Mục 1-3 SVR + ghi chú) dạng jsonb.
-- Mục 4 (giá mủ nước theo đơn vị) đồng bộ sang fact_price (source=vrg, purchase).
CREATE TABLE IF NOT EXISTS market_quote (
    as_of       date PRIMARY KEY,
    payload     jsonb NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
