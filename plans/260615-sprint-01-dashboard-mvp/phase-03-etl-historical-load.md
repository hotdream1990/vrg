# Phase 03 — ETL Pipeline + Nạp lịch sử ~2 năm + Kết nối BCTM

## Context Links
- [plan.md](plan.md) · [data-flow.md](../../docs/architecture/data-flow.md) · [pipelines/README.md](../../pipelines/README.md)
- [data-checklist.md](../../docs/project/data-checklist.md) · spec crawler: [phase-02](phase-02-crawlers-exchanges-macro.md) · schema: [phase-01](phase-01-infra-database.md)

## Overview
- **Priority**: P1
- **Status**: ⚪ pending
- **Mô tả**: Pipeline ETL (Airflow/Prefect) điều phối crawler → làm sạch → chuẩn hóa đơn vị/tiền tệ → **tính Premium/Discount** → load TimescaleDB. Backfill ~2 năm lịch sử. Kết nối & nạp BCTM nội bộ (sau NDA).

## Key Insights
- **Premium/Discount tính ở ETL** (1 lần, lưu sẵn) thay vì tính lại ở mỗi request → nhanh cho Dashboard (DRY). Công thức: `premium = giá_sàn_tham_chiếu − giá_sàn_VRG` (cùng mặt hàng/đơn vị/ngày) — **chốt định nghĩa với VRG** (xem câu hỏi mở).
- Backfill khác incremental: backfill chạy theo dải ngày (loop `as_of_date`), incremental chạy hằng ngày 1 ngày. Dùng chung transform (DRY).
- BCTM (Excel tồn kho/sản lượng theo loại mủ) là **đầu vào dự báo (Sprint 2)** nhưng Sprint 1 chỉ cần **kết nối + nạp thô** vào bảng riêng để chứng minh đường ống.
- Lịch sử sàn ~2 năm: nhiều site chỉ cho T-1/giới hạn cửa sổ → cần nguồn lịch sử (file Excel chuyên viên Tâm / nguồn trả phí) — đánh dấu phụ thuộc.

## Requirements
**Chức năng**
- DAG `ingest_daily`: gọi crawler (4 sàn + vĩ mô) cho T-1 → staging → transform → load fact.
- DAG `backfill_history`: tham số `start_date`/`end_date` → loop nạp ~2 năm.
- Bước transform: chuẩn hóa đơn vị/tiền tệ, dedup, validate, tính Premium/Discount.
- Loader: upsert vào `fact_price`, `fact_macro`, `fact_vrg_reference`, `fact_premium_discount`.
- Connector BCTM: đọc Excel mẫu (templates) → bảng `stg_bctm_*` → load `fact_inventory_output` (thô).
- Reconciliation report: số dòng kỳ vọng vs thực, gap ngày, % null.

**Phi chức năng**
- Idempotent (chạy lại không nhân đôi). Logging có cấu trúc; alert khi DAG fail.
- Backfill chịu tải: batch + checkpoint để resume.

## Architecture
```
pipelines/
  dags/
    ingest_daily.py        T-1: crawl → transform → load
    backfill_history.py    loop dải ngày (≈2 năm)
    ingest_bctm.py         đọc Excel BCTM → load thô
  tasks/
    extract.py             gọi services/crawlers (registry)
    transform.py           clean + normalize unit/currency + dedup + validate
    premium_discount.py    join giá sàn ↔ giá VRG → ghi fact_premium_discount
    load.py                upsert TimescaleDB (SQLAlchemy, batch)
    reconcile.py           kiểm đếm + report gap/null
  common/
    units.py               quy đổi đơn vị/tiền tệ (tái dùng fx_rates crawler)
    config.py              schedule, batch size, source list
```
Luồng: `extract → transform → premium_discount → load → reconcile`.
Bảng mới (bổ sung Phase 01): `fact_premium_discount(time, product_id, ref_exchange_id, vrg_price, ref_price, premium, unit)`, `fact_inventory_output(time, product_code, inventory, output, source_file)`, `stg_*` staging.

## Related Code Files
**Tạo**
- `pipelines/dags/{ingest_daily,backfill_history,ingest_bctm}.py`
- `pipelines/tasks/{extract,transform,premium_discount,load,reconcile}.py`
- `pipelines/common/{units,config}.py`
- `pipelines/pyproject.toml` (Prefect **hoặc** Airflow — chốt 1; + pandas, sqlalchemy, openpyxl)
- `pipelines/tests/` (test transform/premium_discount với dữ liệu mẫu)
- `infra/db/03-etl-tables.sql` **hoặc** Alembic migration 0002 (bảng premium_discount, inventory, staging)

