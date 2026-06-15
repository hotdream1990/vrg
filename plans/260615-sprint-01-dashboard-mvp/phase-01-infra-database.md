# Phase 01 — Hạ tầng + Database (TimescaleDB + pgvector)

## Context Links
- [plan.md](plan.md) · [system-architecture.md](../../docs/architecture/system-architecture.md) · [infra/README.md](../../infra/README.md)
- [.env.example](../../.env.example) · [code-standards.md](../../docs/project/code-standards.md)

## Overview
- **Priority**: P1 (chặn mọi phase sau)
- **Status**: ⚪ pending
- **Mô tả**: Dựng stack dev qua `docker-compose` (Postgres + TimescaleDB + pgvector, api, web, redis), khởi tạo schema time-series cho giá đa sàn + vĩ mô + giá tham chiếu VRG. Đặt nền cho crawler/ETL ghi dữ liệu.

## Key Insights
- 1 Postgres image bật **cả** TimescaleDB **và** pgvector (image `timescale/timescaledb-ha:pg16` có sẵn cả hai, hoặc cài extension thủ công). KISS: 1 DB container, 2 extension.
- Dữ liệu giá là **time-series chuẩn** → dùng `create_hypertable` cho bảng giá; partition theo thời gian.
- pgvector dựng sẵn ở Sprint 1 (cột/extension) nhưng **chưa nạp embedding** (đó là Sprint 2 RAG) — chỉ bật extension + bảng rỗng để tránh migration phá vỡ sau.
- Schema phải tách: **bảng dimension** (sàn, mặt hàng, kỳ hạn) vs **bảng fact giá** (hypertable) → chuẩn hóa, dễ tính Premium/Discount.

## Requirements
**Chức năng**
- `docker-compose` chạy được: `db` (TimescaleDB+pgvector), `redis`, `api`, `web` (dev profile).
- Script init DB tạo extension + schema + hypertable + index.
- Bảng lưu: giá sàn (per sàn/mặt hàng/kỳ hạn/ngày), chỉ số vĩ mô, giá tham chiếu VRG, bảng nguồn/metadata crawl.
- Migration có versioning (Alembic) để Phase sau mở rộng an toàn.

**Phi chức năng**
- Healthcheck cho `db`; biến môi trường từ `.env` (không hardcode mật khẩu).
- Sẵn sàng cấu hình TLS/at-rest encryption cho production (ghi chú, không bật ở dev).

## Architecture
```
infra/docker/docker-compose.yml
  db (timescaledb-ha pg16) ──┐
  redis                      ├─ network: vrg-net
  api (apps/api, uvicorn)    │
  web (apps/web, vite)       ┘
infra/db/
  00-extensions.sql   → CREATE EXTENSION timescaledb, vector;
  01-schema.sql       → dimension + fact tables
  02-hypertables.sql  → create_hypertable + indexes
apps/api/app/core/db.py → engine + session (SQLAlchemy)
```
Schema chính (rút gọn):
- `dim_exchange(id, code{TOCOM,SICOM,SHFE,AFET,LGM}, name, country)`
- `dim_product(id, code{SVR10,RSS3,TSR20,...}, group)`
- `dim_contract(id, exchange_id, product_id, label, expiry_month, expiry_year)` — kỳ hạn động
- `fact_price(time, contract_id, settle, volume, trading_value, currency, source_ts)` → **hypertable** theo `time`
- `fact_macro(time, indicator{WTI,BRENT,USDVND,USDX,PMI_CN}, value, unit)` → hypertable
- `fact_vrg_reference(time, product_id, price, unit, note)` — giá sàn VRG (cho Premium/Discount)
- `meta_crawl_run(id, source, started_at, finished_at, status, rows, error)`

## Related Code Files
**Tạo**
- `infra/docker/docker-compose.yml`
- `infra/docker/.env.docker.example` (biến cho compose, không secret thật)
- `infra/db/00-extensions.sql`, `infra/db/01-schema.sql`, `infra/db/02-hypertables.sql`
- `apps/api/app/core/db.py` (engine/session SQLAlchemy)
- `apps/api/alembic.ini` + `apps/api/migrations/` (Alembic env + version đầu)
- `packages/shared-py/db_models/` (SQLAlchemy models dùng chung api + pipelines)

