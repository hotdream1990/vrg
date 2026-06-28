"""Cổng gọi LLM — đọc provider/key/model từ Cấu hình hệ thống (app_config), fallback .env.

Tạm thời dùng OpenAI (provider mặc định 'openai'). Vẫn giữ nhánh Anthropic để bật lại sau.
Đổi provider/model/key ở Quản trị → Cấu hình → tab AI.
"""
from __future__ import annotations

from app.core.config import settings
from app.services import config_repo

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"


class LLMNotConfigured(RuntimeError):
    """Chưa cấu hình API key/provider — báo người dùng vào Cấu hình hệ thống đặt key."""


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    """Gọi 1 lượt LLM → trả về text. Provider lấy từ cấu hình (mặc định 'openai')."""
    provider = (config_repo.get_value("LLM_PROVIDER", "openai") or "openai").lower()
    if provider == "openai":
        return _openai(system, user, max_tokens)
    if provider == "anthropic":
        return _anthropic(system, user, max_tokens)
    raise LLMNotConfigured(
        f"Provider '{provider}' chưa được hỗ trợ — hiện dùng OpenAI. "
        "Vào Cấu hình hệ thống → tab AI, đặt LLM_PROVIDER=openai."
    )


def _openai(system: str, user: str, max_tokens: int) -> str:
    api_key = config_repo.get_value("OPENAI_API_KEY") or (settings.openai_api_key or None)
    if not api_key:
        raise LLMNotConfigured(
            "Chưa có OpenAI API Key. Vào Quản trị → Cấu hình hệ thống → tab AI để đặt khóa."
        )
    model = config_repo.get_value("OPENAI_MODEL", DEFAULT_OPENAI_MODEL) or DEFAULT_OPENAI_MODEL
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_completion_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    api_key = config_repo.get_value("ANTHROPIC_API_KEY") or (settings.anthropic_api_key or None)
    if not api_key:
        raise LLMNotConfigured(
            "Chưa có Anthropic API Key. Vào Quản trị → Cấu hình hệ thống → tab AI để đặt khóa."
        )
    model = config_repo.get_value("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL) or DEFAULT_ANTHROPIC_MODEL
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
