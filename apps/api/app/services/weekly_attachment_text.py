"""Trích CHỮ từ tài liệu đính kèm Báo cáo tuần (PDF · DOCX) để AI đọc — hàm thuần, không DB.

PDF: `pdftotext -layout` (poppler — giữ bảng số); máy không có poppler mới lùi về pdfplumber/pypdf. DOCX: đọc thẳng
`word/document.xml` trong gói zip — mỗi đoạn (`</w:p>`) một dòng, bảng thì mỗi hàng một dòng với các ô
ngăn bằng " | ". File scan (ảnh) không có lớp chữ → trả chuỗi rỗng, KHÔNG đoán nội dung.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 200_000
MAX_PDF_PAGES = 150          # báo cáo ANRPC ~15 trang; trần chặn file dựng để làm treo máy
MAX_FALLBACK_PAGES = 40
PDFTOTEXT_TIMEOUT_S = 60
_MAX_DOCX_XML_BYTES = 10 * 1024 * 1024  # chặn "zip bomb": document.xml giải nén quá lớn thì bỏ
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def normalize_text(raw: str) -> str:
    """Gộp khoảng trắng trong dòng, bỏ dòng trống thừa (tối đa 1 dòng trống), cắt MAX_TEXT_CHARS."""
    raw = (raw or "").replace("\x00", "")  # Postgres text không nhận ký tự NUL (PDF lỗi font hay có)
    lines = [re.sub(r"[ \t\u00a0\u200b\f\v]+", " ", ln).strip() for ln in raw.splitlines()]
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return out[:MAX_TEXT_CHARS]


def _pdftotext(path: Path) -> str | None:
    """Chữ theo bố cục từ `pdftotext -layout` (poppler). Ưu tiên vì GIỮ ĐƯỢC BẢNG số: báo cáo ANRPC có
    bảng giá (Table 1) mà pdfplumber bỏ sót hẳn, pypdf thì đảo chữ ("xetaL") → AI đọc sai số.
    None = máy không có poppler (được lùi về thư viện Python); '' = có chạy nhưng không ra chữ/lỗi/quá giờ."""
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    try:
        # env tối giản: tiến trình con không thừa hưởng biến môi trường chứa khoá bí mật của API.
        res = subprocess.run([exe, "-layout", "-enc", "UTF-8", "-l", str(MAX_PDF_PAGES), str(path), "-"],
                             capture_output=True, timeout=PDFTOTEXT_TIMEOUT_S, check=False,
                             env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("[weekly-attachment] pdftotext lỗi/quá giờ với %s: %s", path.name, exc)
        return ""
    return res.stdout.decode("utf-8", errors="replace") if res.returncode == 0 else ""


def _page_count(path: Path) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[weekly-attachment] Không đếm được trang %s: %s", path.name, exc)
        return None


def _python_pdf_text(path: Path) -> str:
    """Dự phòng khi máy KHÔNG có poppler: pdfplumber rồi pypdf, chỉ MAX_FALLBACK_PAGES trang đầu
    (pdfminer thuần Python giữ GIL — PDF dựng hiểm có thể mất hàng chục giây mỗi trang)."""
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            text = "\n\n".join((p.extract_text() or "") for p in pdf.pages[:MAX_FALLBACK_PAGES])
        if text.strip():
            return text
    except Exception as exc:  # noqa: BLE001 - PDF hỏng/lạ → thử pypdf
        logger.warning("[weekly-attachment] pdfplumber lỗi với %s: %s", path.name, exc)
    try:
        from pypdf import PdfReader

        return "\n\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages[:MAX_FALLBACK_PAGES])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[weekly-attachment] pypdf lỗi với %s: %s", path.name, exc)
        return ""


def extract_pdf(path: Path) -> tuple[str, int | None]:
    """(chữ, số trang). Không mở được file → ('', None). Không có poppler mới dùng thư viện Python;
    poppler quá giờ/lỗi thì KHÔNG lùi (tránh treo CPU với PDF độc) — file coi như không trích được chữ."""
    text = _pdftotext(path)
    if text is None:
        text = _python_pdf_text(path)
    return normalize_text(text), _page_count(path)


def _para_text(p: ET.Element) -> str:
    parts: list[str] = []
    for el in p.iter():
        if el.tag == f"{_W}t" and el.text:
            parts.append(el.text)
        elif el.tag == f"{_W}tab":
            parts.append("\t")
        elif el.tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
    return "".join(parts)


def _block_lines(parent: ET.Element, out: list[str]) -> None:
    """Duyệt các khối con theo thứ tự tài liệu: đoạn · bảng · khối nội dung (sdt) lồng nhau."""
    for el in parent:
        if el.tag == f"{_W}p":
            out.append(_para_text(el))
        elif el.tag == f"{_W}tbl":
            for tr in el.findall(f"{_W}tr"):  # hàng trực tiếp (bảng lồng gộp vào chữ của ô)
                cells = []
                for tc in tr.findall(f"{_W}tc"):
                    cells.append(" ".join(_para_text(p).strip() for p in tc.iter(f"{_W}p")).strip())
                out.append(" | ".join(cells))
        elif el.tag in (f"{_W}sdt", f"{_W}sdtContent", f"{_W}body"):
            _block_lines(el, out)


def extract_docx(path: Path) -> str:
    """Chữ trong DOCX. File không phải DOCX hợp lệ → ''."""
    try:
        with zipfile.ZipFile(str(path)) as zf:
            info = zf.getinfo("word/document.xml")
            if info.file_size > _MAX_DOCX_XML_BYTES:
                logger.warning("[weekly-attachment] %s: document.xml quá lớn, bỏ qua", path.name)
                return ""
            root = ET.fromstring(zf.read(info))
        lines: list[str] = []
        body = root.find(f"{_W}body")
        _block_lines(body if body is not None else root, lines)  # đệ quy: khối lồng quá sâu → RecursionError
    except (Exception, RecursionError) as exc:  # noqa: BLE001 - zip hỏng/thiếu document.xml/XML lỗi
        logger.warning("[weekly-attachment] Không đọc được DOCX %s: %s", path.name, exc)
        return ""
    return normalize_text("\n".join(lines))


def extract(path: Path) -> tuple[str, int | None]:
    """Theo đuôi file → (chữ, số trang PDF | None)."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path), None
    return "", None


def guess_kind(filename: str, content: str) -> str:
    """'anrpc' nếu tên file hoặc phần đầu nội dung nhắc tới ANRPC, còn lại 'other'."""
    probe = f"{filename}\n{(content or '')[:20000]}"
    return "anrpc" if "anrpc" in probe.lower() else "other"
