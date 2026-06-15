# Phase 04 — Dashboard MVP (React + TypeScript)

## Context Links
- [plan.md](plan.md) · [apps/web/README.md](../../apps/web/README.md) · [apps/api/README.md](../../apps/api/README.md)
- [system-architecture.md](../../docs/architecture/system-architecture.md) · [code-standards.md](../../docs/project/code-standards.md) · mockup tham khảo: `docs/data/ref/dashboard_caosu.html`

## Overview
- **Priority**: P1
- **Status**: ⚪ pending
- **Mô tả**: Dashboard giám sát đa sàn: hiển thị **giá real-time (T-1)** 4 sàn + vĩ mô, **biểu đồ lịch sử**, và bảng **Premium/Discount** so giá sàn VRG. Gồm 2 phần: API đọc (`apps/api`) + UI React (`apps/web`).

## Key Insights
- Dashboard chỉ **đọc** dữ liệu đã có sẵn từ TimescaleDB (Phase 03 đã tính Premium/Discount) → API mỏng, nhanh; KHÔNG tính toán nặng ở request.
- "Real-time" ở Sprint 1 = **giá T-1 mới nhất** (spec lấy T-1) + auto-refresh/poll; chưa cần websocket/intraday (YAGNI). Ghi rõ để tránh over-engineer.
- Response chuẩn `{ success, data | error }` (theo code-standards) → client xử lý đồng nhất.
- Brand: emerald `#13A05A` + navy `#0E1B2C`, nền sáng, **không emoji** (theo deck). Component < 200 dòng.

## Requirements
**Chức năng (API — `apps/api`)**
- `GET /api/prices/latest` → giá mới nhất mỗi sàn/mặt hàng (kèm kỳ hạn đang chọn).
- `GET /api/prices/history?product=&exchange=&from=&to=` → chuỗi cho biểu đồ.
- `GET /api/macro/latest` → WTI/Brent, USD/VNĐ, USD Index, PMI TQ.
- `GET /api/premium-discount?product=&date=` → bảng so sánh giá sàn VRG.
- Tất cả trả `{ success, data }`; lỗi `{ success, error{code,message} }`.

**Chức năng (UI — `apps/web`)**
- Trang Dashboard: thẻ giá 4 sàn + vĩ mô; biểu đồ lịch sử (chọn mặt hàng/khoảng thời gian); bảng Premium/Discount; auto-refresh.
- Trạng thái loading/error/empty rõ ràng; chọn mặt hàng (mặc định SVR 10).

**Phi chức năng**
- API có pagination/limit cho history; CORS đã cấu hình (`config.py`).
- UI responsive cơ bản; tách feature `dashboard/` (theo cấu trúc đã định).

## Architecture
```
apps/api/app/
  routers/
    prices.py        latest / history
    macro.py         macro latest
    premium.py       premium-discount
  schemas/
    price.py, macro.py, premium.py   (Pydantic response, chuẩn {success,data})
  services/
    price_repo.py    truy vấn TimescaleDB (dùng db_models)
    macro_repo.py, premium_repo.py
apps/web/src/
  features/dashboard/
    DashboardPage.tsx          layout chính (< 200 dòng → tách con)
    PriceCards.tsx             thẻ giá 4 sàn + vĩ mô
    HistoryChart.tsx           biểu đồ lịch sử (recharts/visx)
    PremiumDiscountTable.tsx   bảng so sánh VRG
    useDashboardData.ts        hooks gọi API (react-query)
  lib/api-client.ts            fetch wrapper (xử lý {success,data|error})
  types/                       types đồng bộ shared-ts
  theme.ts                     token màu emerald/navy
```
Luồng: `apps/web` → `apps/api` routers → repos → TimescaleDB (fact_price, fact_macro, fact_premium_discount).

## Related Code Files
**Tạo (API)**
- `apps/api/app/routers/{prices,macro,premium}.py`
- `apps/api/app/schemas/{price,macro,premium}.py`
- `apps/api/app/services/{price_repo,macro_repo,premium_repo}.py`
- `apps/api/tests/test_prices.py` (test endpoint với DB test/fixture)

