"""FastAPI gateway — AI Dự báo Giá Cao su (VRG).

Cổng backend phục vụ Dashboard · Forecast · Command Center.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.executive_readonly_guard import block_executive_writes
from app.core.security import block_unit_roles, get_current_user, require_admin, require_cap
from app.web_static import mount_spa
from app.routers import (
    anomalies,
    access_log,
    audit,
    auth,
    assistant,
    assistant_history,
    bulletins,
    config,
    customers,
    floor,
    floor_suggest,
    health,
    inventory,
    data_lock,
    edit_requests,
    market_demand,
    market_movement,
    market_quote,
    master_contracts,
    member_anomalies,
    member_edit_requests,
    member_region,
    member_self,
    member_unit,
    prices,
    public_purchase,
    purchase_auto_sync,
    sales_contracts,
    schedules,
    series,
    settings as settings_router,
    support,
    support_reminders,
    unit_analytics,
    unit_daily,
    users,
    weekly_report_inputs,
    weekly_reports,
    weekly_sources,
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
        from app.services import access_repo

        access_repo.purge_old()  # dọn lịch sử truy cập quá hạn lưu (400 ngày)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[access] Bỏ qua dọn lịch sử truy cập: %s", exc)
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
    # Lãnh đạo Tập đoàn chỉ xem: chặn method ghi ở tầng app để không endpoint nào lọt.
    dependencies=[Depends(block_executive_writes)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"http://localhost:\d+",  # dev: web có thể chạy ở cổng bất kỳ
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Web đọc header này để biết 403 là do hàng rào thời gian → mời gửi «Đề nghị sửa».
    expose_headers=["X-Edit-Blocked"],
)


@app.middleware("http")
async def _audit_context(request: Request, call_next):
    """Đặt ngữ cảnh (ai thao tác · IP) cho Nhật ký hoạt động — repo ghi dữ liệu tự đọc lại.

    Phải đặt ở MIDDLEWARE (không phải dependency): ContextVar set trong dependency chạy ở
    threadpool sẽ không lan tới handler. Giải mã token tại chỗ (không truy vấn DB) nên rất nhẹ.
    """
    from app.core import request_ctx
    from app.core.security import decode_bearer

    actor, on_behalf = decode_bearer(request.headers.get("authorization"))
    request_ctx.set_request(actor, _client_ip(request), on_behalf)
    return await call_next(request)


def _client_ip(request: Request) -> str:
    """IP THẬT của khách sau proxy. Prod chạy sau Cloudflare→Traefik nên `X-Forwarded-For[0]` là
    IP edge Cloudflare (dải 162.158.x.x, đổi mỗi request) — KHÔNG dùng để định danh được. Cloudflare
    đặt `CF-Connecting-IP` = IP thật của khách → ưu tiên header này, rồi mới tới XFF phần tử đầu,
    cuối cùng là peer trực tiếp."""
    cf = (request.headers.get("cf-connecting-ip") or "").strip()
    if cf:
        return cf
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")


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
# Số liệu/danh mục MỨC TẬP ĐOÀN: tài khoản của đơn vị thành viên (nhập liệu + lãnh đạo) không
# có màn nào dùng, mà nội dung thì có phần chia theo TỪNG đơn vị (giá thu mua từng đơn vị,
# danh mục đơn vị…) → chặn hẳn, đừng dựa vào việc "menu không có link".
_hq_only = [Depends(block_unit_roles)]
app.include_router(prices.router, dependencies=_hq_only)
app.include_router(purchase_auto_sync.router, dependencies=_protected)  # cầu tự động: giá đơn vị tự khai → lớp chuyên viên
app.include_router(floor.router, dependencies=_hq_only)
# Các màn phân tích/bản tin gác theo quyền (admin=tất cả, editor=được-cấp, viewer=không) — cả đọc lẫn ghi.
app.include_router(floor_suggest.router, dependencies=[Depends(require_cap("floor_suggest"))])
app.include_router(member_unit.router, dependencies=_hq_only)
app.include_router(member_region.router, dependencies=_hq_only)
app.include_router(member_self.router, dependencies=_protected)  # đơn vị thành viên tự nhập giá của mình
app.include_router(market_demand.router, dependencies=_protected)  # nhu cầu thị trường (editor có quyền: xem/sửa mọi đơn vị)
app.include_router(data_lock.router, dependencies=_protected)  # chốt số liệu đơn vị (đơn vị xác nhận · Ban theo dõi)
# Đề nghị sửa số liệu quá khứ: đơn vị gửi (/api/member/edit-requests) · Ban duyệt (quyền `edit_request`).
app.include_router(member_edit_requests.router, dependencies=_protected)
# Cảnh báo bất thường của RIÊNG đơn vị mình — cho lãnh đạo đơn vị (tự gác `get_current_leader`).
app.include_router(member_anomalies.router, dependencies=_protected)
app.include_router(edit_requests.router)  # tự gác quyền `edit_request` trong router
app.include_router(unit_daily.router, dependencies=[Depends(require_cap("unit_daily"))])  # báo cáo tiêu thụ–tồn kho theo ngày (chuyên viên xem/sửa mọi đơn vị)
app.include_router(unit_analytics.router, dependencies=[Depends(require_cap("unit_daily"))])  # thống kê/lọc số liệu đơn vị đã nhập (chỉ đọc)
# Hợp đồng & khách hàng: DÙNG CHUNG cho đơn vị thành viên lẫn chuyên viên — router tự ép phạm vi
# đơn vị theo tài khoản (cap_or_member_scope), nên chỉ gác đăng nhập ở đây.
app.include_router(customers.router, dependencies=_protected)
app.include_router(master_contracts.router, dependencies=_protected)  # hợp đồng mẹ HĐNT/HĐDH (cùng quyền `sales_contract`)
app.include_router(sales_contracts.router, dependencies=_protected)
app.include_router(audit.router)  # Nhật ký hoạt động (tự gác quyền `audit` trong router)
app.include_router(access_log.router)  # Lịch sử truy cập (ghi: mọi user · đọc: quyền `audit`)
# Hỗ trợ & Thông báo: DÙNG CHUNG cho lãnh đạo đơn vị (role=leader) và Tập đoàn (quyền `support`)
# — router tự nhận diện bên nào và ép phạm vi đơn vị, nên không gác cap ở đây.
app.include_router(support.router)
app.include_router(support_reminders.router)  # nhắc lịch — cùng phạm vi truy cập (support_scope)
app.include_router(assistant.router, dependencies=[Depends(require_cap("assistant"))])  # Trợ lý AI (hỏi đáp số liệu + tư vấn giá sàn)
app.include_router(assistant_history.router, dependencies=[Depends(require_cap("assistant"))])  # Lịch sử hỏi–đáp Trợ lý AI (xem lại + dọn log)
app.include_router(settings_router.router, dependencies=_protected)  # cài đặt đọc-được (cửa sổ nhập liệu)
app.include_router(inventory.router, dependencies=_hq_only)
# Chuỗi số liệu theo ngày cho dashboard (thu mua · tồn kho · tiêu thụ) — chỉ đọc. Mở cho mọi tài
# khoản NỘI BỘ (kể cả Người xem, vì Dashboard hiện cho họ), nhưng CHẶN tài khoản đơn vị: số ở đây
# chia được theo từng đơn vị nên đơn vị này sẽ đọc được số của đơn vị kia.
app.include_router(series.router, dependencies=[Depends(block_unit_roles)])
app.include_router(market_movement.router, dependencies=[Depends(require_cap("market_movement"))])
app.include_router(market_quote.router, dependencies=_protected)
app.include_router(weekly_reports.router, dependencies=[Depends(require_cap("bulletin_weekly"))])
# Đầu vào báo cáo tuần (đính kèm · chỉ số thị trường · tin trong kỳ) + danh mục nguồn tham khảo:
# cùng quyền xem màn; endpoint ghi tự gác thêm mức Sửa trong router.
app.include_router(weekly_report_inputs.router, dependencies=[Depends(require_cap("bulletin_weekly"))])
app.include_router(weekly_sources.router, dependencies=[Depends(require_cap("bulletin_weekly"))])
app.include_router(users.router, dependencies=[Depends(require_admin)])  # quản trị: chỉ admin
app.include_router(config.router, dependencies=[Depends(require_admin)])  # cấu hình: chỉ admin
app.include_router(schedules.router, dependencies=[Depends(require_admin)])  # lịch chạy: chỉ admin
app.include_router(anomalies.router, dependencies=[Depends(require_admin)])  # cảnh báo bất thường: chỉ admin

# Phục vụ web tĩnh (image gộp) ở "/" — phải đặt SAU khi include hết router API.
# Dev/API thuần (không có WEB_DIST_DIR): "/" trả thông tin service dạng JSON.
mount_spa(app, settings.app_env)
