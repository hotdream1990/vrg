# Triển khai VRG (image gộp)

Đóng gói VRG thành **một image** `registry.gitlab.com/flowbot1/flowbot/vrg`:
build web (Vite) thành tĩnh rồi để **FastAPI phục vụ cả SPA lẫn API** trong 1 container
(cùng origin → web gọi `/api/...`, không cần CORS hay URL tuyệt đối).

| File | Vai trò |
|---|---|
| `../Dockerfile` | Multi-stage gộp web + API (build từ repo root) |
| `deploy_script.sh` | Build cho `linux/amd64` + push tag version (không đẩy `latest`) |
| `vrg_deploy.yaml` | Compose triển khai: `app` (image) + `db` (TimescaleDB) |
| `vrg.env.example` | Mẫu biến môi trường — copy thành `.env` |

## 1. Build & push

```bash
docker login registry.gitlab.com         # cần quyền push vào flowbot1/flowbot/vrg
./deployment/deploy_script.sh             # hỏi version (mặc định lấy từ pyproject.toml)
```

## 2. Triển khai

```bash
cp deployment/vrg.env.example deployment/.env   # điền JWT_SECRET, ADMIN_PASSWORD, DB_PASSWORD, API key…
VRG_TAG=0.1.0 docker compose --env-file deployment/.env -f deployment/vrg_deploy.yaml up -d
```

Mở `http://<host>:${APP_PORT:-8390}` — đăng nhập bằng `ADMIN_USERNAME/ADMIN_PASSWORD`.
Health check: `GET /health` · DB: `GET /health/db`.

## Ghi chú

- **Schema DB**: lấy từ `infra/db/init/*.sql`, chỉ chạy lần đầu khi volume `db-data` còn trống.
- **Crawler/Quét giá**: image này **chưa kèm** runtime trình duyệt (Firefox/Selenium) cho các
  crawler chạy bằng subprocess → nút "Quét giá ngay" sẽ trả lỗi 500 thân thiện. Phục vụ
  dashboard/bản tin/nhập liệu thì đủ. Nếu cần quét giá trong container, bổ sung Firefox +
  dependencies vào stage `app` của `../Dockerfile` (việc riêng, ngoài phạm vi image cơ bản).
- **VITE_API_URL** được set rỗng khi build (cùng origin). Nếu tách domain web/API về sau,
  truyền `--build-arg`/`ENV VITE_API_URL=https://api...` ở stage `web`.
