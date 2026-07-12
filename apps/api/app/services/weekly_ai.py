"""AI dựng nháp các phần viết cho Báo cáo tuần (I, II, III-nhận định, IV, V, VI).

Ngữ cảnh = số liệu tuần THẬT (bảng III + ĐỈNH/ĐÁY tuần từ data + tỷ giá TB tuần) + bài
'Giá cao su hôm nay' mới nhất vietnambiz. Prompt bám khung logic (Logic viết Bản tin tuần.docx)
và CHỐNG BỊA cứng: chỉ dùng số/sự kiện có trong ngữ cảnh/nguồn; yếu tố vĩ mô không có dữ liệu →
viết định tính, KHÔNG bịa số. User sửa lại sau.
"""

from __future__ import annotations

import re

from app.services import llm, market_analysis, weekly_report_service

_SYSTEM = (
    "Bạn là chuyên viên Ban Thị trường Kinh doanh của Tập đoàn Công nghiệp Cao su Việt Nam (VRG), "
    "viết Báo cáo phân tích thị trường cao su TUẦN. Văn phong: báo cáo nội bộ trang trọng, khách "
    "quan, tiếng Việt, phân tích nhân–quả và quy về hàm ý cho giá cao su tự nhiên."
)

# Luật chống bịa — chèn vào MỌI prompt.
_ANTIFAB = (
    "QUY TẮC CHỐNG BỊA (BẮT BUỘC): CHỈ dùng con số/sự kiện có trong NGỮ CẢNH SỐ LIỆU hoặc NGUỒN TIN "
    "bên dưới. Số 'Cao nhất/Thấp nhất tuần' phải lấy ĐÚNG từ mục 'Đỉnh/đáy tuần' trong ngữ cảnh (kèm "
    "ngày), TUYỆT ĐỐI không tự tính hay ước số khác. Các yếu tố vĩ mô (giá dầu Brent/WTI, chỉ số DXY, "
    "cán cân cung–cầu ANRPC/IRSG, quyết định lãi suất FED/BoJ, mốc thời hạn EUDR, sắc thuế…) CHỈ nêu "
    "khi NGUỒN TIN có đề cập; nếu KHÔNG có dữ liệu thì viết định tính dựa trên diễn biến giá/tỷ giá đã "
    "cho, KHÔNG bịa con số, mốc thời gian hay sự kiện. Không nêu lịch sự kiện tương lai cụ thể nếu "
    "nguồn không có. QUAN TRỌNG: khi thiếu dữ liệu cho một ý, viết định tính ngắn gọn, tự nhiên như "
    "văn bản chính thức; TUYỆT ĐỐI KHÔNG viết câu nhận xét về việc thiếu/không có dữ liệu (không dùng "
    "'nguồn không đề cập', 'không có dữ liệu', 'trong ngữ cảnh không có', 'chưa có số liệu'…)."
)

