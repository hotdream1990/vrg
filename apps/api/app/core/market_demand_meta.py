"""Danh mục của phiếu Nhu cầu thị trường (theo trường, 17/09/2026) — nguồn chung cho router, luật
kiểm tra và luồng «Đề nghị sửa». Web giữ bản sao nhãn ở `apps/web/src/lib/market-demand-meta.ts`.

Chủng loại dùng lại `market_meta.UNIT_GRADES` (cùng danh mục với biểu Thu mua / Tiêu thụ) để nhu cầu
khớp tên với số liệu bán thật của đơn vị.
"""

from __future__ import annotations

from app.core.market_meta import UNIT_GRADES

GRADES: list[str] = list(UNIT_GRADES)

QTY_UNITS: dict[str, str] = {"ton": "tấn", "container": "container"}

# VND tính bằng TRIỆU đồng/tấn (cùng quy ước giá bán ở biểu Tiêu thụ) — không phải đồng/tấn.
CURRENCIES: dict[str, str] = {"VND": "triệu đồng/tấn", "USD": "USD/tấn"}

STATUS_OPEN, STATUS_SIGNED, STATUS_FAILED = "open", "signed", "failed"
STATUSES: dict[str, str] = {
    STATUS_OPEN: "Đang đàm phán",
    STATUS_SIGNED: "Đã ký hợp đồng",
    STATUS_FAILED: "Không thành",
}

# Trần đơn giá: bắt lỗi nhập nhầm đơn vị tính (gõ 40.000.000 đồng thay vì 40 triệu) — lỗi đã gặp
# nhiều lần ở biểu Tiêu thụ (xem đợt rà số liệu 10/08/2026).
PRICE_CAP: dict[str, float] = {"VND": 1000, "USD": 20000}
PRICE_CAP_MESSAGE: dict[str, str] = {
    "VND": "Đơn giá tính bằng TRIỆU đồng/tấn (vd 40 = 40 triệu) — tối đa 1.000.",
    "USD": "Đơn giá tính bằng USD/tấn (vd 2380 = 2.380 USD/tấn) — tối đa 20.000.",
}

CUSTOMER_MAX = 200
PLACE_MAX = 200
NOTE_MAX = 2000
CONTRACT_NO_MAX = 60

#: Ô NỘI DUNG — đổi bất kỳ ô nào thì phải qua cửa sổ nhập liệu (nội dung nhu cầu đã báo lên).
CONTENT_FIELDS: tuple[str, ...] = (
    "company", "as_of", "customer", "grade", "qty", "qty_unit", "price", "currency",
    "price_provisional", "delivery_place", "delivery_from", "delivery_to",
)

#: Ô THEO DÕI — kết quả đàm phán cập nhật về sau, MIỄN cửa sổ (chốt 17/09/2026).
TRACKING_FIELDS: tuple[str, ...] = ("status", "contract_no", "contract_date", "note")

#: Toàn bộ ô dữ liệu của một phiếu (dùng cho ghi DB, ảnh chụp đề nghị sửa, nhật ký).
DATA_FIELDS: tuple[str, ...] = (*CONTENT_FIELDS, *TRACKING_FIELDS)
