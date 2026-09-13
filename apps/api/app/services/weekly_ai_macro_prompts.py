"""Hướng dẫn AI viết Phần IV (các yếu tố vĩ mô) Báo cáo tuần — logic 16.7 + báo cáo thật tuần 35–36.

Tiêu đề tiểu mục sửa được (lưu trong narrative.macro[].title) nên nhận diện chủ đề theo TỪ KHOÁ tiêu đề
trước (báo cáo cũ có thể xếp thứ tự khác), không khớp mới lùi về vị trí mặc định (`MACRO_TITLES`).
Mã mục nguồn tham khảo IV.n cũng tính theo chủ đề — xem `source_code_map`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_SUPPLY_WITH_DOCS = (
    "Cung – Cầu (số liệu ANRPC): dòng 1 = đoạn mở nêu trạng thái cán cân cao su thiên nhiên toàn cầu (thâm "
    "hụt/dư cung, khối lượng, năm/kỳ số liệu) theo báo cáo ANRPC; tiếp theo gạch '**Sản lượng sản xuất toàn "
    "cầu:** …' và '**Nhu cầu tiêu thụ toàn cầu:** …' (số dự báo + % so cùng kỳ YoY), dưới mỗi gạch 1–3 dòng "
    "chi tiết MỞ ĐẦU '> ' (quốc gia chủ lực, khối ANRPC/ngoài ANRPC, thời tiết/El Niño, Trung Quốc…); có thể "
    "thêm 1 dòng nhận định ngắn hạn (Short-term Market Outlook) của ANRPC. Logic: sản lượng tăng → nguồn cung "
    "dồi dào → giảm áp lực thiếu hụt → giá điều chỉnh xuống; thâm hụt kéo dài → bệ đỡ trung hạn. Mọi số CHỈ "
    "từ TÀI LIỆU ĐÍNH KÈM."
)
_SUPPLY_NO_DOCS = (
    "Cung – Cầu: kỳ này KHÔNG có tài liệu cung – cầu đính kèm → viết 1–2 câu định tính về mùa vụ, thời tiết "
    "và nguồn cung Đông Nam Á theo bài tin trong kỳ; KHÔNG dùng các gạch Sản lượng/Nhu cầu, KHÔNG nêu số "
    "cung – cầu, KHÔNG ghi 'theo báo cáo ANRPC' trừ khi chính bài tin trong kỳ trích ANRPC."
)
_GUIDES = {
    "energy": (
        "Thị trường năng lượng, địa chính trị & cao su tổng hợp (Butadien): 1–2 đoạn. Logic: giá dầu WTI/Brent "
        "tăng (vd rủi ro địa chính trị, nguồn cung dầu gián đoạn) → chi phí sản xuất Butadien tăng → cao su tổng "
        "hợp đắt hơn → nhà máy lốp xe ưu tiên cao su tự nhiên → hỗ trợ giá; dầu giảm → ngược lại. Nêu số dầu "
        "(TB tuần, % thay đổi) từ khối CHỈ SỐ; Butadien và sự kiện địa chính trị chỉ nêu khi tin/tài liệu có."),
    "finance": (
        "Tỷ giá và tài chính Nhật Bản: 1–2 đoạn. Logic: USD/JPY tăng (Yên yếu) → cao su OSE hấp dẫn nhà đầu tư "
        "nước ngoài → hỗ trợ sàn OSE; Yên phục hồi → áp lực lên OSE. DXY tăng (USD mạnh lên) hoặc FED duy trì "
        "lãi suất cao → chi phí nắm giữ hàng hóa đắt hơn → quỹ đầu tư rút bớt vốn khỏi hàng hóa kỳ hạn → áp lực "
        "bán chốt lời. Số USD/JPY từ khối TỶ GIÁ, DXY từ khối CHỈ SỐ; lãi suất FED/BoJ chỉ nêu khi tin/tài liệu "
        "có. Kỳ nhiều tuần thì so sánh diễn biến từng tuần."),
    "china": (
        "Dữ liệu kinh tế Trung Quốc & các yếu tố khác: 1 đoạn — PMI sản xuất, sản lượng ô tô – lốp xe, nhập "
        "khẩu, tồn kho Thượng Hải/Thanh Đảo (tồn kho tăng, PMI yếu → nhà máy lốp mua ít → áp lực giảm); yếu tố "
        "khác: EUDR, vĩ mô Việt Nam (tỷ giá USD/VND), thuế quan — CHỈ nêu yếu tố có trong bài tin/tài liệu của "
        "kỳ; kết bằng hàm ý cho giá."),
    "other": "Yếu tố vĩ mô khác theo đúng tiêu đề: 1 đoạn, chỉ dựa tin/tài liệu trong kỳ, kết bằng hàm ý cho giá.",
}
# Thứ tự xét = thứ tự ưu tiên khi tiêu đề chứa từ khoá của nhiều chủ đề. Khớp từ ĐẦU chữ ('yên' không
# khớp 'nguyên', 'butadien' vẫn khớp 'Butadiene').
_KEYWORDS = [("energy", ("năng lượng", "dầu", "butadien")), ("supply", ("cung", "cầu", "anrpc")),
             ("finance", ("tỷ giá", "yên", "dxy", "tài chính", "lãi suất")), ("china", ("trung quốc", "khác"))]
# Thứ tự mặc định = MACRO_TITLES; mã nguồn mặc định IV.1..IV.4 theo thứ tự này.
_DEFAULT_ORDER = ["energy", "supply", "finance", "china"]


def macro_titles(rep: dict[str, Any]) -> list[str]:
    """Tiêu đề IV hiện có của báo cáo; báo cáo chưa có → mặc định."""
    from app.services.weekly_report_service import MACRO_TITLES

    return [m.get("title") or "" for m in (rep.get("narrative") or {}).get("macro") or []] or list(MACRO_TITLES)


def macro_topic(title: str, idx: int) -> str:
    low = unicodedata.normalize("NFC", title or "").lower()
    topic = next((t for t, kws in _KEYWORDS if any(re.search(rf"(?<!\w){re.escape(k)}", low) for k in kws)), None)
    return topic or (_DEFAULT_ORDER[idx] if idx < len(_DEFAULT_ORDER) else "other")


def source_code(title: str, idx: int) -> str:
    """Mã mục nguồn tham khảo (theo bố cục mặc định) của tiểu mục IV thứ idx: chủ đề → IV.k."""
    topic = macro_topic(title, idx)
    pos = _DEFAULT_ORDER.index(topic) if topic in _DEFAULT_ORDER else idx
    return f"IV.{pos + 1}"


def source_code_map(titles: list[str]) -> dict[str, str]:
    """{mã nguồn IV.k → nhãn tiểu mục thật IV.n của báo cáo} — báo cáo xếp IV khác mặc định vẫn nhận đúng
    nguồn. Hai tiểu mục trùng chủ đề thì mã thuộc tiểu mục đầu."""
    out: dict[str, str] = {}
    for i, title in enumerate(titles):
        out.setdefault(source_code(title, i), f"IV.{i + 1}")
    return out


def macro_guide(title: str, idx: int, has_docs: bool) -> str:
    topic = macro_topic(title, idx)
    body = (_SUPPLY_WITH_DOCS if has_docs else _SUPPLY_NO_DOCS) if topic == "supply" else _GUIDES[topic]
    return (f"Tiểu mục IV.{idx + 1} — tiêu đề '{title}' (hệ thống tự in tiêu đề, KHÔNG viết lại). Viết bám "
            f"đúng tiêu đề. {body}")
