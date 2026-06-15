# pipelines/ — ETL & Lịch chạy

DAG cho **Airflow / Prefect**: thu thập → làm sạch → chuẩn hóa → nạp vào TimescaleDB/pgvector.

## Luồng chính
1. **Ingest**: gọi `services/crawlers` (4 sàn + vĩ mô) định kỳ.
2. **Transform**: làm sạch, chuẩn hóa đơn vị/tiền tệ, tính Premium/Discount.
3. **Load**: ghi time-series (TimescaleDB) + embedding tài liệu (pgvector).
4. **Schedule**: báo cáo tự động **07:30** (dự báo mở cửa) & **17:00** (thực tế vs dự báo).

Xem [docs/architecture/data-flow.md](../docs/architecture/data-flow.md).
