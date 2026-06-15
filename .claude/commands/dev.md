---
description: Khởi động dev VRG (API :8390 + Web :5390) để bấm "Quét giá ngay"
---

Khởi động môi trường dev của project VRG để tôi mở web và bấm "Quét giá ngay":

1. Chạy `bash scripts/dev.sh` ở chế độ **nền** (run_in_background) — script khởi động cả API
   (FastAPI, cổng `${API_PORT:-8390}`) lẫn Web (Vite, cổng `${WEB_PORT:-5390}`).
2. Chờ tới khi `http://localhost:8390/health` trả 200 **và** web `:5390` lên (curl --retry).
3. Báo URL web **http://localhost:5390** cho tôi mở và bấm nút **"Quét giá ngay"**.
4. Nếu cổng bận: chạy lại `API_PORT=<x> WEB_PORT=<y> bash scripts/dev.sh` và đặt `VITE_API_URL=http://localhost:<x>` cho web.

Đây chỉ là khởi động dev local — KHÔNG commit gì.
