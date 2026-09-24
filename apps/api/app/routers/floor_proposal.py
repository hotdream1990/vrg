"""API phương án giá sàn nháp (không ghi DB) + bản nháp tờ trình (ghi DB).

- Phương án: dùng ở màn Trợ lý AI (quyền `assistant`) lẫn màn soạn nháp (quyền `floor_suggest`) —
  chỉ tính toán, không lưu gì, nên mở cho một trong hai quyền.
- Bản nháp: quyền `floor_suggest`; ghi cần mức Sửa (Lãnh đạo Tập đoàn chỉ xem).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.security import assert_cap, require_any_cap, require_cap, require_cap_edit
from app.schemas.floor_proposal import (
    ApplyProposal, CreateDraft, CreateProposal, PreviewProposal, UpdateDraft, clean_paragraphs,
)
from app.services import floor_draft_repo as repo
from app.services import floor_draft_service as svc
from app.services import floor_proposal as fp
from app.services import floor_proposal_ops as ops

router = APIRouter(prefix="/api/floor-proposal", tags=["floor-proposal"])

_ANY = require_any_cap("assistant", "floor_suggest")


def _bad(exc: Exception) -> HTTPException:
    return HTTPException(400, str(exc))


def _clean(raw: dict) -> dict:
    try:
        prop = fp.sanitize(raw)
    except fp.ProposalError as exc:
        raise _bad(exc) from exc
    if not prop:
        raise HTTPException(400, "Thiếu phương án.")
    return prop


@router.post("/create")
def create(body: CreateProposal, _: str = Depends(_ANY)) -> dict:
    """Lập phương án mới: mức mô hình (base=model) hoặc giá hiện hành (base=current)."""
    try:
        return fp.build(body.as_of, body.base, body.model or fp.fs.DEFAULT_MODEL)
    except fp.ProposalError as exc:
        raise _bad(exc) from exc


@router.post("/apply")
def apply(body: ApplyProposal, _: str = Depends(_ANY)) -> dict:
    """Áp thay đổi (sửa tay, hoàn tác, làm lại…) — trả phương án mới, không lưu gì."""
    prop = _clean(body.proposal)
    try:
        new, applied, warnings = ops.apply(prop, [c.model_dump() for c in body.changes], body.by)
    except fp.ProposalError as exc:
        raise _bad(exc) from exc
    return {"proposal": new, "applied": applied, "warnings": warnings}


@router.post("/preview", response_class=HTMLResponse)
def preview(body: PreviewProposal, username: str = Depends(_ANY)) -> HTMLResponse:
    """Tờ trình (HTML) từ phương án đang soạn — kể cả phần chưa lưu của một bản nháp (draft_id)."""
    prop = _clean(body.proposal)
    if body.draft_id is not None:
        assert_cap(username, "floor_suggest")  # ảnh chụp của bản nháp chỉ người có quyền nháp xem
        draft = repo.get(body.draft_id)
        if not draft:
            raise HTTPException(404, "Không có bản nháp này.")
        doc = draft["doc"]
    else:
        doc = svc.market_doc(prop["as_of"])
    return HTMLResponse(svc.render(prop, doc, clean_paragraphs(body.n1), clean_paragraphs(body.n2)))


@router.get("/drafts")
def list_drafts(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=repo.PAGE_SIZE_MAX),
                _: str = Depends(require_cap("floor_suggest"))) -> dict:
    return repo.list_page(page, page_size)


def _draft_or_404(draft_id: int) -> dict:
    d = repo.get(draft_id)
    if not d:
        raise HTTPException(404, "Không có bản nháp này.")
    return d


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: int, _: str = Depends(require_cap("floor_suggest"))) -> dict:
    return _draft_or_404(draft_id)


@router.get("/drafts/{draft_id}/html", response_class=HTMLResponse)
def draft_html(draft_id: int, _: str = Depends(require_cap("floor_suggest"))) -> HTMLResponse:
    d = _draft_or_404(draft_id)
    return HTMLResponse(svc.render(d["proposal"], d["doc"]))


@router.post("/drafts", status_code=201)
def create_draft(body: CreateDraft, username: str = Depends(require_cap_edit("floor_suggest"))) -> dict:
    try:
        return svc.create(proposal=body.proposal, as_of=body.as_of, model=body.model, title=body.title,
                          note=body.note, source=body.source, username=username)
    except fp.ProposalError as exc:
        raise _bad(exc) from exc


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: int, body: UpdateDraft,
                 username: str = Depends(require_cap_edit("floor_suggest"))) -> dict:
    try:
        saved = svc.update(draft_id, title=body.title, note=body.note, proposal=body.proposal,
                           n1=clean_paragraphs(body.n1) or [], n2=clean_paragraphs(body.n2) or [],
                           username=username, base_updated_at=body.base_updated_at)
    except fp.ProposalError as exc:
        raise _bad(exc) from exc
    except svc.DraftConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    if not saved:
        raise HTTPException(404, "Không có bản nháp này.")
    return saved


@router.delete("/drafts/{draft_id}")
def delete_draft(draft_id: int, _: str = Depends(require_cap_edit("floor_suggest"))) -> dict:
    if not repo.delete(draft_id):
        raise HTTPException(404, "Không có bản nháp này.")
    return {"deleted": 1}