# section key → (mô tả yêu cầu, số đoạn cắt; 0 = giữ hết dòng)
_PROMPTS = {
    "summary_prev": ("Viết Phần I – TÓM TẮT TUẦN TRƯỚC: 1 đoạn tái hiện ngắn gọn bối cảnh & xu hướng "
                     "giá TUẦN LIỀN TRƯỚC để làm nền so sánh.", 1),
    "movement": ("Viết Phần II – DIỄN BIẾN TUẦN BÁO CÁO: 2 đoạn phác họa 'hình thái' chuyển động giá "
                 "cả tuần (tăng/giảm đầu–cuối tuần, phân hóa hay bứt phá) và nguyên nhân chính.", 2),
    "exchange_notes": (
        "Viết Nhận định bảng giá sàn quốc tế (III.1): TỪNG sàn 1 gạch chính kèm % thay đổi tuần. Góc "
        "phân tích gợi ý (chỉ khẳng định khi nguồn có): OSE gắn đồng Yên (USD/JPY) & giá dầu; SHANGHAI "
        "gắn tồn kho Thanh Đảo & nhà máy lốp xe; SGX/MRE gắn nguồn cung găng tay & cấu trúc chi phí sàn "
        "Malaysia. Dưới mỗi sàn thêm 2 gạch phụ MỞ ĐẦU bằng '>': '> Cao nhất tuần: {số} ({ngày})' và "
        "'> Thấp nhất tuần: {số} ({ngày})' — lấy ĐÚNG số từ mục Đỉnh/đáy tuần trong ngữ cảnh.", 0),
    "physical_notes": ("Viết Nhận định bảng giá giao ngay (III.2): 1 đoạn về mức hạ nhiệt/tăng & biên "
                       "độ % của RSS3/STR20/SMR20/Latex; có thể dẫn đỉnh/đáy tuần (đúng số ngữ cảnh) và "
                       "diễn biến nguồn cung mủ Đông Nam Á nếu nguồn đề cập.", 1),
    "latex_notes": ("Viết Nhận định giá thu mua mủ nước nội địa (III.3): 1 đoạn so sánh biên độ giá "
                    "tuần này với tuần trước và lý do (cầu nội địa, nguồn cung cục bộ).", 1),
    "forecast": ("Viết Phần V – DỰ BÁO XU HƯỚNG TUẦN TIẾP THEO: 1 đoạn mở + 2 gạch MỞ ĐẦU bằng '-': "
                 "'- Xu hướng chủ đạo: …' (dựa quán tính kỹ thuật các phiên cuối tuần) và '- Tiêu điểm "
                 "quan sát: …' (định hướng theo dõi sự kiện tài chính tuần tới, dữ liệu PMI lốp xe "
                 "Trung Quốc — nêu định hướng, KHÔNG bịa lịch/số cụ thể).", 0),
    "conclusion": ("Viết Phần VI – KẾT LUẬN VÀ KHUYẾN NGHỊ: 1 đoạn chốt trạng thái thị trường và "
                   "khuyến nghị hành động quản trị rủi ro cho các đơn vị thành viên (thận trọng/theo "
                   "dõi ngưỡng hỗ trợ, hoặc tận dụng nhịp điều chỉnh cân đối nguồn hàng).", 1),
}
_MACRO_PROMPTS = [
    "Viết tiểu mục IV.1 – Thị trường Năng lượng và giá cao su tổng hợp (Butadien): 2 gạch ('Giá dầu "
    "thô', 'Giá cao su tổng hợp (Butadien)'). Chỉ nêu số giá dầu/Butadien nếu nguồn có; liên kết "
    "nhân–quả dầu→chi phí cao su tổng hợp→giá cao su tự nhiên.",
    "Viết tiểu mục IV.2 – Cung – Cầu cơ bản: 2 gạch ('Nguồn cung mùa vụ', 'Yếu tố thời tiết'). Nếu "
    "nguồn có số cán cân cung–cầu ANRPC (vd thâm hụt toàn cầu) thì trích để nói 'bệ đỡ trung hạn'; "
    "KHÔNG có thì viết định tính về mùa vụ/thời tiết Đông Nam Á.",
    "Viết tiểu mục IV.3 – Tỷ giá và Tài chính Nhật Bản: 1 gạch ('Đồng Yên và Chỉ số Nikkei'). Dùng "
    "USD/JPY trong ngữ cảnh; chỉ nêu Nikkei/BoJ/FED nếu nguồn có.",
    "Viết tiểu mục IV.4 – Các thông tin kinh tế Trung Quốc và dữ liệu khác: 1–2 gạch ('Thị trường "
    "tiêu thụ' và nếu nguồn có: tin chính sách/địa chính trị như thuế quan, EUDR).",
]


def _stats_lines(stats: dict, key: str, title: str) -> list[str]:
    out = []
    d = stats.get(key, {})
    if d:
        out.append(title)
        for k, s in d.items():
            out.append(f"- {k}: Cao nhất {s['high']} ({s['high_date']}); Thấp nhất {s['low']} ({s['low_date']})")
    return out


def _context(week_key: str) -> str:
    rep = weekly_report_service.build_report(week_key)
    stats = weekly_report_service.weekly_stats(week_key)
    lines = [
        f"BÁO CÁO TUẦN {rep['week_no']}/{rep['year']} ({rep['date_range']}). "
        f"Cột: {rep['prev_col_label']} → {rep['curr_col_label']}.",
        "Giá sàn quốc tế (TB tuần USD/tấn, prev → curr [+/- ; %]):",
    ]
    for r in rep["exchange_rows"]:
        lines.append(f"- {r['exchange']} {r['grade']}: {r['prev']} → {r['curr']} "
                     f"({r['change_abs']}; {r['change_pct']}%)")
    lines += _stats_lines(stats, "exchange", "Đỉnh/đáy tuần theo sàn (USD/tấn) — DÙNG ĐÚNG cho Cao/Thấp nhất tuần:")
    lines.append("Giá giao ngay (TB tuần USD/tấn):")
    for r in rep["physical_rows"]:
        lines.append(f"- {r['grade']}: {r['prev']} → {r['curr']} ({r['change_abs']}; {r['change_pct']}%)")
    lines += _stats_lines(stats, "physical", "Đỉnh/đáy tuần giao ngay (USD/tấn):")
    lines.append(f"Mủ nước nội địa (VNĐ/độ TSC): {rep['latex_prev']} → {rep['latex_curr']} "
                 f"(biến động {rep['latex_change']}).")
    if stats.get("fx"):
        lines.append("Tỷ giá TB tuần: " + ", ".join(f"{p}={v}" for p, v in stats["fx"].items()) + ".")
    return "\n".join(lines)


def _split(out: str, limit: int = 0) -> list[str]:
    paras = [re.sub(r"^\s*[•*]\s*", "", p).strip() for p in out.split("\n") if p.strip()]
    paras = [p for p in paras if p]
    return paras[:limit] if limit else paras