**Tạo (Web)**
- `apps/web/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/main.tsx`, `src/App.tsx`
- `apps/web/src/features/dashboard/*` (các component + hook ở trên)
- `apps/web/src/lib/api-client.ts`, `apps/web/src/theme.ts`
- `apps/web/src/types/*` (đồng bộ `packages/shared-ts`)

**Sửa / Tái dùng**
- `apps/api/app/main.py` → `include_router(prices, macro, premium)`
- `apps/api/app/core/db.py` (Phase 01) cho session; `packages/shared-py/db_models` cho query
- `packages/shared-ts/` → types dùng chung (DTO giá)

## Implementation Steps
1. **API repos**: `price_repo.py` query latest (DISTINCT ON contract) + history (range, limit); `macro_repo`, `premium_repo`.
2. **API schemas**: Pydantic response bọc `{success, data}`; helper chuẩn hóa lỗi.
3. **API routers**: 4 endpoint; validate query param; gắn vào `main.py`.
4. Test endpoint (httpx + DB test hoặc fixture seed) → đảm bảo shape `{success,data}`.
5. **Web skeleton**: khởi tạo Vite + React-TS + pnpm; `theme.ts` (emerald/navy); `api-client.ts` xử lý envelope.
6. `useDashboardData.ts`: react-query hooks (latest/history/macro/premium) + auto-refresh interval.
7. `PriceCards.tsx`: render thẻ 4 sàn + vĩ mô; trạng thái loading/error.
8. `HistoryChart.tsx`: biểu đồ lịch sử + chọn mặt hàng/khoảng thời gian.
9. `PremiumDiscountTable.tsx`: bảng so sánh; tô màu premium/discount theo dấu.
10. `DashboardPage.tsx`: ghép layout; tách nhỏ nếu > 200 dòng.
11. Lint/format: `ruff` (api), `eslint`/`prettier` (web); `pnpm build` + `tsc` không lỗi.

## Todo List
- [ ] API repos (price/macro/premium) query TimescaleDB
- [ ] API schemas `{success,data}` + routers + gắn `main.py`
- [ ] Test endpoint (shape + dữ liệu)
- [ ] Web skeleton (Vite/React-TS/pnpm) + theme + api-client
- [ ] Hooks react-query + auto-refresh
- [ ] PriceCards / HistoryChart / PremiumDiscountTable / DashboardPage
- [ ] Trạng thái loading/error/empty + chọn mặt hàng (mặc định SVR 10)
- [ ] `uv run ruff check`; `pnpm build` + `tsc` pass

## Success Criteria
- Mở Dashboard → thấy giá mới nhất 4 sàn + vĩ mô, biểu đồ lịch sử vẽ được, bảng Premium/Discount hiển thị đúng dấu/giá trị.
- Đổi mặt hàng/khoảng thời gian → biểu đồ cập nhật.
- API trả đúng `{success,data}`; lỗi trả `{success:false,error}`.
- Build web sạch (không lỗi TS), lint api sạch.

## Risk Assessment
- **Thiếu dữ liệu Premium/Discount** (định nghĩa chưa chốt ở Phase 03) → UI để placeholder/empty-state, không vỡ layout.
- **History 2 năm nặng** → API limit/aggregate (downsample theo ngày), client lazy-load.
- **Over-engineering real-time** → giữ poll T-1; websocket để Sprint sau (YAGNI).
- **Lệch type API↔UI** → dùng `packages/shared-ts` làm nguồn DTO chung.

## Security Considerations
- API chỉ đọc; validate query param; không lộ giá nội bộ ngoài phạm vi cho phép.
- CORS giới hạn origin (`config.cors_origins`).
- Không để secret trong bundle web; gọi API qua biến môi trường build.

## Next Steps
- Demo Dashboard ở **Phase 05**; thu thập phản hồi VRG để chỉnh trước nghiệm thu.
- Chuẩn bị điểm mở rộng cho Sprint 2 (Forecast/Command Center) nhưng KHÔNG implement ở Sprint 1.
