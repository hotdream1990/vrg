"""Nhật ký hoạt động — tra cứu ai · lúc nào · sửa gì (chỉ đọc, không có endpoint ghi).

Gác bằng quyền `audit` (admin mặc định có tất cả). Nhật ký do tầng repo tự ghi khi có
thay đổi số liệu, KHÔNG cho tạo/sửa/xoá qua API để đảm bảo tính toàn vẹn của vết.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.audit_meta import ACTIONS, ENTITIES
from app.core.security import require_cap
from app.services import audit_export, audit_repo, member_unit_repo

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_cap("audit"))])


#: Trần số dòng cho 1 lần xuất Excel (đủ cho tra cứu; tránh dựng file khổng lồ).
_EXPORT_LIMIT = 5000


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


@router.get("/meta")
def meta() -> dict:
    """Dữ liệu đổ vào các ô lọc: nhóm số liệu · loại thao tác · người thao tác · đơn vị."""
    return {
        "entities": [{"key": k, "label": v} for k, v in ENTITIES.items()],
        "actions": [{"key": k, "label": v} for k, v in ACTIONS.items()],
        "actors": audit_repo.known_actors(),
        "units": member_unit_repo.active_names(),
    }


@router.get("")
def search(
    date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD'"),
    date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD'"),
    actor: str | None = Query(None, description="Người thao tác (username)"),
    entity: str | None = Query(None, description="Nhóm số liệu"),
    action: str | None = Query(None, description="create | update | delete | import | scan"),
    company: str | None = Query(None, description="Đơn vị thành viên"),
    q: str | None = Query(None, max_length=120, description="Tìm tự do trong khoá/nội dung/ghi chú"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """Tra cứu nhật ký (mới nhất trước) → {items, total, page, page_size}."""
    _check_date("Từ ngày", date_from)
    _check_date("Đến ngày", date_to)
    if entity and entity not in ENTITIES:
        raise HTTPException(400, "Nhóm số liệu không hợp lệ.")
    if action and action not in ACTIONS:
        raise HTTPException(400, "Loại thao tác không hợp lệ.")
    res = audit_repo.search(date_from=date_from, date_to=date_to, actor=actor, entity=entity,
                            action=action, company=company, q=q,
                            limit=page_size, offset=(page - 1) * page_size)
    return {**res, "page": page, "page_size": page_size}


@router.get("/export")
def export_xlsx(
    date_from: str | None = Query(None), date_to: str | None = Query(None),
    actor: str | None = Query(None), entity: str | None = Query(None),
    action: str | None = Query(None), company: str | None = Query(None),
    q: str | None = Query(None, max_length=120),
) -> Response:
    """Xuất Excel đúng bộ lọc đang xem (tối đa 5.000 dòng gần nhất) — để kèm biên bản đối chiếu."""
    _check_date("Từ ngày", date_from)
    _check_date("Đến ngày", date_to)
    res = audit_repo.search(date_from=date_from, date_to=date_to, actor=actor, entity=entity,
                            action=action, company=company, q=q, limit=_EXPORT_LIMIT)
    name = f"nhat-ky-hoat-dong-{date_from or 'tat-ca'}-{date_to or 'nay'}.xlsx"
    return Response(
        content=audit_export.build_xlsx(res["items"]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
