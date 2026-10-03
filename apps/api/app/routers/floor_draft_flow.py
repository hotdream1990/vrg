"""Quy trình bản nháp giá sàn: Nháp → Dự thảo → Tờ trình → Áp dụng (plans/261003-quy-trinh-gia-san).

Chuyển bước · AI soạn nội dung tờ trình · tải hình dự thảo (PNG) · tải tờ trình (PDF, Word) · tỷ giá VCB.
Quyền như bản nháp: `floor_suggest` (ghi/AI cần mức Sửa; Lãnh đạo Tập đoàn xem + tải được).
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.core.security import require_cap, require_cap_edit
from app.schemas.floor_proposal import MemoAi, MoveStage
from app.services import doc_render, floor_draft_export, to_trinh_ai, to_trinh_memo, vcb_rate
from app.services import floor_draft_repo as repo
from app.services import floor_draft_service as svc
from app.services import floor_draft_stage as st
from app.services import floor_proposal as fp

router = APIRouter(prefix="/api/floor-proposal", tags=["floor-proposal"])

_VIEW = require_cap("floor_suggest")
_EDIT = require_cap_edit("floor_suggest")
_MIME = {"png": "image/png", "pdf": "application/pdf",
         "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def _draft(draft_id: int) -> dict:
    d = repo.get(draft_id)
    if not d:
        raise HTTPException(404, "Không có bản nháp này.")
    return d


def _file(make, draft_id: int, kind: str, inline: bool = False) -> Response:
    try:
        data, name = make(_draft(draft_id))
    except doc_render.RenderError as exc:
        raise HTTPException(503, str(exc)) from exc
    disp = "inline" if inline else "attachment"
    return Response(data, media_type=_MIME[kind], headers={
        "Content-Disposition": f"{disp}; filename=\"{name}\"; filename*=UTF-8''{quote(name)}",
        "Cache-Control": "no-store"})


@router.post("/drafts/{draft_id}/stage")
def move_stage(draft_id: int, body: MoveStage, username: str = Depends(_EDIT)) -> dict:
    try:
        saved = svc.change_stage(draft_id, body.to, username=username, base_updated_at=body.base_updated_at)
    except st.StageError as exc:
        raise HTTPException(400, str(exc)) from exc
    except svc.DraftConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    if not saved:
        raise HTTPException(404, "Không có bản nháp này.")
    return saved


@router.post("/drafts/{draft_id}/memo/ai")
def memo_ai(draft_id: int, body: MemoAi, username: str = Depends(_EDIT)) -> dict:
    """AI viết lại phần nhận định (mục I, II, cung – cầu) từ dữ liệu của bản nháp — KHÔNG lưu."""
    from app.services import llm

    d = _draft(draft_id)
    try:
        st.check_edit(st.normalize(d["stage"]), "memo")
    except st.StageError as exc:
        raise HTTPException(400, str(exc)) from exc
    base = svc.memo_for(d)
    memo = to_trinh_memo.clean(body.memo.model_dump(exclude_unset=True), base) if body.memo else base
    try:
        return to_trinh_ai.generate(d, memo, username)
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - lỗi nhà cung cấp AI → báo gọn, không 500
        raise HTTPException(502, f"AI chưa soạn được: {exc}".splitlines()[0][:300]) from exc


@router.get("/drafts/{draft_id}/du-thao.png")
def du_thao_png(draft_id: int, inline: bool = Query(False), _: str = Depends(_VIEW)) -> Response:
    return _file(floor_draft_export.du_thao_png, draft_id, "png", inline)


@router.get("/drafts/{draft_id}/to-trinh.pdf")
def to_trinh_pdf(draft_id: int, _: str = Depends(_VIEW)) -> Response:
    return _file(floor_draft_export.to_trinh_pdf, draft_id, "pdf")


@router.get("/drafts/{draft_id}/to-trinh.docx")
def to_trinh_docx(draft_id: int, _: str = Depends(_VIEW)) -> Response:
    return _file(floor_draft_export.to_trinh_docx_bytes, draft_id, "docx")


@router.get("/vcb-rate")
def vcb(date: str | None = Query(None, max_length=10), _: str = Depends(_VIEW)) -> dict:
    """Tỷ giá USD mua chuyển khoản của Vietcombank (cho chú thích hình dự thảo)."""
    try:
        r = vcb_rate.fetch_usd(fp.valid_date(date) if date else None)
    except Exception as exc:  # noqa: BLE001 - mạng/VCB lỗi → người dùng tự nhập tay
        raise HTTPException(502, f"Chưa lấy được tỷ giá VCB — nhập tay. ({exc})"[:300]) from exc
    return {"rate": r.get("mua_ck"), "date": r.get("date")}
