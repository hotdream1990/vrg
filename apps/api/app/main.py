"""FastAPI gateway — AI Dự báo Giá Cao su (VRG).

Cổng backend phục vụ Dashboard · Forecast · Command Center.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import bulletins, health, prices

app = FastAPI(
    title="VRG — AI Dự báo Giá Cao su",
    version="0.1.0",
    description="Backend gateway: Dashboard · Forecast · Command Center",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://localhost:\d+",  # dev: web có thể chạy ở cổng bất kỳ
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(prices.router)
app.include_router(bulletins.router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    """Thông tin service."""
    return {"service": "vrg-caosu-api", "status": "ok", "env": settings.app_env}
