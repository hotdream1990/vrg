# apps/web — Frontend (React + TypeScript)

Giao diện người dùng: **Dashboard giám sát**, **Forecast (Bull/Base/Bear)**, **Executive Command Center (chat)**.

## Cấu trúc dự kiến
```
src/
  features/
    dashboard/        giám sát đa sàn + Premium/Discount
    forecast/         ma trận kịch bản + khung thời gian
    command-center/   RAG chatbot + citation
  components/         UI dùng chung
  lib/                api client, utils
  types/              types đồng bộ với packages/shared-ts
```

## Quy ước
- **pnpm + Vite**; lint eslint, format prettier.
- Brand: emerald green (#13A05A) + navy (#0E1B2C), nền sáng, **không emoji** (theo deck).
- Ưu tiên bất biến, component nhỏ < 200 dòng.

## Chạy & build (đã verified)
```bash
pnpm install
pnpm dev      # http://localhost:5390 (cổng VRG)
pnpm build    # tsc + vite build → dist/
```
> `pnpm-workspace.yaml` đã bật `allowBuilds: esbuild` để build chạy được ngay sau clone.

## Dashboard "Quét giá" (đã có)
`App.tsx` có nút **Quét giá ngay** → gọi `GET {VITE_API_URL|:8390}/api/prices/scan` → hiện bảng giá đa sàn + chip trạng thái nguồn.
Chạy đủ bộ: mở API (`apps/api`, cổng 8390) **và** web (`pnpm dev`, cổng 5390) rồi bấm nút. Đổi cổng qua `.env` / `VITE_API_URL`.