def _strip_lead_dash(lines: list[str]) -> list[str]:
    """Bỏ tiền tố '-' thừa đầu dòng (giữ nguyên '>' của gạch phụ). Dùng cho mọi phần TRỪ Phần V,
    nơi '-' là gạch đầu dòng có ý nghĩa (Xu hướng chủ đạo / Tiêu điểm quan sát)."""
    return [re.sub(r"^\s*-\s*", "", s) for s in lines]


def _prompt(ctx: str, article: str, ask: str) -> str:
    return (
        f"NGỮ CẢNH SỐ LIỆU TUẦN:\n{ctx}\n\n"
        f"NGUỒN TIN (bài 'Giá cao su hôm nay' mới nhất, vietnambiz.vn):\n\"\"\"\n{article}\n\"\"\"\n\n"
        f"{_ANTIFAB}\n\n{ask}"
    )


_ALL_TEMPLATE = (
    "### I\n### II\n### III.1\n### III.2\n### III.3\n"
    "### IV.1\n### IV.2\n### IV.3\n### IV.4\n### V\n### VI"
)
_ALL_GUIDE = (
    "Viết TOÀN BỘ các phần theo KHUNG NHÃN dưới. Giữ NGUYÊN các dòng nhãn '### ...', đặt nội dung ở "
    "các dòng ngay dưới mỗi nhãn (mỗi ý 1 dòng, KHÔNG đánh số, KHÔNG markdown).\n"
    + "\n".join(
        f"- {lbl}: {_PROMPTS[field][0]}"
        for lbl, field in [("I", "summary_prev"), ("II", "movement"), ("III.1", "exchange_notes"),
                           ("III.2", "physical_notes"), ("III.3", "latex_notes")]
    )
    + "\n- IV.1..IV.4: " + " | ".join(m.split(":", 1)[0] for m in _MACRO_PROMPTS)
    + " (theo hướng dẫn từng tiểu mục: dầu/Butadien; cung–cầu mùa vụ + ANRPC nếu nguồn có; đồng Yên/"
    "USD-JPY; tiêu thụ TQ + chính sách/EUDR nếu nguồn có).\n"
    f"- V: {_PROMPTS['forecast'][0]}\n- VI: {_PROMPTS['conclusion'][0]}\n"
    "YÊU CẦU NHẤT QUÁN: mọi phần kể CÙNG MỘT câu chuyện thị trường tuần — xu hướng ở II khớp số liệu "
    "bảng, nhận định III, phân tích IV, dự báo V, kết luận VI; không mâu thuẫn và không lặp y nguyên "
    "câu chữ giữa các phần."
)
_LABEL_FIELD = {
    "I": "summary_prev", "II": "movement", "III.1": "exchange_notes",
    "III.2": "physical_notes", "III.3": "latex_notes", "V": "forecast", "VI": "conclusion",
}


def _parse_sections(out: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    cur = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("###"):
            cur = s.lstrip("#").strip()
            buckets.setdefault(cur, [])
        elif cur is not None and s:
            buckets[cur].append(re.sub(r"^\s*[•*]\s*", "", s).strip())
    return buckets


def assist_all(week_key: str) -> dict:
    """1 lượt AI sinh TẤT CẢ phần viết (nhất quán + chống bịa). Trả {sections, source_urls}."""
    article, url = market_analysis._fetch()
    ask = f"{_ALL_GUIDE}\n\nKHUNG NHÃN:\n{_ALL_TEMPLATE}"
    out = llm.complete(_SYSTEM, _prompt(_context(week_key), article, ask), max_tokens=3200)
    parsed = _parse_sections(out)
    sections: dict = {
        field: (parsed.get(label, []) if field == "forecast" else _strip_lead_dash(parsed.get(label, [])))
        for label, field in _LABEL_FIELD.items()
    }
    sections["macro"] = [
        {"title": weekly_report_service._MACRO_TITLES[i],
         "bullets": _strip_lead_dash(parsed.get(f"IV.{i + 1}", []))}
        for i in range(4)
    ]
    return {"sections": sections, "source_urls": [url]}


def assist(week_key: str, section: str) -> dict:
    """AI dựng nháp 1 phần. section ∈ _PROMPTS hoặc 'macro:<idx>'. Trả {paragraphs, source_urls}."""
    article, url = market_analysis._fetch()
    if section.startswith("macro:"):
        ask, limit = _MACRO_PROMPTS[int(section.split(":", 1)[1])], 0
    else:
        ask, limit = _PROMPTS[section]
    ask += ("\nCHỈ trả về các đoạn/gạch đầu dòng, mỗi ý 1 dòng, KHÔNG đánh số, KHÔNG markdown, "
            "KHÔNG tiêu đề.")
    out = llm.complete(_SYSTEM, _prompt(_context(week_key), article, ask), max_tokens=900)
    paras = _split(out, limit)
    if section != "forecast":  # mọi phần trừ Phần V: bỏ tiền tố '-' thừa (Phần V dùng '-' làm gạch)
        paras = _strip_lead_dash(paras)
    return {"paragraphs": paras, "source_urls": [url]}
