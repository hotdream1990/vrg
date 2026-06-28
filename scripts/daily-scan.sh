#!/usr/bin/env bash
# Quét giá VRG hàng ngày → ghi TimescaleDB (tích lũy lịch sử). Gọi bởi launchd/cron.
# Cài lịch: xem infra/launchd/com.vrg.daily-scan.plist
set -uo pipefail

# launchd/cron có PATH tối thiểu → nạp đường dẫn uv + docker + bin hệ thống (tránh exit 127)
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

echo "=== daily-scan $(date '+%Y-%m-%d %H:%M:%S') ==="

# Đảm bảo DB chạy (best-effort; nếu Docker tắt thì job sẽ degrade & ghi log).
DB_PORT="${DB_PORT:-5433}" DB_PASSWORD="${DB_PASSWORD:-changeme}" \
  docker compose -f infra/docker/docker-compose.yml up -d db >/dev/null 2>&1 || \
  echo "warn: không khởi động được DB container (có thể Docker chưa chạy)"

# Chạy job trong uv env của apps/api (có sqlalchemy/psycopg).
cd apps/api && exec uv run python -m app.jobs.daily_scan
