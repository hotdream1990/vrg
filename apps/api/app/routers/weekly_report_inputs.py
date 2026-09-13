"""Router đầu vào của 1 Báo cáo tuần: tài liệu đính kèm · chỉ số thị trường · tin vietnambiz trong kỳ.

Xem: quyền `bulletin_weekly` (gác ở main). Ghi (tải/sửa/xoá file, AI tóm tắt): thêm mức Sửa.
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.security import require_cap_edit
from app.routers.weekly_reports import week_key_or_400
from app.schemas.weekly_report_inputs import (
    AttachmentPatch,
    IndicatorsResponse,
    NewsResponse,
    WeeklyAttachment,
)
from app.services import market_analysis, weekly_attachment_service as att_svc
from app.services import weekly_market_feed, weekly_news, weekly_period, weekly_source_repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/weekly-reports/{week_key}", tags=["weekly-report-inputs"])
_edit = require_cap_edit("bulletin_weekly")
_NOT_FOUND = "Không tìm thấy tài liệu đính kèm."


_wk = week_key_or_400  # khoá tuần chuẩn (Thứ 2 ISO), 400 nếu không phải ngày — dùng chung router báo cáo


def _period(week_key: str, span: int | None) -> dict:
    """Kỳ báo cáo; không truyền span → lấy số tuần gộp đã lưu trong báo cáo (mặc định 1)."""
    if span is None:
        ensure_schema()
        with session_scope() as db:
            span = db.execute(text("SELECT payload->>'span_weeks' FROM weekly_report WHERE week_key = :k"),
                              {"k": week_key}).scalar()
    return weekly_period.period(week_key, span or 1)


# ── Tài liệu đính kèm ──
@router.get("/attachments", response_model=list[WeeklyAttachment])
def list_attachments(week_key: str):
    return att_svc.list_attachments(_wk(week_key))


@router.post("/attachments", response_model=WeeklyAttachment)
def upload_attachment(week_key: str, file: UploadFile = File(...), kind: str | None = Form(None),
                      username: str = Depends(_edit)):
    """Tải PDF/DOCX lên → lưu file + trích chữ cho AI (file scan không có chữ vẫn lưu)."""
    return att_svc.upload(_wk(week_key), file, (kind or "").strip() or None, username)


@router.patch("/attachments/{att_id}", response_model=WeeklyAttachment, dependencies=[Depends(_edit)])
def patch_attachment(week_key: str, att_id: int, body: AttachmentPatch):
    updated = att_svc.update(_wk(week_key), att_id, body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(404, _NOT_FOUND)
    return updated


@router.delete("/attachments/{att_id}", dependencies=[Depends(_edit)])
def delete_attachment(week_key: str, att_id: int) -> dict:
    if not att_svc.delete(_wk(week_key), att_id):
        raise HTTPException(404, _NOT_FOUND)
    return {"deleted": att_id}


@router.get("/attachments/{att_id}/file")
def download_attachment(week_key: str, att_id: int):
    return att_svc.serve_file(_wk(week_key), att_id)


@router.get("/attachments/{att_id}/text")
def attachment_text(week_key: str, att_id: int) -> dict:
    att = att_svc.get_attachment(_wk(week_key), att_id, with_text=True)
    if not att:
        raise HTTPException(404, _NOT_FOUND)
    return {"text": att["text_content"]}


@router.post("/attachments/{att_id}/summarize", dependencies=[Depends(_edit)])
def summarize_attachment(week_key: str, att_id: int) -> dict:
    """AI tóm tắt số liệu chính của tài liệu → lưu vào `summary`."""
    wk = _wk(week_key)
    if not att_svc.get_attachment(wk, att_id):
        raise HTTPException(404, _NOT_FOUND)
    from app.services import llm, weekly_ai
    try:
        result = weekly_ai.summarize_attachment(wk, att_id)
    except (llm.LLMNotConfigured, ValueError) as exc:  # ValueError: file không có lớp chữ (bản scan)
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("AI tóm tắt đính kèm %s/%s lỗi", wk, att_id, exc_info=exc)
        raise HTTPException(502, "Lỗi tạo nội dung AI — kiểm tra cấu hình LLM hoặc log máy chủ.") from exc
    summary = result.get("summary") if isinstance(result, dict) else result
    summary = str(summary or "").strip()
    if summary:
        att_svc.set_summary(wk, att_id, summary)  # đã lưu sẵn thì nhật ký tự bỏ qua (không đổi gì)
    warnings = result.get("warnings", []) if isinstance(result, dict) else []
    return {"summary": summary, "warnings": warnings}


# ── Số liệu thị trường & tin trong kỳ ──
@router.get("/indicators", response_model=IndicatorsResponse)
def indicators(week_key: str, span: int | None = Query(None, ge=1, le=weekly_period.MAX_SPAN)):
    """DXY · WTI · Brent … (nguồn `market_feed`) — TB giá đóng cửa từng tuần của kỳ + cao/thấp."""
    per = _period(_wk(week_key), span)
    return {"indicators": weekly_market_feed.weekly_indicators(per["weeks"]), "period": per}


@router.get("/news", response_model=NewsResponse)
def news(week_key: str, span: int | None = Query(None, ge=1, le=weekly_period.MAX_SPAN)):
    """Các bài 'Giá cao su hôm nay' đăng trong kỳ (không kèm thân bài — AI đọc qua service)."""
    per = _period(_wk(week_key), span)
    feeds = [s for s in weekly_source_repo.list_sources(enabled_only=True)
             if s["mode"] == "vietnambiz" and s["url"]]
    source_url = feeds[0]["url"] if feeds else market_analysis.INDEX_URL
    weeks = per["weeks"]
    articles = weekly_news.fetch_period_articles(
        source_url, date.fromisoformat(weeks[1]["mon"]), date.fromisoformat(weeks[-1]["fri"]))
    return {"articles": [{k: a[k] for k in ("url", "title", "published")} for a in articles],
            "source_url": source_url}
