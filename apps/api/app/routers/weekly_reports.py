"""Router Báo cáo phân tích thị trường TUẦN — bảng auto + narrative (AI/sửa tay) + xuất PDF."""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.core.security import require_editor
from app.schemas.weekly_report import (
    AiAssistAllResult,
    AiAssistRequest,
    AiAssistResult,
    WeeklyNarrative,
    WeeklyReport,
    WeeklyReportSummary,
)
from app.services import weekly_report_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/weekly-reports", tags=["weekly-reports"])
_editor = [Depends(require_editor)]


@router.get("", response_model=list[WeeklyReportSummary])
def list_reports():
    """Danh sách báo cáo tuần đã lưu (mới nhất trước)."""
    return weekly_report_service.list_reports()


@router.get("/resolve")
def resolve(date_str: str = Query(..., alias="date", description="YYYY-MM-DD bất kỳ trong tuần")) -> dict:
    """Đổi 1 ngày → khóa tuần (Thứ 2 ISO) để tạo/mở báo cáo."""
    try:
        d = date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    return {"week_key": weekly_report_service.week_key_for(d)}


@router.get("/{week_key}", response_model=WeeklyReport)
def get_report(week_key: str):
    """Dựng báo cáo tuần: bảng tự tính từ giá + narrative đã lưu (seed nếu trống)."""
    try:
        return weekly_report_service.build_report(week_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("Dựng báo cáo tuần %s lỗi", week_key, exc_info=exc)
        raise HTTPException(500, "Không dựng được báo cáo tuần — kiểm tra dữ liệu giá/log.") from exc


@router.put("/{week_key}", response_model=WeeklyReport, dependencies=_editor)
def save_report(week_key: str, narrative: WeeklyNarrative):
    """Lưu narrative (+ override biên độ III.3) → trả báo cáo dựng lại."""
    return weekly_report_service.save_narrative(week_key, narrative.model_dump())


@router.delete("/{week_key}", dependencies=_editor)
def delete_report(week_key: str) -> dict:
    if not weekly_report_service.delete_report(week_key):
        raise HTTPException(404, f"Không có báo cáo tuần {week_key}")
    return {"deleted": week_key}


@router.post("/{week_key}/ai-assist", response_model=AiAssistResult, dependencies=_editor)
def ai_assist(week_key: str, body: AiAssistRequest):
    """AI dựng nháp 1 phần viết (I/II/III-nhận định/IV/V/VI)."""
    from app.services import llm, weekly_ai
    try:
        return weekly_ai.assist(week_key, body.section)
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("AI báo cáo tuần %s/%s lỗi", week_key, body.section, exc_info=exc)
        raise HTTPException(502, "Lỗi tạo nội dung AI — kiểm tra cấu hình LLM hoặc log máy chủ.") from exc


@router.post("/{week_key}/ai-assist-all", response_model=AiAssistAllResult, dependencies=_editor)
def ai_assist_all(week_key: str):
    """AI dựng nháp TẤT CẢ phần viết trong 1 lượt (nhất quán với nhau)."""
    from app.services import llm, weekly_ai
    try:
        return weekly_ai.assist_all(week_key)
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("AI toàn bộ báo cáo tuần %s lỗi", week_key, exc_info=exc)
        raise HTTPException(502, "Lỗi tạo nội dung AI — kiểm tra cấu hình LLM hoặc log máy chủ.") from exc


@router.post("/{week_key}/generate-pdf")
def generate_pdf(week_key: str):
    """Xuất PDF báo cáo tuần từ bản ĐÃ LƯU.

    Không sửa số liệu nên chỉ cần quyền xem màn (`bulletin_weekly`, gác ở main) — người chỉ xem
    (vd Lãnh đạo Tập đoàn) cũng tải được PDF.
    """
    try:
        path = weekly_report_service.generate_pdf(week_key)
    except Exception as exc:  # noqa: BLE001
        logger.error("Xuất PDF tuần %s lỗi", week_key, exc_info=exc)
        raise HTTPException(500, "Không tạo được PDF báo cáo tuần — kiểm tra log.") from exc
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)
