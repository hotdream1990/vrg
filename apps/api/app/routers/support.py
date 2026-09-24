"""Router Hỗ trợ & Thông báo — hộp thư hai chiều giữa Tập đoàn và lãnh đạo đơn vị thành viên.

Phạm vi truy cập (ai đứng bên nào, thấy đơn vị nào) nằm ở `support_scope`; nhắc lịch nằm ở
`support_reminders`. Ở đây chỉ có luồng tin: danh sách · chi tiết · gửi · phản hồi · file đính kèm.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from app.core.security import require_admin
from app.routers.support_scope import (
    Scope, ScopeDep, assert_hq, assert_may_write, can_write, display_name, store,
)
from app.schemas.support import AnnounceCreate, ReplyCreate, StatusUpdate, UnitRequestCreate
from app.services import (
    attachment_store, member_region_repo, member_unit_repo, support_notify, support_query,
    support_reminder_repo, support_repo,
)

router = APIRouter(prefix="/api/support", tags=["support"])


def _thread_in_scope(thread_id: int, scope: Scope) -> dict:
    _, companies, _ = scope
    thread = support_repo.get_thread(thread_id, companies)
    if not thread:
        raise HTTPException(404, "Không tìm thấy tin trong phạm vi tài khoản.")
    return thread


# ── Ngữ cảnh + danh sách ──
@router.get("/context")
def context(scope: ScopeDep) -> dict:
    """Thông tin dựng màn: đứng bên nào · đơn vị được chọn · khu vực · có được gửi không."""
    _, companies, side = scope
    is_hq = side == support_repo.HQ
    return {
        "side": side,
        "can_write": can_write(scope),
        "units": member_unit_repo.active_names() if is_hq else companies,
        "regions": member_region_repo.active_names() if is_hq else [],
        "unread": support_query.count_unread(companies, side),
        "accept_label": attachment_store.ACCEPT_LABEL,
    }


@router.get("/unread")
def unread(scope: ScopeDep) -> dict:
    """Số tin chưa đọc — cho huy hiệu trên menu."""
    _, companies, side = scope
    return {"count": support_query.count_unread(companies, side)}


@router.get("/threads")
def list_threads(
    scope: ScopeDep,
    kind: str | None = Query(None, description="request | announce | reminder | alert"),
    status: str | None = None,
    q: str | None = None,
    company: str | None = None,
    batch_id: str | None = None,
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=support_query.MAX_PAGE_SIZE),
) -> dict:
    """Hộp thư (phân trang ở server). Bên đơn vị luôn bị lọc về đúng các đơn vị được gán."""
    _, companies, side = scope
    kinds = [kind] if kind in support_repo.KINDS else None
    return support_query.list_threads(
        companies, side, kinds=kinds, status=status, q=q, company=company, batch_id=batch_id,
        unread_only=unread_only, page=page, page_size=page_size,
    )


@router.get("/batches")
def list_batches(
    scope: ScopeDep,
    status: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=support_query.MAX_PAGE_SIZE),
) -> dict:
    """Các ĐỢT gửi của Tập đoàn, gom 1 dòng/lần gửi (chỉ phía Tập đoàn)."""
    assert_hq(scope)
    return support_query.list_batches(
        kinds=[support_repo.KIND_ANNOUNCE, support_repo.KIND_REMINDER, support_repo.KIND_ALERT],
        status=status, q=q, page=page, page_size=page_size,
    )


@router.get("/threads/{thread_id}")
def get_thread(thread_id: int, scope: ScopeDep) -> dict:
    """Chi tiết 1 luồng + toàn bộ phản hồi. Mở ra là đánh dấu đã đọc cho chính bên đang xem."""
    _, companies, side = scope
    thread = _thread_in_scope(thread_id, scope)
    support_repo.mark_read(thread_id, side, companies)
    return {"thread": thread, "messages": support_repo.messages(thread_id)}


# ── Gửi tin ──
@router.post("/requests")
def create_request(body: UnitRequestCreate, scope: ScopeDep) -> dict:
    """Lãnh đạo đơn vị mở một yêu cầu hỗ trợ gửi Tập đoàn."""
    username, companies, side = scope
    if side != support_repo.UNIT:
        raise HTTPException(403, "Chỉ lãnh đạo đơn vị thành viên mới gửi được yêu cầu hỗ trợ.")
    if body.company not in (companies or []):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")
    subject = body.subject.strip()
    files = [f.model_dump() for f in body.files]
    ids = support_repo.open_threads([body.company], support_repo.KIND_REQUEST, subject, body.body,
                                    files, username, display_name(username), support_repo.UNIT)
    support_notify.notify_to_hq(ids[0], body.company, subject, body.body, display_name(username))
    return {"ok": True, "thread_id": ids[0]}


@router.post("/announcements")
def create_announcement(body: AnnounceCreate, scope: ScopeDep) -> dict:
    """Tập đoàn gửi thông báo xuống 1 đơn vị · một nhóm · tất cả (mỗi đơn vị một luồng RIÊNG)."""
    username, _, _ = scope
    assert_hq(scope)
    assert_may_write(scope)
    units = support_reminder_repo.targets(body.model_dump())
    if not units:
        raise HTTPException(400, "Không có đơn vị nào trong phạm vi đã chọn.")
    subject = body.subject.strip()
    files = [f.model_dump() for f in body.files]
    ids = support_repo.open_threads(units, support_repo.KIND_ANNOUNCE, subject, body.body, files,
                                    username, display_name(username), support_repo.HQ)
    support_notify.notify_to_units(list(zip(ids, units, strict=True)), subject, body.body,
                                   display_name(username))
    return {"ok": True, "units": units, "threads": len(ids)}


@router.post("/threads/{thread_id}/reply")
def reply(thread_id: int, body: ReplyCreate, scope: ScopeDep) -> dict:
    """Phản hồi trong luồng. Phản hồi nằm TRONG luồng nên chỉ đúng đơn vị của luồng đọc được."""
    username, _, side = scope
    assert_may_write(scope)
    thread = _thread_in_scope(thread_id, scope)
    # Mỗi thẻ = MỘT trường hợp: khép rồi thì không nhận thêm phản hồi, có việc mới thì mở thẻ mới.
    if thread["status"] == "closed":
        raise HTTPException(409, "Trường hợp này đã khép lại — vui lòng mở thẻ mới cho việc mới.")
    if not body.body.strip() and not body.files:
        raise HTTPException(400, "Nhập nội dung phản hồi hoặc đính kèm file.")
    files = [f.model_dump() for f in body.files]
    msg = support_repo.add_message(thread_id, side, username, display_name(username),
                                   body.body, files)
    excerpt = body.body or "(chỉ có file đính kèm)"
    if side == support_repo.HQ:
        support_notify.notify_to_units([(thread_id, thread["company"])], thread["subject"],
                                       excerpt, display_name(username))
    else:
        support_notify.notify_to_hq(thread_id, thread["company"], thread["subject"], excerpt,
                                    display_name(username))
    return {"ok": True, "message": msg}


@router.put("/threads/{thread_id}/status")
def set_status(thread_id: int, body: StatusUpdate, scope: ScopeDep) -> dict:
    """Đóng / mở lại luồng (cả hai bên đều làm được với luồng trong phạm vi của mình)."""
    _, companies, _ = scope
    assert_may_write(scope)
    _thread_in_scope(thread_id, scope)
    support_repo.set_status(thread_id, body.status, companies)
    return {"ok": True, "status": body.status}


@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, username: str = Depends(require_admin)) -> dict:
    """Xoá hẳn 1 luồng — chỉ quản trị (dọn tin gửi nhầm)."""
    if not support_repo.delete_thread(thread_id):
        raise HTTPException(404, "Không tìm thấy tin.")
    return {"ok": True}


# ── File đính kèm ──
@router.post("/file")
def upload_file(file: UploadFile, scope: ScopeDep) -> dict:
    """Upload đính kèm (ảnh · PDF · Word · Excel · ZIP) — trả tên lưu để gắn vào tin."""
    assert_may_write(scope)
    return store.save(file)


@router.get("/file/{name}")
def get_file(name: str, scope: ScopeDep, filename: str | None = Query(None)):
    """Tải đính kèm. Chặn tải chéo: file phải thuộc luồng nằm trong phạm vi tài khoản."""
    _, companies, side = scope
    owners = support_repo.companies_of_file(name)
    if not owners:
        # File vừa upload cho tin/lịch nhắc chưa gửi: chỉ Tập đoàn (người đang soạn) xem lại được.
        if side == support_repo.HQ:
            return store.serve(name, filename)
        raise HTTPException(404, "Không tìm thấy file đính kèm.")
    if companies is not None and not owners & set(companies):
        raise HTTPException(404, "Không tìm thấy file trong phạm vi tài khoản.")
    return store.serve(name, filename)
