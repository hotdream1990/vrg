"""FastAPI gateway — AI Dự báo Giá Cao su (VRG).

Cổng backend phục vụ Dashboard · Forecast · Command Center.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import get_current_user, require_admin
from app.web_static import mount_spa
from app.routers import (
    auth,
    bulletins,
    config,
    floor,
    floor_suggest,
    health,
    inventory,
    market_movement,
    market_quote,
    member_region,
    member_unit,
    prices,
    public_purchase,
    schedules,
    users,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("vrg.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động: tạo tài khoản admin lần đầu (best-effort; bỏ qua nếu DB chưa sẵn sàng)."""
    try:
        from app.services import user_repo

        user_repo.seed_admin()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[auth] Bỏ qua seed admin (DB chưa sẵn sàng?): %s", exc)
    try:
        from app.services import scheduler

        scheduler.start()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[scheduler] Bỏ qua khởi động scheduler (DB chưa sẵn sàng?): %s", exc)
    yield
    try:
        from app.services import scheduler

        if scheduler._scheduler:
            scheduler._scheduler.shutdown(wait=False)
    except Exception:  # noqa: BLE001
        pass


def _app_version() -> str:
    """Version từ pyproject.toml (đồng bộ apps/web + tag deploy; có ở /app/pyproject.toml runtime)."""
    try:
        import tomllib
        from pathlib import Path
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        return tomllib.loads(pyproject.read_text("utf-8"))["project"]["version"]
    except Exception:  # noqa: BLE001
        return "0"


app = FastAPI(
    title="VRG — AI Dự báo Giá Cao su",
    version=_app_version(),
    description="Backend gateway: Dashboard · Forecast · Command Center",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://localhost:\d+",  # dev: web có thể chạy ở cổng bất kỳ
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Bắt mọi lỗi CHƯA xử lý → log đầy đủ phía server, trả 500 chung (không lộ traceback/nội bộ).

    HTTPException (401/403/404/400…) vẫn đi qua handler riêng của FastAPI; handler này chỉ
    áp cho lỗi ngoài dự kiến để tránh rò rỉ thông tin nhạy cảm ra client.
    """
    logger.error("Lỗi chưa xử lý: %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Lỗi hệ thống — vui lòng thử lại hoặc liên hệ quản trị."},
    )

# Mở: health + auth. Bảo vệ (cần JWT): router dữ liệu (đều fetch-based).
# bulletins để mở vì phục vụ ảnh banner (<img>) + tải file (<a>) không gửi được Bearer;
# UI vẫn bị chặn bởi login. Có thể siết sau bằng blob-fetch.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(bulletins.router)
app.include_router(public_purchase.router)  # CÔNG KHAI: đơn vị nhập giá mủ (gác bằng mật khẩu riêng)

_protected = [Depends(get_current_user)]
app.include_router(prices.router, dependencies=_protected)
app.include_router(floor.router, dependencies=_protected)
app.include_router(floor_suggest.router, dependencies=_protected)
app.include_router(member_unit.router, dependencies=_protected)
app.include_router(member_region.router, dependencies=_protected)
app.include_router(inventory.router, dependencies=_protected)
app.include_router(market_movement.router, dependencies=_protected)  # nhận định AI: per-route require_editor
app.include_router(market_quote.router, dependencies=_protected)
app.include_router(users.router, dependencies=[Depends(require_admin)])  # quản trị: chỉ admin
app.include_router(config.router, dependencies=[Depends(require_admin)])  # cấu hình: chỉ admin
app.include_router(schedules.router, dependencies=[Depends(require_admin)])  # lịch chạy: chỉ admin

# Phục vụ web tĩnh (image gộp) ở "/" — phải đặt SAU khi include hết router API.
# Dev/API thuần (không có WEB_DIST_DIR): "/" trả thông tin service dạng JSON.
mount_spa(app, settings.app_env)
