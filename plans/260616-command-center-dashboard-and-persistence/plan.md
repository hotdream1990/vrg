---
title: "Command Center Dashboard (theo demo) + Ghi nhận giá quét vào DB"
description: "Dựng lại apps/web giống docs/data/demos/Dashboard_Gia_CaoSu.html (dark theme), tích hợp chức năng quét giá đa sàn (live) làm 1 section, và ghi giá đã quét vào TimescaleDB. Sau đó hoàn thiện các phần Sprint 1 còn thiếu."
status: in-progress
priority: P1
created: 2026-06-16
branch: feature/exchange-crawlers
supersedes: phase-04 (đổi sang dark Command Center theme theo yêu cầu mới)
pulls_in: phase-01 (phần fact_price + meta_crawl_run cho persistence)
---

# Command Center Dashboard + Persistence

> Yêu cầu: web phải GIỐNG demo `docs/data/demos/Dashboard_Gia_CaoSu.html` (giữ nguyên style).
> Tách demo → khung layout + data sample → bổ sung section "Quét giá đa sàn (Live)" → ghi DB thật.
> Làm xong thì tiếp tục các phần implement còn thiếu của Sprint 1.

## Quyết định kiến trúc (KISS/YAGNI/DRY)
- **Routing** (feedback anh Trung): tách 1 page khổng lồ → React Router. `AppLayout` (shell giữ nguyên) + route con. Đã implement thật: `/` Dashboard (mockup) + `/quet-da-san` Quét Đa sàn. Mục sidebar mockup dùng `to:"/"` + `hash` (cuộn trong Dashboard, tách route sau).
- **Style**: bê nguyên CSS demo thành 1 stylesheet `command-center.css` (giữ đúng style, DRY — không re-implement bằng JS).
- **Charts**: Chart.js (demo dùng) qua `react-chartjs-2` + `chart.js`. Vite `dedupe`+`optimizeDeps.include` React để tránh "Invalid hook call".
- **Data sample**: trích từ demo vào `data/sample-data.ts` (typed) cho phần khung tĩnh.
- **Route Quét Đa sàn** (`pages/ScanPage.tsx`): mở trang **tự nạp giá đã lưu từ DB** (`GET /latest`) — không phải click mỗi lần; nút "Quét giá ngay" gọi `POST /scan` rồi refresh. Hiển thị "cập nhật lúc" theo `ingested_at`.
- **Persistence**: SQLAlchemy 2 + psycopg3. Bảng `fact_price` (hypertable theo `as_of`) + `meta_crawl_run`. Upsert ON CONFLICT. Degrade gracefully nếu DB down (scan vẫn trả data).
- **Đọc cho dashboard**: `GET /api/prices/latest` (kèm `ingested_at`), `GET /api/prices/history`.

## File map
**API (`apps/api`)**
- `pyproject.toml` → +sqlalchemy, +psycopg[binary]
- `app/core/config.py` → database_url dev default
- `app/core/db.py` (mới) → engine/session + ensure_schema idempotent + db_healthy
- `app/services/price_repo.py` (mới) → record_run / upsert_prices / latest / history
- `app/schemas/price.py` (mới) → response models
- `app/routers/prices.py` → scan (POST, persist) + latest + history
- `app/routers/health.py` → +/health/db
- `tests/test_prices_persist.py` (mới)

**Infra**
- `infra/db/init/02-schema.sql` (mới) → fact_price + meta_crawl_run + hypertable + index

**Web (`apps/web`)** — component < 200 dòng
- `index.html` → dark theme, title Command Center
- `package.json` → +chart.js +react-chartjs-2
- `src/styles/command-center.css` (mới, từ demo)
- `src/data/sample-data.ts` (mới)
- `src/lib/api-client.ts` (mới) → fetch + types
- `src/features/command-center/CommandCenter.tsx` + TopBar/Sidebar/Footer
- `src/features/command-center/sections/*` (Kpi, PriceConvergence, Alerts, Scenario, Forecast, Heatmap, VrgTable, SupplyDemand, Tsr20, Architecture, Workflow, RagChat, Security, LivePriceScan★)
- `src/features/command-center/charts/*` (Line/Bar wrappers)
- `src/App.tsx` → render CommandCenter

## Checklist
- [ ] API: db.py (engine/session/ensure_schema) + deps
- [ ] API: price_repo (upsert/latest/history) + schemas
- [ ] API: prices router (scan POST persist + latest + history) + /health/db
- [ ] Infra: 02-schema.sql (hypertable)
- [ ] DB container up → verify fact_price hypertable + persist thật
- [ ] API tests pass (uv run pytest)
- [ ] Web: CSS demo + sample-data + api-client
- [ ] Web: layout (TopBar/Sidebar/Footer/CommandCenter)
- [ ] Web: sections tĩnh + 3 charts khớp demo
- [ ] Web: LivePriceScan gọi API + render dark theme
- [ ] Web: pnpm build + tsc sạch; preview verify khớp demo
- [ ] code-reviewer pass; docs update

## Sau khi xong (Sprint 1 còn thiếu)
- Phase 01 còn lại: dimension tables + Alembic + db_models shared-py
- Phase 03: ETL nạp lịch sử + premium/discount
- Phase 05: demo/nghiệm thu checklist
