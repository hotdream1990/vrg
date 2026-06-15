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
