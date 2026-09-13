"""Danh mục nguồn tham khảo MẶC ĐỊNH của Báo cáo tuần + nhãn tiếng Việt cho màn cấu hình.

Bám mục "I. SOURCE" của tài liệu "Logic viết Bản tin tuần 16.7". Chỉ dùng để seed khi bảng
`weekly_source` rỗng hoặc khi chuyên viên bấm "Khôi phục mặc định" — sau đó chuyên viên sửa thoải mái.
Investing.com chặn bot (HTTP 403) nên số liệu tự lấy đi qua mã `feed_symbol` (kiểu Yahoo; tự đổi sang CNBC — Yahoo chặn IP máy chủ prod);
link Investing vẫn giữ ở `url` để chuyên viên mở đối chiếu.
"""

from __future__ import annotations

from typing import Any

CATEGORIES: dict[str, str] = {
    "futures": "Giá cao su kỳ hạn",
    "physical": "Giá giao ngay & thu mua nội địa",
    "financial": "Tỷ giá, chỉ số tài chính & dầu thô",
    "news": "Tin tức hằng ngày",
    "macro": "Vĩ mô, cung – cầu & chính sách",
}

MODES: dict[str, str] = {
    "internal": "Dữ liệu hệ thống (như bản tin ngày)",
    "market_feed": "Tự lấy số liệu thị trường theo mã",
    "vietnambiz": "Tự đọc bài 'Giá cao su hôm nay' trong kỳ",
    "attachment": "Chuyên viên tải file lên — AI đọc",
    "manual": "Link tham khảo — chuyên viên tự đọc",
}

# IV.n theo bố cục Phần IV mặc định (`MACRO_TITLES`); báo cáo xếp IV khác thì mã được đổi theo chủ đề
# tiêu đề (`weekly_ai_macro_prompts.source_code_map`, web `macroSourceCode`).
SECTIONS: dict[str, str] = {
    "I": "I. Tóm tắt tuần trước",
    "II": "II. Diễn biến trong kỳ",
    "III.1": "III.1. Giá cao su kỳ hạn các sàn",
    "III.2": "III.2. Giá giao ngay (Physical)",
    "III.3": "III.3. Giá thu mua mủ nước nội địa",
    "IV.1": "IV.1. Năng lượng, địa chính trị & cao su tổng hợp",
    "IV.2": "IV.2. Cung – Cầu",
    "IV.3": "IV.3. Tỷ giá & tài chính Nhật Bản",
    "IV.4": "IV.4. Kinh tế Trung Quốc & yếu tố khác",
    "V": "V. Dự báo",
    "VI": "VI. Kết luận & khuyến nghị",
}

KINDS = ("anrpc", "other")  # loại tài liệu đính kèm

_VIETNAMBIZ_GUIDE = (
    "Bước 1: Truy cập đường link vào cuối ngày hoặc sáng thứ Bảy hằng tuần.\n"
    "Bước 2: Đọc các bài viết có tiêu đề dạng \"Giá cao su hôm nay ngày...:\".\n"
    "Bước 3: Trích xuất giá đóng cửa (mức cao nhất/thấp nhất) của các sàn: OSE (chủng loại RSS3), "
    "Shanghai (chủng loại RSS3) và SGX (chủng loại TSR20 và RSS3) được nêu trực tiếp trong nội dung "
    "bài viết. Lưu ý: Shanghai (RSS3) lấy dữ liệu giá kỳ hạn tháng 9, OSE lấy kỳ hạn tháng 12, SGX "
    "lấy kỳ hạn tháng tiếp theo. Khi so sánh phải dùng kỳ hạn đồng nhất giữa các bản tin.\n"
    "Bước 4: Tham khảo thêm thông tin thị trường (lý do tăng/giảm, cung – cầu, tỷ giá, giá dầu)."
)

_ANRPC_GUIDE = (
    "Số liệu cho IV.2 (Cung – Cầu): Mục 1 & 2 (World Supply & Demand) — lấy tổng sản lượng "
    "và tổng lượng tiêu thụ toàn cầu (% tăng/giảm so với cùng kỳ YoY) để chứng minh nguồn cung đang "
    "thừa hay thiếu. Mục Short-term Market Outlook — lấy nhận định ngắn của ANRPC về việc thị trường "
    "các tháng tới sẽ thâm hụt hay dư cung.\n"
    "Logic tỷ giá cho sàn SGX & MRE: Mục 5 (Strength of Thai Baht & Malaysian Ringgit) — xem Baht "
    "(THB) và Ringgit (MYR) mạnh lên hay yếu đi so với USD.\n"
    "Tải file PDF báo cáo vào mục Tài liệu đính kèm của báo cáo tuần để AI đọc và tóm tắt."
)


def _src(category: str, name: str, role: str, url: str, sections: list[str], mode: str,
         guide: str = "", feed_symbol: str | None = None) -> dict[str, Any]:
    return {"category": category, "name": name, "role": role, "url": url, "sections": sections,
            "guide": guide, "mode": mode, "feed_symbol": feed_symbol, "enabled": True}


