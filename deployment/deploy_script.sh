#!/usr/bin/env bash
# Build & push image GỘP VRG (web tĩnh + FastAPI) lên GitLab registry.
# Chạy từ bất kỳ đâu — script tự về repo root làm build context.
#
# Yêu cầu trước: docker login registry.gitlab.com   (image private)
set -euo pipefail

IMAGE_NAME="registry.gitlab.com/flowbot1/flowbot/vrg"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Version mặc định lấy từ apps/api/pyproject.toml (đồng bộ với apps/web/package.json).
DEFAULT_VERSION=$(grep -m1 '^version' "$ROOT/apps/api/pyproject.toml" | sed 's/.*"\(.*\)".*/\1/')

read -rp "Nhập version (mặc định: ${DEFAULT_VERSION}): " VERSION
VERSION=${VERSION:-$DEFAULT_VERSION}

# Validate dạng X.Y.Z
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Lỗi: version phải dạng '1.2.3'." >&2
  exit 1
fi

echo "▶ Build + push ${IMAGE_NAME}:${VERSION}"
echo "  context: ${ROOT}"

# buildx --push: build cho linux/amd64 rồi đẩy thẳng tag version (an toàn khi build trên máy ARM).
docker buildx build \
  --platform linux/amd64 \
  -f "${ROOT}/Dockerfile" \
  -t "${IMAGE_NAME}:${VERSION}" \
  --push \
  "${ROOT}"

echo "✅ Xong! Đã push ${IMAGE_NAME}:${VERSION}"
