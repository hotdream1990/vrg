"""Phục vụ web tĩnh (SPA React build) trực tiếp từ FastAPI — dùng cho image GỘP.

Khi biến môi trường WEB_DIST_DIR trỏ tới thư mục build của Vite (chứa index.html),
FastAPI phục vụ SPA ở "/" + fallback deep-link cho React Router và mount /assets.
Nếu không có (chạy API thuần khi dev), "/" chỉ trả thông tin service dạng JSON.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

# Tiền tố thuộc về API/hệ thống — KHÔNG bao giờ trả index.html cho các path này.
_API_PREFIXES = ("api/", "api", "health", "docs", "redoc", "openapi.json")
# File tĩnh tên cố định cần `no-cache` như index.html (Web Push: service worker + manifest).
_NO_CACHE_FILES = frozenset({"sw.js", "manifest.webmanifest"})


def mount_spa(app: FastAPI, app_env: str) -> bool:
    """Gắn SPA nếu WEB_DIST_DIR hợp lệ. Trả True nếu đang phục vụ web tĩnh.

    Gọi SAU khi đã include hết router API để /api/* được khớp trước catch-all SPA.
    """
    dist_dir = os.getenv("WEB_DIST_DIR")
    dist = Path(dist_dir).resolve() if dist_dir else None
    index = dist / "index.html" if dist else None

    if not (index and index.is_file()):
        @app.get("/", tags=["system"])
        def _service_info() -> dict[str, str]:
            """Thông tin service (chế độ API thuần — chưa kèm web build)."""
            return {"service": "vrg-caosu-api", "status": "ok", "env": app_env}

        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    # `index.html` KHÔNG được để trình duyệt tự đoán thời hạn lưu đệm. Không có `Cache-Control`,
    # trình duyệt áp quy tắc suy đoán (~10% khoảng thời gian kể từ `Last-Modified`): bản cũ để 3
    # ngày ⇒ giữ tới ~7 tiếng mà KHÔNG hỏi lại máy chủ, nên sau khi deploy người dùng vẫn nhận
    # index.html cũ → nó trỏ sang bundle JS cũ → "đã deploy mà không thấy gì đổi"
    # (chủ dự án gặp đúng ca này 20/09/2026, phải mở cửa sổ ẩn danh mới thấy).
    # `no-cache` = VẪN lưu, nhưng lần nào cũng hỏi lại; file ~1KB, không đổi thì trả 304.
    # Các file trong /assets giữ nguyên lưu đệm dài vì tên đã có mã băm — đổi nội dung là đổi tên.
    _HTML_HEADERS = {"Cache-Control": "no-cache"}

    @app.get("/", include_in_schema=False)
    async def _root() -> FileResponse:
        return FileResponse(index, headers=_HTML_HEADERS)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa_fallback(full_path: str) -> FileResponse:
        # /api/*, /health, /docs… đã khớp router phía trước; tới đây mà còn tiền tố này = 404 thật.
        if full_path.startswith(_API_PREFIXES):
            raise HTTPException(404, "Not found")
        target = (dist / full_path).resolve()
        # Chống path traversal: target phải nằm trong dist và là file thật.
        if full_path and dist in target.parents and target.is_file():
            # Service worker + manifest: tên cố định (không mã băm) → phải hỏi lại mỗi lần như
            # index.html, không thì bản sw.js cũ bám trình duyệt sau khi deploy.
            if full_path in _NO_CACHE_FILES:
                return FileResponse(target, headers=_HTML_HEADERS)
            return FileResponse(target)
        # deep-link React Router → trả index.html (cùng luật lưu đệm với "/")
        return FileResponse(index, headers=_HTML_HEADERS)

    return True
