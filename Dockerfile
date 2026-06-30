# syntax=docker/dockerfile:1
# Image GỘP VRG: build web (Vite → tĩnh) rồi để FastAPI phục vụ CẢ SPA + API trong 1 container.
# Build từ repo ROOT:
#   docker buildx build --platform linux/amd64 -t registry.gitlab.com/flowbot1/flowbot/vrg:<tag> .
# Hoặc dùng deployment/deploy_script.sh.

# ---- Stage 1: build web tĩnh ----
FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
# Cùng origin với API → web gọi "/api/..." (URL tương đối), khỏi lo CORS / VITE_API_URL tuyệt đối.
ENV VITE_API_URL=""
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY apps/web/ ./
RUN pnpm build

# ---- Stage 2: API (FastAPI) + web tĩnh + crawler (quét giá) ----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS app
WORKDIR /app
ENV WEB_DIST_DIR=/app/web_dist \
    VRG_SERVICES_DIR=/app/services \
    API_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    UV_NO_SYNC=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Deps API
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --no-dev --frozen

# Deps crawler + trình duyệt Chromium (cho nút "Quét giá ngay" / scheduler — chạy subprocess `uv run`).
# FX (exchangerates sau Cloudflare) cần trình duyệt thật; các sàn khác thuần HTTP.
COPY services/crawlers/pyproject.toml services/crawlers/uv.lock ./services/crawlers/
RUN cd services/crawlers && uv sync --no-dev --frozen \
    && uv run playwright install --with-deps chromium

# Mã nguồn: app + package bulletin + package crawler + web build
COPY apps/api/app ./app
COPY services/bulletin/bulletin ./services/bulletin/bulletin
COPY services/crawlers/crawlers ./services/crawlers/crawlers
COPY --from=web /web/dist ./web_dist
EXPOSE 8000
# Chạy bằng `python -m uvicorn` (tự thêm /app vào sys.path → import được app.main dù
# package=false) và KHÔNG qua 'uv run' để tránh re-sync/tải gói dev lúc khởi động.
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
