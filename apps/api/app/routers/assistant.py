"""Router Trợ lý AI — hỏi đáp số liệu nội bộ + tư vấn giá sàn (tool-calling).

Gác bằng cap `assistant` (admin tự có; chuyên viên cần cấp; đơn vị thành viên không thấy).
Trong đó các GÓI KỸ NĂNG còn gác thêm theo quyền dữ liệu của chính tài khoản (vd gói "Đơn vị
thành viên" cần cap `unit_daily`) — xem `assistant_tools.PACKS`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_cap, user_caps
from app.schemas.assistant import ChatRequest
from app.services import assistant_service, llm

logger = logging.getLogger("app.assistant")
router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/packs")
def packs(username: str = Depends(require_cap("assistant"))) -> dict:
    """Các nhóm dữ liệu Trợ lý được phép tra cứu với tài khoản này (chip chọn trên UI)."""
    return {"packs": assistant_service.packs_for(user_caps(username))}


@router.post("/chat")
def chat(body: ChatRequest, username: str = Depends(require_cap("assistant"))) -> dict:
    """Một lượt hỏi–đáp (kèm lịch sử). Trả {answer, artifacts, sources}."""
    try:
        return assistant_service.chat([m.model_dump() for m in body.messages],
                                      user_caps(username), body.packs, body.advice,
                                      body.session_id, username)
    except llm.LLMNotConfigured as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Trợ lý AI lỗi", exc_info=exc)
        raise HTTPException(502, "Lỗi trợ lý AI — kiểm tra cấu hình LLM hoặc log máy chủ.") from exc