**Sửa**
- `apps/api/pyproject.toml` → thêm `sqlalchemy`, `psycopg[binary]`, `alembic`, `pgvector`
- `apps/api/app/core/config.py` → thêm `database_url` đã có; bổ sung `redis_url`, `pgvector_dim`
- `infra/README.md` (chỉ cập nhật khi triển khai thật — NGOÀI phạm vi sửa của plan này)

## Implementation Steps
1. Viết `docker-compose.yml`: service `db` image `timescale/timescaledb-ha:pg16`, volume bền, healthcheck `pg_isready`; mount `infra/db/*.sql` vào `/docker-entrypoint-initdb.d/`.
2. Thêm `redis`, `api`, `web` services (build context tương ứng) với `depends_on: db (healthy)`.
3. Viết `00-extensions.sql` bật `timescaledb`, `vector`.
4. Viết `01-schema.sql` (dimension + fact + meta) theo Architecture; khóa ngoại, unique constraint `(exchange,product,expiry)`.
5. Viết `02-hypertables.sql`: `create_hypertable('fact_price','time')`, `fact_macro`; index `(contract_id, time DESC)`.
6. Khởi tạo Alembic trong `apps/api`; tạo models ở `packages/shared-py/db_models/` (Base, dim, fact); sinh migration version 0001 khớp SQL init.
7. Thêm `apps/api/app/core/db.py`: tạo engine từ `settings.database_url`, session factory; healthcheck DB cho router `/health/db`.
8. Cập nhật `config.py` thêm `redis_url`; đảm bảo đọc từ `.env`.
9. Tài liệu cách chạy: `docker compose -f infra/docker/docker-compose.yml up -d db` (ghi trong plan, không sửa repo README).

## Todo List
- [ ] `docker-compose.yml` (db+redis+api+web) có healthcheck
- [ ] SQL init: extensions + schema + hypertables + indexes
- [ ] SQLAlchemy models trong `packages/shared-py/db_models/`
- [ ] Alembic init + migration 0001
- [ ] `apps/api/app/core/db.py` + `/health/db`
- [ ] Cập nhật `pyproject.toml` + `config.py`
- [ ] Compile check: `uv run ruff check`, `uv run python -c "import app.main"`
- [ ] Verify: container `db` healthy, `\dx` thấy timescaledb+vector, hypertable tồn tại

## Success Criteria
- `docker compose up db redis` → `db` healthy; `psql` kết nối được.
- `SELECT * FROM timescaledb_information.hypertables;` trả về `fact_price`, `fact_macro`.
- `/health/db` trả `success:true`; Alembic `upgrade head` chạy sạch.
- Không có secret hardcode; mật khẩu DB đọc từ env.

## Risk Assessment
- **Image TimescaleDB-HA nặng/khó pull** → fallback: Postgres + cài extension qua apt trong Dockerfile riêng. Mitigation: pin tag, cache layer.
- **pgvector dim chưa chốt (1536)** → để cấu hình `PGVECTOR_DIM`; bảng vector tạo rỗng, không khóa cứng dim ở Sprint 1.
- **Migration drift** giữa SQL init và Alembic → chọn 1 nguồn sự thật: Alembic sinh schema, SQL chỉ lo extension (giảm trùng lặp - DRY).

## Security Considerations
- Mật khẩu DB qua `.env`/secret compose, không in log.
- Ghi chú production: TLS 1.3 cho kết nối DB, AES-256 at-rest (volume mã hóa), Cloud VN.
- Tham số hóa mọi query (SQLAlchemy) — tránh injection.

## Next Steps
- Bàn giao schema cho **Phase 02** (crawler ghi vào `meta_crawl_run` + bảng staging) và **Phase 03** (ETL load fact).
- Cung cấp `db_models` cho pipelines tái sử dụng (DRY).
