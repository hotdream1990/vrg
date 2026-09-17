"""10 mục Nhu cầu thị trường CŨ không theo mẫu câu nào — soạn tay sau khi đọc từng câu.

Khoá = (ngày, đơn vị, số thứ tự mục trong ô chữ). Mỗi mục có thể thành NHIỀU phiếu vì mỗi phiếu chỉ
một chủng loại (chốt 17/09/2026). `flag` = điểm cần chủ dự án xem lại trong bảng đối chiếu.
Nguyên tắc: chỗ nào bản cũ không nói rõ thì để trống, ghi lại bằng lời ở `note` — không tự điền số.
"""
from __future__ import annotations

BR = "Công ty TNHH MTV Best Royal (K)"
DP = "Công ty Cổ phần Cao Su Đồng Phú"
TNSR_BUYER = "Công ty Tây Ninh Siêm Riệp PTCS"
CUP = "Mủ nguyên liệu nước chưa cán vắt (chén)"
LACE = "Mủ dây"
OTHER = "Chủng loại khác"
FLAG_RAW = "Bản cũ ghi «mủ nguyên liệu», không nói rõ loại → để «Chủng loại khác»"


def _i(customer: str, grade: str, note: str, **kw) -> dict:
    return {"customer": customer, "grade": grade, "note": note, "qty": None, "qty_unit": "ton",
            "price": None, "currency": "VND", "price_provisional": False, "delivery_place": "",
            "delivery_from": None, "delivery_to": None, **kw}


MANUAL: dict[tuple[str, str, int], list[dict]] = {
    ("2026-07-31", BR, 1): [_i(
        TNSR_BUYER, OTHER, "Mủ nguyên liệu khai thác 15/07–31/07/2026 · giá tính trên tấn quy khô",
        price=1735.46, currency="USD", delivery_from="2026-07-31", delivery_to="2026-07-31",
        flag=FLAG_RAW)],
    ("2026-07-31", BR, 2): [_i(
        TNSR_BUYER, OTHER, "Mủ nguyên liệu khai thác 01/08–31/08/2026 · giá tạm tính trên tấn quy khô"
        " · giao 2–3 đợt trong tháng 8 tùy tình hình khai thác",
        price=1735.46, currency="USD", price_provisional=True,
        delivery_from="2026-08-01", delivery_to="2026-08-31", flag=FLAG_RAW)],
    ("2026-08-14", BR, 1): [_i(
        TNSR_BUYER, OTHER, "Đợt 01 tháng 08/2026 · mủ nguyên liệu khai thác 01/08–14/08/2026"
        " · giá tính trên tấn quy khô",
        price=1735.46, currency="USD", delivery_from="2026-08-14", delivery_to="2026-08-14",
        flag=FLAG_RAW)],
    ("2026-08-31", BR, 1): [
        _i(TNSR_BUYER, CUP, "Đợt 02 tháng 08/2026 · mủ khai thác 15/08–31/08/2026 · giá tính trên tấn tươi",
           price=1009.50, currency="USD", delivery_from="2026-08-31", delivery_to="2026-08-31"),
        _i(TNSR_BUYER, LACE, "Đợt 02 tháng 08/2026 · mủ khai thác 15/08–31/08/2026 · giá tính trên tấn tươi",
           price=1135.19, currency="USD", delivery_from="2026-08-31", delivery_to="2026-08-31"),
    ],
    ("2026-09-01", BR, 1): [
        _i(TNSR_BUYER, CUP, "Mủ khai thác 01/09–30/09/2026 · giá tạm tính trên tấn tươi"
           " · giao 2–3 đợt trong tháng 9 tùy tình hình khai thác",
           price=1009.50, currency="USD", price_provisional=True,
           delivery_from="2026-09-01", delivery_to="2026-09-30"),
        _i(TNSR_BUYER, LACE, "Mủ khai thác 01/09–30/09/2026 · giá tạm tính trên tấn tươi"
           " · giao 2–3 đợt trong tháng 9 tùy tình hình khai thác",
           price=1135.19, currency="USD", price_provisional=True,
           delivery_from="2026-09-01", delivery_to="2026-09-30"),
    ],
    ("2026-08-12", DP, 1): [
        _i("RIOMI COMMERCIAL PTE. LTD.", "SVR 3L", "Giao ngay · thị trường Trung Quốc",
           qty=1, qty_unit="container"),
        _i("RIOMI COMMERCIAL PTE. LTD.", "SVR CV60", "Giao ngay · thị trường Trung Quốc",
           qty=1, qty_unit="container"),
    ],
    ("2026-08-17", DP, 1): [
        _i("Korean SPA Accessories (Pvt) Ltd.", g,
           "Tổng 200 tấn cho cả SVR 3L và SVR 10 — bản cũ không tách từng loại",
           flag="200 tấn ghi chung cho 2 loại → để trống số lượng từng dòng")
        for g in ("SVR 3L", "SVR 10 / CSR 10")
    ],
    ("2026-08-20", DP, 1): [_i(
        "J&G Trading Co., Ltd.", "SVR 10 / CSR 10", "Đóng gói 35 kg/bành, có pallet · 1 container 20ft",
        qty=21.16, delivery_place="FOB")],
    ("2026-08-20", DP, 2): [
        _i("LUU GIA AUSTRALIA PTY LTD", g,
           "Đóng gói normal poly, pallet quấn màng co · giao cuối tháng 9 – đầu tháng 10/2026",
           qty=n, qty_unit="container",
           flag="Thời gian giao ghi bằng chữ → để trống ô ngày, ghi trong Ghi chú")
        for g, n in (("SVR CV60", 3), ("SVR 3L", 2))
    ],
    ("2026-08-20", DP, 3): [_i(
        "CHEMICO Co., Ltd", "SVR 3L", "2 container mỗi tháng · hàng Tập đoàn",
        qty=2, qty_unit="container")],
}
