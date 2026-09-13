"""AI dựng nháp các phần viết Báo cáo tuần v2 (I, II, III nhận định, IV, V, VI) + tóm tắt đính kèm.

Ngữ cảnh = dữ liệu THẬT của kỳ (`weekly_ai_context`); prompt theo logic 16.7 (`weekly_ai_prompts`);
phần số III.1/III.2 dựng bằng code (`weekly_ai_compose`). Mỗi kết quả kèm cảnh báo: số AI viết không
đối chiếu được với ngữ cảnh + từ ngữ tuyệt đối (`weekly_number_check`). Chuyên viên soát & sửa sau.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services import llm, weekly_report_service
from app.services import weekly_ai_compose as compose
from app.services import weekly_ai_prompts as prompts
from app.services.weekly_ai_context import build_context
from app.services.weekly_number_check import absolute_words, unverified_numbers

logger = logging.getLogger(__name__)

MAX_TOKENS_ALL = 5000
MAX_TOKENS_SUMMARY = 2500
MAX_TOKENS_SECTION = {"exchange_notes": 1500, "movement": 1200, "forecast": 1200}
MAX_TOKENS_MACRO = 1400
MAX_TOKENS_DEFAULT = 900
SUMMARY_SOURCE_MAX_CHARS = 60_000

_BULLET_RE = re.compile(r"^\s*(?:•\s*|\*\s+)")          # '• ' / '* ' — không đụng '**đậm**'
_LABEL_RE = re.compile(r"^#{2,}\s*([IVX]+(?:\.\d+)?)\b")
# Kỳ nhiều tuần: AI hay dồn các tuần vào 1 dòng → tách trước 'Trong Tuần 35…' / 'Sang Tuần 36…'.
_WEEK_PARA_RE = re.compile(r"(?<=[.;!?])\s+(?=(?:Trong|Sang|Bước sang|Đến|Tới) Tuần \d)")


def _lines(out: str) -> list[str]:
    lines = [_BULLET_RE.sub("", s).strip() for s in (out or "").splitlines()]
    return [s for s in lines if s and s.strip("'\"") != prompts.SKIP_MARK]


def _strip_lead_dash(lines: list[str]) -> list[str]:
    """Bỏ tiền tố '-' thừa đầu dòng (giữ nguyên '>'/'>>' của gạch cấp 2/3). Dùng cho mọi phần TRỪ
    Phần V, nơi '-' là gạch đầu dòng có ý nghĩa (Hỗ trợ giá / Kìm hãm đà tăng)."""
    return [re.sub(r"^\s*-\s*", "", s) for s in lines]


def _parse_sections(out: str) -> dict[str, list[str]]:
    """Văn theo khung '### I' … '### VI' → {nhãn: [dòng]}."""
    buckets: dict[str, list[str]] = {}
    cur: str | None = None
    for line in (out or "").splitlines():
        m = _LABEL_RE.match(line.strip())
        if m:
            cur = m.group(1)
            buckets.setdefault(cur, [])
        elif cur is not None:
            buckets[cur] += _lines(line)
    return buckets


def _norm_title(s: str) -> str:
    return re.sub(r"[*\s:]+", " ", s or "").strip().lower()


def _drop_title_prefix(line: str, title: str) -> str:
    """'**1. Cung – Cầu …:** Thị trường …' → 'Thị trường …' (AI hay mở đoạn bằng chính tiêu đề in đậm)."""
    m = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", line)
    if m and m.group(2) and _norm_title(m.group(1)) == _norm_title(title):
        return m.group(2)
    return line


def _macro_bullets(lines: list[str], title: str) -> list[str]:
    """Bỏ '-' thừa + dòng/tiền tố AI lặp lại tiêu đề tiểu mục (tiêu đề đã có ở field title)."""
    return [_drop_title_prefix(s, title) for s in _strip_lead_dash(lines)
            if _norm_title(s) != _norm_title(title)]


def _complete(prompt: str, max_tokens: int, what: str) -> str:
    out = llm.complete(prompts.SYSTEM, prompt, max_tokens=max_tokens)
    logger.info("[weekly-ai] %s: prompt %d ký tự → trả %d ký tự", what, len(prompt), len(out or ""))
    if not (out or "").strip():
        raise RuntimeError(f"AI trả về rỗng ({what}) — thử lại hoặc tăng giới hạn token.")
    return out


def _forecast_lines(lines: list[str]) -> list[str]:
    """Phần V = 1 đoạn mở (dòng ngay trước gạch đầu tiên) + các gạch '- '. AI viết lan sang phần khác
    (hay gặp khi gọi riêng Phần V) thì chỉ giữ khung này."""
    first = next((i for i, s in enumerate(lines) if s.startswith("-")), None)
    if first is None:
        return lines[:1]
    opener = [re.sub(r"^[>\s]+", "", lines[first - 1])] if first > 0 else []
    return opener + [s for s in lines[first:] if s.startswith("-")]


def _finalize(field: str, lines: list[str], rep: dict[str, Any]) -> list[str]:
    """Hậu xử lý theo phần: III.1 ghép số từ bảng; III.2 câu mở + gạch cao/thấp; V giữ '-'."""
    if field == "exchange_notes":
        return compose.exchange_notes(rep, compose.parse_causes(lines))
    if field == "physical_notes":
        intro = [s for s in _strip_lead_dash(lines) if not s.startswith("**")][:2]
        return intro + compose.physical_lines(rep)
    if field == "forecast":
        return _forecast_lines(lines)
    if field == "movement" and len(rep.get("weeks") or []) > 2:
        lines = [p for s in lines for p in _WEEK_PARA_RE.split(s) if p.strip()]
    return _strip_lead_dash(lines)


def _checks(lines: list[str], ctx: str) -> tuple[list[str], list[str]]:
    return unverified_numbers(lines, ctx, locale="vi"), absolute_words(lines)


def assist(week_key: str, section: str) -> dict[str, Any]:
    """AI dựng nháp 1 phần. section ∈ summary_prev|movement|exchange_notes|physical_notes|latex_notes|
    forecast|conclusion|macro:<i> → {paragraphs, source_urls, warnings, absolute_words}."""
    label = prompts.label_of(section)
    rep = weekly_report_service.build_report(week_key)
    is_macro = section.startswith("macro:")
    titles = prompts.macro_titles(rep)
    idx = int(section.split(":", 1)[1]) if is_macro else 0
    if is_macro and idx >= len(titles):  # kiểm trước khi dựng ngữ cảnh (tốn ~8 giây mạng)
        raise ValueError(f"Báo cáo không có tiểu mục {label}")
    ctx, urls = build_context(week_key, rep=rep, section_keys=[label])
    tokens = MAX_TOKENS_MACRO if is_macro else MAX_TOKENS_SECTION.get(section, MAX_TOKENS_DEFAULT)
    out = _complete(prompts.section_prompt(ctx, rep, section), tokens, f"{week_key}/{section}")
    lines = _lines(out)
    if is_macro:
        paras = _macro_bullets(lines, titles[idx])
    else:
        paras = _finalize(section, lines, rep)
    warnings, absolute = _checks(paras, ctx)
    return {"paragraphs": paras, "source_urls": urls, "warnings": warnings, "absolute_words": absolute}


def assist_all(week_key: str) -> dict[str, Any]:
    """1 lượt AI sinh TẤT CẢ phần viết (nhất quán) → {sections, source_urls, warnings, absolute_words}.
    macro giữ tiêu đề hiện có của báo cáo; warnings/absolute_words chỉ gồm phần có cảnh báo."""
    rep = weekly_report_service.build_report(week_key)
    ctx, urls = build_context(week_key, rep=rep)
    out = _complete(prompts.all_prompt(ctx, rep), MAX_TOKENS_ALL, f"{week_key}/toàn bộ")
    parsed = _parse_sections(out)
    if not parsed:
        raise RuntimeError("AI trả về sai khung nhãn '### …' — thử lại.")
    sections: dict[str, Any] = {field: _finalize(field, parsed.get(label, []), rep)
                                for field, label in prompts.FIELD_LABEL.items()}
    sections["macro"] = [{"title": title, "bullets": _macro_bullets(parsed.get(f"IV.{i + 1}", []), title)}
                         for i, title in enumerate(prompts.macro_titles(rep))]
    warnings: dict[str, list[str]] = {}
    absolute: dict[str, list[str]] = {}
    checked = [(f, sections[f]) for f in prompts.FIELD_LABEL]
    checked += [(f"macro:{i}", m["bullets"]) for i, m in enumerate(sections["macro"])]
    for key, lines in checked:
        w, a = _checks(lines, ctx)
        if w:
            warnings[key] = w
        if a:
            absolute[key] = a
    return {"sections": sections, "source_urls": urls, "warnings": warnings, "absolute_words": absolute}


def summarize_attachment(week_key: str, att_id: int) -> dict[str, Any]:
    """AI trích số liệu chính của 1 tài liệu đính kèm → lưu `summary` → {summary, warnings}."""
    from app.services import weekly_attachment_service as att_svc

    att = att_svc.get_attachment(week_key, att_id, with_text=True)
    if not att:
        raise LookupError("Không tìm thấy tài liệu đính kèm.")
    text = (att.get("text_content") or "").strip()
    if not text:
        raise ValueError("Tài liệu không trích được chữ (có thể là bản scan) — hãy tự nhập tóm tắt.")
    src = text[:SUMMARY_SOURCE_MAX_CHARS]
    out = _complete(prompts.summary_prompt(att["filename"], att["kind"], src), MAX_TOKENS_SUMMARY,
                    f"{week_key}/đính kèm #{att_id}")
    lines = [s.rstrip() for s in out.splitlines() if s.strip()]
    summary = "\n".join(lines)
    att_svc.set_summary(week_key, att_id, summary)
    # Tóm tắt có thể giữ số kiểu Anh của tài liệu → đọc cả 2 kiểu (văn báo cáo chỉ đọc kiểu Việt).
    return {"summary": summary, "warnings": unverified_numbers(lines, src, locale="any")}