DEFAULT_SOURCES: list[dict[str, Any]] = [
    _src("futures", "Giá cao su kỳ hạn thế giới (OSE · SHANGHAI · SGX · MRE)",
         "Lấy như Bản tin ngày", "", ["I", "II", "III.1"], "internal",
         "Giá thanh toán các sàn đã lưu trong hệ thống — cùng nguồn với Bản tin ngày."),
    _src("physical", "Giá giao ngay (RSS3, STR20, SMR20, Latex)",
         "Theo Bản tin ngày", "", ["III.2"], "internal",
         "Giá physical đã lưu trong hệ thống — cùng nguồn với Bản tin ngày."),
    _src("physical", "Giá thu mua mủ nước nội địa (VNĐ/độ TSC)",
         "Theo Bản tin ngày", "", ["III.3"], "internal",
         "Giá mủ nguyên liệu chuyên viên đã chốt — cùng nguồn với Bản tin ngày."),
    _src("financial", "Chỉ số DXY", "Đo lường sức mạnh đồng Đô la Mỹ",
         "https://vn.investing.com/indices/usdollar", ["IV.3"], "market_feed",
         "Đồng USD mạnh lên thường gây áp lực lên giá hàng hoá định giá bằng USD.", "DX-Y.NYB"),
    _src("financial", "Tỷ giá USD/JPY", "Đo lường sức mạnh đồng Yên Nhật",
         "https://vn.investing.com/currencies/usd-jpy", ["III.1", "IV.3"], "internal",
         "Tỷ giá hệ thống. Đồng Yên yếu đi (USD/JPY tăng) → cao su OSE rẻ hơn với người mua "
         "dùng ngoại tệ → có thể nâng đỡ giá sàn OSE."),
    _src("financial", "Giá dầu thô WTI", "Cơ sở tính toán chi phí cao su tổng hợp",
         "https://vn.investing.com/commodities/crude-oil", ["IV.1"], "market_feed",
         "Giá dầu tăng → chi phí cao su tổng hợp tăng → hỗ trợ giá cao su thiên nhiên.", "CL=F"),
    _src("financial", "Giá dầu Brent", "Chỉ báo năng lượng toàn cầu",
         "https://vn.investing.com/commodities/brent-oil", ["IV.1"], "market_feed", "", "BZ=F"),
    _src("financial", "Tỷ giá USD/THB & USD/MYR",
         "Sức mạnh đồng Baht Thái & Ringgit Malaysia", "", ["III.1"], "internal",
         "Tỷ giá hệ thống. Baht/Ringgit mạnh lên → giá cao su xuất khẩu quy USD đắt hơn → có thể "
         "nâng đỡ giá sàn SGX/MRE."),
    _src("news", "Vietnambiz — Giá cao su hôm nay", "Tin tức giá cao su hằng ngày",
         "https://vietnambiz.vn/gia-cao-su.html", ["I", "II", "III.1", "IV.1", "IV.4"],
         "vietnambiz", _VIETNAMBIZ_GUIDE),
    _src("macro", "Báo cáo ANRPC", "Hiệp hội các quốc gia sản xuất cao su thiên nhiên",
         "https://www.anrpc.org", ["IV.2", "III.1", "V"], "attachment", _ANRPC_GUIDE),
    _src("macro", "Bộ Công Thương — EUDR", "Chính sách EU chống phá rừng (EUDR)",
         "https://moit.gov.vn/", ["IV.4"], "manual",
         "Theo dõi tiến độ gia hạn hoặc hướng dẫn EUDR để cập nhật ảnh hưởng tâm lý giao dịch."),
    _src("macro", "Ngân hàng Nhà nước Việt Nam", "Điều hành tỷ giá USD/VND",
         "https://sbv.gov.vn/", ["IV.4"], "manual",
         "Theo dõi định hướng điều hành tỷ giá USD/VND; tuỳ thực tế, tìm theo từ khoá."),
    _src("macro", "CafeF", "Tin kinh tế vĩ mô Việt Nam", "https://cafef.vn/", ["IV.4"], "manual",
         "Tin vĩ mô Việt Nam — tuỳ thực tế, tìm theo từ khoá."),
    _src("macro", "Tinnhanhchungkhoan", "Tin kinh tế vĩ mô Việt Nam",
         "https://tinnhanhchungkhoan.vn/", ["IV.4"], "manual",
         "Tin vĩ mô Việt Nam — tuỳ thực tế, tìm theo từ khoá."),
]


def meta() -> dict[str, list[dict[str, str]]]:
    """Nhãn cho màn cấu hình: [{value, label}] giữ đúng thứ tự khai báo."""
    def items(d: dict[str, str]) -> list[dict[str, str]]:
        return [{"value": k, "label": v} for k, v in d.items()]
    return {"categories": items(CATEGORIES), "modes": items(MODES), "sections": items(SECTIONS)}
