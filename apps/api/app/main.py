"""FastAPI gateway — AI Dự báo Giá Cao su (VRG).

Cổng backend phục vụ Dashboard · Forecast · Command Center.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.security import get_current_user, require_admin
from app.routers import (
    auth,
    bulletins,
    config,
    floor,
    floor_suggest,
    health,
    inventory,
    member_unit,
    prices,
    users,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi động: tạo tài khoản admin lần đầu (best-effort; bỏ qua nếu DB chưa sẵn sàng)."""
    try:
        from app.services import user_repo

        user_repo.seed_admin()
    except Exception as exc:  # noqa: BLE001
        print(f"[auth] Bỏ qua seed admin (DB chưa sẵn sàng?): {exc}")
    yield


app = FastAPI(
    title="VRG — AI Dự báo Giá Cao su",
    version="0.1.0",
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

# Mở: health + auth. Bảo vệ (cần JWT): router dữ liệu (đều fetch-based).
# bulletins để mở vì phục vụ ảnh banner (<img>) + tải file (<a>) không gửi được Bearer;
# UI vẫn bị chặn bởi login. Có thể siết sau bằng blob-fetch.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(bulletins.router)

_protected = [Depends(get_current_user)]
app.include_router(prices.router, dependencies=_protected)
app.include_router(floor.router, dependencies=_protected)
app.include_router(floor_suggest.router, dependencies=_protected)
app.include_router(member_unit.router, dependencies=_protected)
app.include_router(inventory.router, dependencies=_protected)
app.include_router(users.router, dependencies=[Depends(require_admin)])  # quản trị: chỉ admin
app.include_router(config.router, dependencies=[Depends(require_admin)])  # cấu hình: chỉ admin


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Thông tin service."""
    return {"service": "vrg-caosu-api", "status": "ok", "env": settings.app_env}
