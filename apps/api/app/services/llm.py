"""Cổng gọi LLM — đọc provider/key/model từ Cấu hình hệ thống (app_config), fallback .env.

Dùng SDK chính thức `anthropic`. Provider mặc định 'anthropic'; model mặc định Haiku 4.5
(nhanh + rẻ, hợp tóm tắt tin hằng ngày). Đổi provider/model/key ở Quản trị → Cấu hình → tab AI.
"""
from __future__ import annotations

from app.core.config import settings
from app.services import config_repo

DEFAULT_MODEL = "claude-haiku-4-5"


class LLMNotConfigured(RuntimeError):
    """Chưa cấu hình API key/provider — báo người dùng vào Cấu hình hệ thống đặt key."""


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Gọi 1 lượt LLM → trả về text. Hiện hỗ trợ provider 'anthropic'."""
    provider = (config_repo.get_value("LLM_PROVIDER", "anthropic") or "anthropic").lower()
    if provider != "anthropic":
        raise LLMNotConfigured(
            f"Provider '{provider}' chưa được hỗ trợ — hiện dùng Anthropic. "
            "Vào Cấu hình hệ thống → tab AI, đặt LLM_PROVIDER=anthropic."
        )
    api_key = config_repo.get_value("ANTHROPIC_API_KEY") or (settings.anthropic_api_key or None)
    if not api_key:
        raise LLMNotConfigured(
            "Chưa có Anthropic API Key. Vào Quản trị → Cấu hình hệ thống → tab AI để đặt khóa."
        )
    model = config_repo.get_value("ANTHROPIC_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
