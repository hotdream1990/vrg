"""Phân tích thông tin thị trường cao su bằng AI cho bản tin ngày (Mục IV.3).

Lấy bài 'Giá cao su hôm nay' MỚI NHẤT trên vietnambiz (nguồn tổng hợp Reuters/SCI99) →
AI viết 3 đoạn 'Các thông tin thị trường liên quan' đúng văn phong bản tin VRG.
Nguồn tin trích dẫn = SCI99 (nguồn gốc) + URL bài vietnambiz có ngày — khớp mẫu chuyên viên.
KHÔNG để AI bịa số liệu/sự kiện ngoài nguồn.
"""
from __future__ import annotations

import re

import httpx

from app.services import llm

INDEX_URL = "https://vietnambiz.vn/gia-cao-su.html"
# SCI99 (Sublime China Information) — nguồn gốc mà vietnambiz tổng hợp; mọi bản tin mẫu đều dẫn.
SCI99_SOURCE = "https://intl.sci99.com/annualreport/;ReportSublimeChinaInformation"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126 Safari/537.36")
_ARTICLE_RE = re.compile(r'href="(/gia-cao-su-hom-nay-[^"]+\.htm)"')
_END_MARKERS = ("Cùng chuyên mục", "Tin liên quan", "Đọc thêm", "Bài viết liên quan",
                "Theo dõi", "Từ khóa", "Bình luận")

_SYSTEM = (
    "Bạn là chuyên viên Ban Thị trường Kinh doanh của Tập đoàn Công nghiệp Cao su Việt Nam "
    "(VRG), viết mục 'Các thông tin thị trường liên quan' cho bản tin giá cao su hằng ngày. "
    "Văn phong: báo cáo nội bộ trang trọng, khách quan, tiếng Việt, câu phân tích theo lối "
    "nhân–quả và luôn quy về hàm ý cho giá cao su tự nhiên. "
    "TUYỆT ĐỐI không bịa số liệu, mốc thời gian hay sự kiện không có trong nguồn được cung cấp."
)

# Ví dụ văn phong (chỉ để AI học cách viết — KHÔNG sao chép nội dung/số liệu).
_STYLE = (
    "Giá cao su kỳ hạn tại Nhật Bản ngày 03/06 tiếp tục tăng, giá tăng nhờ nguồn cung bị thắt "
    "chặt tại châu Á do thời tiết cực đoan, đồng yên suy yếu và giá dầu đi lên trong bối cảnh "
    "căng thẳng địa chính trị gia tăng, qua đó hỗ trợ giá cao su tự nhiên."
)


def _clean_article(html: str) -> str:
    """Bóc thân bài (bỏ menu điều hướng đầu trang + khối 'tin liên quan' cuối)."""
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
    pos = text.find("Chia sẻ")  # nút chia sẻ nằm ngay trước sapo bài
    body = text[pos + len("Chia sẻ"):] if pos >= 0 else text
    for end in _END_MARKERS:
        i = body.find(end)
        if i > 300:
            body = body[:i]
            break
    return body[:3800].strip()


def _fetch() -> tuple[str, str]:
    """Trả (thân bài, url bài). Ưu tiên bài 'Giá cao su hôm nay' mới nhất; lỗi → trang index."""
    idx = httpx.get(INDEX_URL, headers={"User-Agent": _UA}, follow_redirects=True, timeout=20)
    idx.raise_for_status()
    m = _ARTICLE_RE.search(idx.text)
    if not m:
        return _clean_article(idx.text), INDEX_URL
    url = "https://vietnambiz.vn" + m.group(1)
    art = httpx.get(url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=20)
    art.raise_for_status()
    return _clean_article(art.text), url


def generate(n_paragraphs: int = 3) -> dict:
    """Lấy tin + AI viết n đoạn phân tích. Trả {paragraphs, source_urls}."""
    article, article_url = _fetch()
    user = (
        "VÍ DỤ VĂN PHONG (chỉ tham khảo cách viết, KHÔNG dùng lại số liệu/nội dung):\n"
        f"“{_STYLE}”\n\n"
        f"NGUỒN — bài 'Giá cao su hôm nay' mới nhất trên vietnambiz.vn:\n“““\n{article}\n”””\n\n"
        f"Hãy viết đúng {n_paragraphs} đoạn cho mục 'Các thông tin thị trường liên quan', mỗi đoạn 2–4 câu:\n"
        "- Đoạn 1: diễn biến giá cao su kỳ hạn tại Nhật Bản (sàn OSE) — tăng/giảm và LÝ DO chính "
        "(tỷ giá đồng yên, giá dầu, tâm lý nhà đầu tư, căng thẳng địa chính trị).\n"
        "- Đoạn 2: yếu tố cung–cầu (thời tiết tại Thái Lan/Indonesia/Malaysia, mùa thay lá và sản "
        "lượng khai thác ở Đông Nam Á, tồn kho) HOẶC diễn biến giá tại các thị trường khác trong "
        "nguồn (Thái Lan, sàn Thượng Hải/SHFE) — chọn nội dung CÓ trong nguồn.\n"
        "- Đoạn 3: giá dầu thô (Brent, Trung Đông) và/hoặc nhu cầu từ Trung Quốc – ngành lốp xe; "
        "kết lại bằng hàm ý cho giá cao su tự nhiên.\n"
        "Yêu cầu: dùng thuật ngữ ngành ('cao su kỳ hạn', 'cao su tự nhiên', 'cao su tổng hợp', "
        "'đồng yên suy yếu', 'nguồn cung thắt chặt'…). CHỈ dùng thông tin có trong NGUỒN — không "
        "thêm số liệu, mốc thời gian hay sự kiện không xuất hiện trong nguồn. "
        "TUYỆT ĐỐI KHÔNG viết các câu nhận xét về việc nguồn thiếu thông tin (không viết 'nguồn "
        "tin không đề cập', 'nguồn không nêu'…); nếu thiếu ý cho một đoạn, hãy tập trung vào thông "
        "tin CÓ trong nguồn và viết ngắn gọn, tự nhiên như văn bản chính thức. "
        "CHỈ trả về các đoạn văn, mỗi đoạn trên 1 dòng, KHÔNG đánh số, KHÔNG tiêu đề, KHÔNG markdown."
    )
    out = llm.complete(_SYSTEM, user, max_tokens=1000)
    paragraphs = [re.sub(r"^\s*[-•*\d.)]+\s*", "", p).strip() for p in out.split("\n") if p.strip()]
    paragraphs = [p for p in paragraphs if p]
    if n_paragraphs:
        paragraphs = paragraphs[:n_paragraphs]
    return {"paragraphs": paragraphs, "source_urls": [SCI99_SOURCE, article_url]}
