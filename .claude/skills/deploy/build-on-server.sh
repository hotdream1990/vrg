#!/usr/bin/env bash
# Build image VRG TRÊN SERVER PROD rồi đẩy lên registry bằng quyền của MÁY DEV.
#
# Vì sao không build ở máy dev nữa (đo thật 20/09/2026): máy dev là arm64, build cho linux/amd64
# phải qua giả lập QEMU + mạng nhà → >20 phút chưa xong. Server là amd64 thật, 16 nhân, mạng
# trung tâm dữ liệu → 112 giây.
#
# Vì sao build ở server mà vẫn push được: token registry của Dokploy nằm trên server CHỈ CÓ QUYỀN
# PULL (`docker push` từ server trả `denied`). buildx chuyển tiếp credential của máy dev xuống
# builder, nên build chạy ở server còn push dùng quyền máy dev — KHÔNG phải mang secret lên server.
#
#   Dùng:  ./.claude/skills/deploy/build-on-server.sh 0.4.80
#   Rồi:   ./.claude/skills/deploy/dokploy-redeploy.local.sh 0.4.80
set -euo pipefail

TAG="${1:?Thiếu tag. Ví dụ: ./build-on-server.sh 0.4.80}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
# shellcheck source=/dev/null
source "$HERE/dokploy-target.local.env"

BUILDER="vrg-builder"
CONTEXT="vrg-prod"
LOG="/tmp/vrg-build-${TAG}.log"

echo "── Builder trên server ──────────────────────"
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  docker context inspect "$CONTEXT" >/dev/null 2>&1 \
    || docker context create "$CONTEXT" --docker "host=ssh://$SSH_USER@$SSH_HOST:$SSH_PORT" >/dev/null
  docker buildx create --name "$BUILDER" --driver docker-container \
    --platform linux/amd64 "$CONTEXT" >/dev/null
  echo "   ✓ đã tạo builder $BUILDER trên $SSH_HOST"
else
  echo "   ✓ builder $BUILDER đã có"
fi
docker buildx inspect "$BUILDER" --bootstrap >/dev/null

echo "── Build + push $TAG ────────────────────────"
echo "   log: $LOG"
START=$(date +%s)
# `--cache-from` báo "buildcache: not found" ở lần chạy đầu tiên sau khi registry bị xoá cache —
# đó chỉ là CẢNH BÁO, build vẫn tiếp tục bình thường.
cd "$ROOT"
docker buildx build --builder "$BUILDER" --platform linux/amd64 -f Dockerfile \
  -t "$IMAGE_BASE:$TAG" \
  --cache-to "type=registry,ref=$IMAGE_BASE:buildcache,mode=max" \
  --cache-from "type=registry,ref=$IMAGE_BASE:buildcache" \
  --push . > "$LOG" 2>&1

echo "   ✓ xong sau $(( $(date +%s) - START )) giây"

echo "── Kiểm image đã LÊN registry thật chưa ─────"
# buildx từng báo thành công nhưng fail ở bước push → không kiểm là deploy chết `manifest unknown`.
if docker manifest inspect "$IMAGE_BASE:$TAG" >/dev/null 2>&1; then
  echo "   ✅ $IMAGE_BASE:$TAG có trên registry"
  echo
  echo "Bước kế: ./.claude/skills/deploy/dokploy-redeploy.local.sh $TAG"
else
  echo "   ❌ KHÔNG thấy trên registry — xem $LOG" >&2
  exit 1
fi
