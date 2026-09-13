"""Chữ narrative → HTML an toàn cho PDF báo cáo tuần.

Quy ước (web hiểu giống hệt):
- Trong dòng: `**đậm**` → <b>, `*nghiêng*` → <i>, `***đậm nghiêng***`. LUÔN escape HTML trước
  (chữ do người dùng/AI gõ, không được chèn thẻ). Dấu * lẻ trong số/biểu thức ("2*3", "a * b")
  giữ nguyên: mở/đóng phải sát chữ, không dính chữ/số ở phía ngoài, không vượt dòng.
- Gạch đầu dòng: dòng thường = cấp 1 (•), `>` = cấp 2 (○), `>>` = cấp 3 (▪).
"""

from __future__ import annotations

import html
import re

_BOLD_ITALIC = re.compile(r"\*\*\*(?=[^\s*])([^\n*]+?)(?<=[^\s*])\*\*\*")
_BOLD = re.compile(r"\*\*(?=[^\s*])([^\n]+?)(?<=[^\s*])\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?=[^\s*])([^\n*]+?)(?<=[^\s*])\*(?![\w*])")


def fmt_inline(s: str | None) -> str:
    """Escape HTML rồi áp đậm/nghiêng."""
    t = html.escape(s or "")
    t = _BOLD_ITALIC.sub(r"<b><i>\1</i></b>", t)
    t = _BOLD.sub(r"<b>\1</b>", t)
    return _ITALIC.sub(r"<i>\1</i>", t)


def level_of(s: str) -> tuple[int, str]:
    """(cấp gạch, nội dung đã bỏ tiền tố) — đọc trên chuỗi THÔ (trước escape)."""
    t = s.strip()
    if t.startswith(">>"):
        return 3, t[2:].strip()
    if t.startswith(">"):
        return 2, t[1:].strip()
    if t.startswith("- "):  # AI/người dùng lỡ gõ '- ' ở cấp 1 → không in 2 dấu gạch
        t = t[2:].strip()
    return 1, t


def bullets(items: list[str]) -> str:
    """Danh sách lồng nhau đúng chuẩn HTML; cấp nhảy cóc (vd `>>` ngay đầu) bị hạ về cấp kế tiếp."""
    out: list[str] = []
    depth = 0
    for raw in items:
        if not raw or not raw.strip():
            continue
        lvl, text = level_of(raw)
        lvl = min(lvl, depth + 1)
        if lvl > depth:
            out.append("<ul class='blt'>" if depth == 0 else "<ul>")
        elif lvl < depth:
            out.append("</li></ul>" * (depth - lvl) + "</li>")
        else:
            out.append("</li>")
        out.append(f"<li>{fmt_inline(text)}")
        depth = lvl
    out.append("</li></ul>" * depth)
    return "".join(out)


def paras(items: list[str]) -> list[str]:
    """Mỗi dòng 1 đoạn văn (trả list để xếp trang theo từng đoạn)."""
    return [f"<p class='para'>{fmt_inline(s)}</p>" for s in items if s and s.strip()]


def paras_or_bullets(items: list[str]) -> list[str]:
    """Phần V: dòng `-` = gạch đầu dòng (kèm `>`/`>>` theo sau), còn lại = đoạn văn. GIỮ thứ tự."""
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if run:
            out.append(bullets(run))
            run.clear()

    for s in items:
        if not s or not s.strip():
            continue
        t = s.strip()
        if t.startswith("-"):
            run.append(t[1:].strip())
        elif t.startswith(">") and run:
            run.append(t)
        else:
            flush()
            out.extend(paras([t]))
    flush()
    return out


def chunk_notes(items: list[str]) -> list[list[str]]:
    """Gom [dòng cấp 1 + mọi dòng `>`/`>>` theo sau] thành từng cụm (mỗi sàn/nhóm 1 cụm)."""
    chunks: list[list[str]] = []
    for s in items:
        if not s or not s.strip():
            continue
        if level_of(s)[0] > 1 and chunks:
            chunks[-1].append(s)
        else:
            chunks.append([s])
    return chunks


def note_blocks(label_html: str, items: list[str]) -> list[str]:
    """Chia danh sách gạch thành nhiều block (mỗi cụm 1 block) để xếp trang dày, không cắt chữ.
    Block đầu kèm nhãn + cụm đầu (nhãn không mồ côi cuối trang)."""
    chunks = chunk_notes(items)
    if not chunks:
        return []
    return [label_html + bullets(chunks[0])] + [bullets(ch) for ch in chunks[1:]]
