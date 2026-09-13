"""Router Bản tin biến động — sinh nhận định AI theo nhóm số liệu (bấm-tạo, không lưu)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.market_movement import AssessmentRequest, AssessmentResult
from app.services import llm, market_movement_service

logger = logging.getLogger("vrg.api")

router = APIRouter(prefix="/api/market-movement", tags=["market-movement"])


@router.post("/assessment", response_model=AssessmentResult)
def generate_assessment(payload: AssessmentRequest) -> AssessmentResult:
    """Nhận tóm tắt số liệu các nhóm → AI viết nhận định từng nhóm + tổng thể.

    Không lưu gì nên chỉ cần quyền xem màn (`market_movement`, gác ở main) — Lãnh đạo Tập đoàn
    cũng bấm được.
    """
    groups = [g.model_dump() for g in payload.groups]
    try:
        return AssessmentResult(**market_movement_service.generate(groups))
    except llm.LLMNotConfigured as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Lỗi sinh nhận định biến động", exc_info=exc)
        raise HTTPException(status_code=502, detail="AI không phản hồi hợp lệ — thử lại sau.") from exc
