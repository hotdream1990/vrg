"""Lịch sử truy cập: web báo "vừa vào trang nào" (POST) + màn tra cứu cho quản trị (GET).

Phân quyền cố ý khác nhau giữa hai chiều: ghi thì MỌI tài khoản đã đăng nhập đều được (chính họ
đang dùng hệ thống), còn đọc phải có quyền `audit` — xem người khác dùng gì là việc của quản trị.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.core.access_meta import EVENTS, MAX_PATH
from app.core.roles import ROLE_LABEL
from app.core.security import get_current_user, require_cap
from app.services import access_export, access_repo, access_stats, member_unit_repo, user_repo

router = APIRouter(prefix="/api/access-log", tags=["access-log"])

#: Trần số dòng chi tiết cho 1 lần xuất Excel (sheet tổng hợp không bị giới hạn này).
_EXPORT_LIMIT = 5000


class PageView(BaseModel):
    """Lượt vào trang do web bắn lên — chỉ nhận ĐƯỜNG DẪN, nhãn do server tự ánh xạ."""

    #: Chỉ nhận ký tự có thật trong đường dẫn (chữ/số/`-_/.:%~`). Chuỗi lạ bị từ chối ngay ở cửa
    #: nên không vào được nhật ký — web bắn xong là quên, 422 không ảnh hưởng người dùng.
    path: str = Field(min_length=1, max_length=MAX_PATH, pattern=r"^/[A-Za-z0-9\-_/.:%~]*$")


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


class Filters:
    """Bộ lọc dùng chung cho tra cứu · tổng hợp · xuất Excel (khai 1 lần, dùng 4 chỗ)."""

    def __init__(
        self,
        date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD'"),
        date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD'"),
        username: str | None = Query(None, description="Tài khoản"),
        role: str | None = Query(None, description="Vai trò, vd 'leader'"),
        event: str | None = Query(None, description="login | login_failed | page"),
        company: str | None = Query(None, description="Đơn vị thành viên"),
        q: str | None = Query(None, max_length=120, description="Tìm tự do: tài khoản · trang · IP"),
    ) -> None:
        _check_date("Từ ngày", date_from)
        _check_date("Đến ngày", date_to)
        if event and event not in EVENTS:
            raise HTTPException(400, "Loại sự kiện không hợp lệ.")
        if role and role not in ROLE_LABEL:
            raise HTTPException(400, "Vai trò không hợp lệ.")
        self.kw = {"date_from": date_from, "date_to": date_to, "username": username,
                   "role": role, "company": company, "q": q}
        self.event = event

    def detail(self) -> dict:
        return {**self.kw, "event": self.event}


@router.post("", status_code=204, response_class=Response)
def track_page(body: PageView, request: Request,
               username: str = Depends(get_current_user)) -> Response:
    """Web gọi mỗi khi người dùng chuyển màn. Không bao giờ báo lỗi ra ngoài: ghi vết hỏng thì
    thôi, tuyệt đối không được làm gián đoạn việc đang làm của người dùng."""
    user = user_repo.get_user(username)
    if user:
        access_repo.log_page(user, body.path, request.headers.get("user-agent", ""))
    return Response(status_code=204)


@router.get("/meta", dependencies=[Depends(require_cap("audit"))])
def meta() -> dict:
    """Dữ liệu đổ vào các ô lọc: sự kiện · vai trò · tài khoản đã xuất hiện · đơn vị."""
    return {
        "events": [{"key": k, "label": v} for k, v in EVENTS.items()],
        "roles": [{"key": k, "label": v} for k, v in ROLE_LABEL.items()],
        "users": access_repo.known_users(),
        "units": member_unit_repo.active_names(),
    }


@router.get("/summary", dependencies=[Depends(require_cap("audit"))])
def summary(f: Filters = Depends()) -> dict:
    """Mỗi tài khoản 1 dòng (đăng nhập gần nhất · số lượt xem · trang hay vào) + xếp hạng trang."""
    return {"items": access_stats.summary(**f.kw), "top_pages": access_stats.top_pages(**f.kw)}


@router.get("", dependencies=[Depends(require_cap("audit"))])
def search(f: Filters = Depends(), page: int = Query(1, ge=1),
           page_size: int = Query(50, ge=1, le=200)) -> dict:
    """Chi tiết từng lượt (mới nhất trước) → {items, total, page, page_size}."""
    res = access_repo.search(**f.detail(), limit=page_size, offset=(page - 1) * page_size)
    return {**res, "page": page, "page_size": page_size}


@router.get("/export", dependencies=[Depends(require_cap("audit"))])
def export_xlsx(f: Filters = Depends()) -> Response:
    """Xuất Excel đúng bộ lọc đang xem: sheet tổng hợp + sheet chi tiết (tối đa 5.000 dòng)."""
    detail = access_repo.search(**f.detail(), limit=_EXPORT_LIMIT)
    content = access_export.build_xlsx(access_stats.summary(**f.kw), detail["items"])
    name = f"lich-su-truy-cap-{f.kw['date_from'] or 'tat-ca'}-{f.kw['date_to'] or 'nay'}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