**Sửa / Tái dùng**
- `packages/shared-py/db_models/` → thêm models bảng mới
- `services/crawlers/run_crawl.py` (Phase 02) — gọi qua registry, KHÔNG copy logic (DRY)
- `data/templates/` → đặt mẫu cấu trúc BCTM (không commit data thật)

## Implementation Steps
1. Chốt orchestrator (**Prefect** ưu tiên cho PoC — nhẹ; hoặc Airflow nếu VRG yêu cầu) và khai báo `pipelines/common/config.py`.
2. `tasks/extract.py`: gọi crawler registry theo `as_of_date`, trả staging records.
3. `tasks/transform.py`: dedup, chuẩn hóa đơn vị/tiền tệ (dùng `common/units.py`), validate schema, gắn `as_of_date`.
4. `tasks/premium_discount.py`: join giá sàn ↔ `fact_vrg_reference` theo mặt hàng/ngày → tính `premium` → records.
5. `tasks/load.py`: upsert batch vào fact tables (on-conflict theo key thời gian + dimension).
6. `dags/ingest_daily.py`: DAG schedule (sau giờ chốt phiên) chạy chuỗi cho T-1.
7. `dags/backfill_history.py`: param `start/end`; loop ngày có checkpoint; gọi cùng transform/load.
8. `dags/ingest_bctm.py`: đọc Excel mẫu BCTM (templates) → `stg_bctm` → load `fact_inventory_output` thô.
9. `tasks/reconcile.py`: đếm dòng/gap/null → report (lưu artifact, log) để nghiệm thu lịch sử.
10. Migration 0002 (bảng mới); cập nhật `db_models`.
11. Test transform & premium_discount với fixture; compile/lint.
12. Chạy backfill thử dải ngắn (vd 1 tháng) trước khi chạy full ~2 năm.

## Todo List
- [ ] Chốt orchestrator (Prefect/Airflow) + `common/config.py`
- [ ] Tasks: extract / transform / premium_discount / load / reconcile
- [ ] DAG `ingest_daily` (incremental T-1)
- [ ] DAG `backfill_history` (loop ~2 năm, checkpoint/resume)
- [ ] DAG `ingest_bctm` (Excel → bảng thô)
- [ ] Migration 0002 (premium_discount, inventory, staging) + models
- [ ] Reconciliation report (gap/null/đếm dòng)
- [ ] Test transform/premium_discount; compile/lint pass
- [ ] Backfill thử 1 tháng → rồi full

## Success Criteria
- `ingest_daily` chạy 1 lượt: fact_price/macro/premium_discount có dữ liệu T-1, không trùng.
- `backfill_history` nạp ~2 năm: reconcile cho thấy độ phủ ngày hợp lý, gap được liệt kê.
- `fact_premium_discount` có giá trị đúng định nghĩa đã chốt (kiểm 1 ngày thủ công).
- `ingest_bctm` nạp được file mẫu BCTM vào bảng thô.

## Risk Assessment
- **Thiếu nguồn lịch sử ~2 năm** (site chỉ T-1) → phụ thuộc file Excel chuyên viên / nguồn trả phí. Mitigation: xác định nguồn lịch sử **trước** khi chạy backfill; ghi rõ phần thiếu.
- **Định nghĩa Premium/Discount chưa chốt** → khóa logic; làm cấu hình hóa công thức, chờ VRG xác nhận (câu hỏi mở #1).
- **BCTM phụ thuộc NDA + bàn giao** → tách `ingest_bctm` để không chặn luồng giá sàn.
- **Backfill nặng/timeout** → batch + checkpoint; chạy ngoài giờ.

## Security Considerations
- BCTM = dữ liệu nội bộ nhạy cảm → **không log giá nội bộ**, lưu trong DB Cloud VN, quyền truy cập hạn chế.
- File mẫu trong `data/templates/` chỉ là cấu trúc; data thật `data/raw/` (gitignored).
- Tham số hóa query; transform validate đầu vào ngoài.

## Next Steps
- Cung cấp fact tables + Premium/Discount cho **Phase 04** (Dashboard).
- Bàn giao reconciliation report cho **Phase 05** (nghiệm thu độ phủ lịch sử).
