#!/usr/bin/env bash
# Cron/launchd job: lấy giá Asian physical rubber mới nhất (chuỗi Reuters) từ
# marketscreener.com → quy đổi USD/T → upsert fact_price (source='reuters', physical).
# Idempotent: upsert theo ngày, chạy lại không nhân đôi.
#
# Cài (macOS launchd):
#   cp infra/launchd/com.vrg.marketscreener.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.vrg.marketscreener.plist
# Gỡ:
#   launchctl unload ~/Library/LaunchAgents/com.vrg.marketscreener.plist
#
# Hoặc crontab (chạy 18:30 hằng ngày):
#   30 18 * * * /bin/bash /<repo>/scripts/cron/daily-marketscreener.sh
set -euo pipefail

# launchd/cron có PATH tối thiểu → nạp đường dẫn uv + bin hệ thống
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="$REPO/data/marketscreener-cron.log"
mkdir -p "$REPO/data"

# Nạp credentials marketscreener + DATABASE_URL từ .env (không commit)
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a

echo "[$(date '+%F %T')] marketscreener daily fetch — bắt đầu" >> "$LOG"
cd "$REPO/services/crawlers"
# lấy ~5 bài gần nhất (bù phiên nghỉ/lỗi mạng); upsert idempotent
uv run --with "psycopg[binary]" python -m crawlers.marketscreener --persist 5 >> "$LOG" 2>&1
echo "[$(date '+%F %T')] xong" >> "$LOG"
