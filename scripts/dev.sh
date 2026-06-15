#!/usr/bin/env bash
# Launcher dev VRG — chạy API (FastAPI) + Web (Vite) cùng lúc. Ctrl+C để dừng cả hai.
# Cổng riêng VRG: API 8390 · Web 5390. Đổi qua biến API_PORT / WEB_PORT (xem .env.example).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
: "${API_PORT:=8390}"
: "${WEB_PORT:=5390}"

trap 'echo; echo "⏹  Dừng dev servers."; kill 0' EXIT INT TERM

echo "▶ API → http://localhost:${API_PORT}    Web → http://localhost:${WEB_PORT}"
echo "  (mở web rồi bấm \"Quét giá ngay\" · Ctrl+C để dừng cả hai)"
echo

( cd "$ROOT/apps/api" && API_PORT="$API_PORT" uv run python -m app ) &
( cd "$ROOT/apps/web" && WEB_PORT="$WEB_PORT" pnpm dev ) &
wait
