# apps/api — FastAPI Gateway

Backend API (Python/FastAPI) — cổng phục vụ Dashboard & Chatbot, điều phối các `services/`.

## Cấu trúc dự kiến
```
app/
  main.py        khởi tạo FastAPI
  core/          config, security, kết nối DB
  routers/       dashboard · forecast · chat · alerts
  schemas/       Pydantic request/response
  services/      lớp gọi tới services/* và DB
tests/
```

## Quy ước
- Quản lý bằng **uv**; lint **ruff**; type **mypy**.
- Response chuẩn `{ success, data | error }` (xem patterns trong code-standards).
- Không hardcode secret — dùng `.env`.

## Chạy & test (đã verified)
```bash
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000/health
uv run pytest                          # 2 passed
```
> Skeleton có sẵn `/` và `/health`. Heavy ML libs (Prophet/XGBoost) thêm ở Sprint 2.
