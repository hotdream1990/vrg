---
title: "Sprint 1 — Nền tảng dữ liệu & Dashboard MVP (VRG)"
description: "Dựng hạ tầng DB, crawler 4 sàn + vĩ mô, ETL nạp ~2 năm lịch sử, Dashboard MVP React real-time + Premium/Discount."
status: pending
priority: P1
effort: ~4 tuần (1 sprint)
branch: main
tags: [vrg, sprint-1, infra, crawler, etl, timescaledb, dashboard, poc]
created: 2026-06-15
---

# Sprint 1 — Nền tảng dữ liệu & Dashboard MVP

> Đề án A (PoC) — Bizino AI + Thái Hưng Infotech. Bàn giao: **Dashboard 4 sàn + dữ liệu lịch sử ~2 năm + kết nối BCTM nội bộ**.
> Nguồn sự thật: [development-roadmap.md](../../docs/project/development-roadmap.md) · [system-architecture.md](../../docs/architecture/system-architecture.md) · [data-flow.md](../../docs/architecture/data-flow.md).

## Mục tiêu Sprint
1. Hạ tầng Cloud VN + DB (TimescaleDB + pgvector) chạy được qua docker-compose; schema time-series sẵn sàng.
2. Crawler 4 sàn (TOCOM/SICOM-SGX/SHFE/AFET) + vĩ mô (WTI/Brent, USD/VNĐ, USD Index, PMI TQ) — bám spec [lay-gia-cac-san.md](../../knowledge/data-sources/lay-gia-cac-san.md), **kỳ hạn tham số hóa (không hardcode số tháng)**.
3. ETL pipeline (Airflow/Prefect) làm sạch → chuẩn hóa → nạp ~2 năm lịch sử vào TimescaleDB; kết nối BCTM nội bộ.
4. Dashboard MVP (React+TS) — giá real-time, lịch sử, tính **Premium/Discount** so giá sàn VRG.
5. Demo & nghiệm thu Sprint 1 với VRG.

## Danh sách Phase
| # | Phase | Trạng thái | Ước lượng | File |
|---|---|---|---|---|
| 01 | Hạ tầng + DB (TimescaleDB + pgvector, docker-compose, schema) | ⚪ pending | ~4 ngày | [phase-01](phase-01-infra-database.md) |
| 02 | Crawler 4 sàn + vĩ mô (bám spec, kỳ hạn tham số hóa) | ⚪ pending | ~7 ngày | [phase-02](phase-02-crawlers-exchanges-macro.md) |
| 03 | ETL pipeline + nạp ~2 năm lịch sử + kết nối BCTM | ⚪ pending | ~5 ngày | [phase-03](phase-03-etl-historical-load.md) |
| 04 | Dashboard MVP React (real-time, lịch sử, Premium/Discount) | ⚪ pending | ~6 ngày | [phase-04](phase-04-dashboard-mvp-react.md) |
| 05 | Demo + nghiệm thu Sprint 1 | ⚪ pending | ~2 ngày | [phase-05](phase-05-demo-acceptance.md) |

## Dependencies (thứ tự thực thi)
```
Phase 01 ──► Phase 02 ──► Phase 03 ──► Phase 04 ──► Phase 05
   DB         crawler        ETL          web          demo
            (cần schema)   (cần raw)   (cần API+data) (cần all)
```
- **01 → 02**: schema + DB phải sẵn để crawler ghi raw/staging.
- **02 → 03**: ETL transform/load dựa trên dữ liệu crawler đã chuẩn cấu trúc.
- **03 → 04**: Dashboard cần API + dữ liệu lịch sử + cột Premium/Discount đã tính.
- **05**: phụ thuộc toàn bộ; cần checklist nghiệm thu của VRG.

## Ràng buộc nền tảng (áp dụng mọi phase)
- Stack đã chốt: **FastAPI (uv, py3.12) · React+TS (Vite, pnpm) · TimescaleDB+pgvector · Airflow/Prefect**.
- File code **< 200 dòng**; kebab-case; YAGNI/KISS/DRY. Không hardcode secret → `.env` (xem `.env.example`).
- Data residency 100% VN; AES-256/TLS 1.3; tuân thủ Nghị định 13/2023/NĐ-CP.
- Phạm vi giá PoC: **SVR 10** + tham chiếu RSS3/TSR20/Natural Rubber/physical theo [san-pham-cao-su.md](../../knowledge/domain/san-pham-cao-su.md).

## Tiền điều kiện (ngoài code — cần VRG)
- ✅ NDA ký xong **trước** khi nhận data thật (BCTM, giá tham chiếu, physical).
- ✅ Xác nhận đầu mối từng nhóm dữ liệu (Triều/Phụng/Tâm/Hạnh) — xem [data-checklist.md](../../docs/project/data-checklist.md).
- ✅ Chốt tổng thời lượng Sprint (deck ghi "3 Sprint × 4 tuần" vs bảng "Tuần 1–6").
- ✅ Cấp tài khoản Cloud VN (VNG/Viettel/VNPT) + quyền truy cập nguồn BCTM nội bộ.

## Rủi ro xuyên suốt (chi tiết trong từng phase)
- Trang sàn đổi layout/đăng nhập/anti-bot → crawler gãy (mitigation: parser tách rời + selector/endpoint cấu hình hóa + alert).
- Dữ liệu lịch sử ~2 năm thiếu/lệch chuẩn → cần nguồn dự phòng + reconciliation.
- Phụ thuộc bàn giao data nội bộ trễ → khóa tiến độ Phase 03/04.

## Câu hỏi mở (xác nhận với VRG trước/đầu Sprint)
1. "Giá sàn VRG" để tính Premium/Discount lấy từ đâu (file nào, tần suất, đơn vị)?
2. AFET (Thái) hiện trạng nguồn — sàn đã sáp nhập TFEX; xác nhận endpoint/nguồn thay thế.
3. ~2 năm là mốc Dashboard MVP; data-checklist yêu cầu ≥3 năm cho train model (Sprint 2) — chốt phạm vi tải lịch sử ở Sprint 1.
4. Real-time mức nào đủ (intraday vs cuối phiên T-1)? Spec hiện lấy giá **T-1** (ngày trước 1 ngày).
