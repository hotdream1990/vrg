"""Phân tích thông tin thị trường cao su bằng AI cho bản tin ngày (Section IV.3).

Lấy tin mới nhất từ vietnambiz (chuỗi "Giá cao su hôm nay") → AI viết các đoạn nhận định
tiếng Việt đúng văn phong bản tin. KHÔNG để AI bịa số liệu ngoài nguồn cung cấp.
"""
from __future__ import annotations

import re

import httpx

from app.services import llm

SOURCE_URL = "https://vietnambiz.vn/gia-cao-su.html"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126 Safari/537.36")

_SYSTEM = (
    "Bạn là chuyên viên phân tích thị trường cao su của Tập đoàn Công nghiệp Cao su Việt Nam "
    "(VRG). Viết phần 'Phân tích & nhận định' cho bản tin giá cao su hằng ngày: súc tích, khách "
    "quan, văn phong báo cáo nội bộ tiếng Việt. TUYỆT ĐỐI không bịa số liệu ngoài nguồn được cung cấp."
)


def _fetch_text() -> str:
    """Tải trang vietnambiz, bóc text bài 'Giá cao su hôm nay' (bỏ nav/boilerplate)."""
    r = httpx.get(SOURCE_URL, headers={"User-Agent": _UA}, follow_redirects=True, timeout=20)
    r.raise_for_status()
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    idx = text.find("Giá cao su hôm nay")
    return text[idx: idx + 3500] if idx >= 0 else text[:3500]


def generate(n_paragraphs: int = 3) -> dict:
    """Lấy tin + AI viết n đoạn phân tích. Trả {paragraphs, source_url}."""
    article = _fetch_text()
    user = (
        f"Dưới đây là thông tin thị trường cao su mới nhất từ vietnambiz.vn:\n\n{article}\n\n"
        f"Hãy viết {n_paragraphs} đoạn 'Phân tích & nhận định' ngắn (mỗi đoạn 2-4 câu) cho bản tin "
        "giá cao su hôm nay của VRG, đề cập: diễn biến giá các sàn (Nhật/OSE, Thượng Hải/SHFE, "
        "Thái Lan), yếu tố cung-cầu (thời tiết, sản lượng, giá dầu) và hàm ý cho giá bán. "
        "CHỈ trả về các đoạn văn, mỗi đoạn trên 1 dòng, không đánh số, không tiêu đề."
    )
    out = llm.complete(_SYSTEM, user, max_tokens=900)
    paragraphs = [p.strip(" -•\t") for p in out.split("\n") if p.strip()]
    return {"paragraphs": paragraphs[:n_paragraphs] if n_paragraphs else paragraphs,
            "source_url": SOURCE_URL}
