"""Router Trợ lý AI — hỏi đáp số liệu nội bộ + tư vấn giá sàn (tool-calling).

Gác bằng cap `assistant` (admin tự có; chuyên viên cần cấp; đơn vị thành viên không thấy).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_cap
from app.schemas.assistant import ChatRequest
from app.services import assistant_service, llm

logger = logging.getLogger("app.assistant")
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.post("/chat")
def chat(body: ChatRequest, username: str = Depends(require_cap("assistant"))) -> dict:
    """Một lượt hỏi–đáp (kèm lịch sử). Trả {answer, artifacts, sources}."""
    try:
        return assistant_service.chat([m.model_dump() for m in body.messages])
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Trợ lý AI lỗi", exc_info=exc)
        raise HTTPException(502, "Lỗi trợ lý AI — kiểm tra cấu hình LLM hoặc log máy chủ.") from exc
