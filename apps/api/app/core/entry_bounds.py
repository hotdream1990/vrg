"""Biên hợp lệ của các ô NHẬP TAY — bản Python của `apps/web/src/lib/entry-bounds.ts`.

CHỈ ĐỂ CẢNH BÁO, không chặn lưu: giá thị trường có thể vượt biên thật, chặn cứng là chặn nghiệp vụ.
Web dùng bộ biên này lúc ĐANG NHẬP; bản này dùng để rà lại SỐ ĐÃ LƯU rồi nhắc trên bảng việc của
đơn vị (`member_data_check`) — cảnh báo chỉ hiện trong form thì nhập xong đóng form là không ai
thấy nữa, mà lỗi nhầm đơn vị tính vẫn nằm im trong báo cáo.

⚠ HAI NƠI PHẢI KHỚP NHAU: sửa số ở đây thì sửa luôn `entry-bounds.ts`
(`test_entry_bounds_match_web` so từng con số và sẽ đỏ nếu lệch).
"""

from __future__ import annotations

from typing import NamedTuple


class Bound(NamedTuple):
    """Khoảng giá trị thường gặp của một ô. `lo`/`hi` = None → không chặn phía đó."""

    lo: float | None
    hi: float | None
    unit: str


# ── Sản lượng (tấn) ──────────────────────────────────────────────────────────────────────
TONNES_DAILY = Bound(0, 1_000, "tấn")        # phát sinh trong MỘT ngày của MỘT đơn vị
TONNES_STOCK = Bound(0, 20_000, "tấn")       # tồn kho = số tích luỹ tại thời điểm
TONNES_CONTRACT = Bound(0, 10_000, "tấn")    # một dòng hợp đồng/đợt giao (cả lô)
TONNES_YEAR = Bound(0, 50_000, "tấn")        # chỉ tiêu cả năm
TONNES_CARRY = Bound(0, 20_000, "tấn")       # sản lượng chuyển từ năm trước

# ── Đơn giá — KHOÁ THEO LOẠI TIỀN: cùng lô mủ, giá VND ≈ 50 còn USD ≈ 1.900 (chênh 40 lần) ──
PRICE_VND = Bound(10, 150, "triệu đ/tấn")
PRICE_USD = Bound(500, 8_000, "USD/tấn")

# ── Tỷ giá & đơn giá mủ nguyên liệu ──────────────────────────────────────────────────────
FX_USD_VND = Bound(15_000, 40_000, "VND")
PRICE_LATEX = Bound(100, 1_500, "đồng/độ TSC")
PRICE_CUP = Bound(50, 1_500, "đồng/độ")
REVENUE_TY = Bound(0, 500, "tỷ đồng")

#: Chủng loại "gom" KHÔNG có mặt bằng giá cố định (mủ tạp, hàng lẻ, lô đặc biệt) — prod có dòng bán
#: thật ở 0,7–2,8 triệu đ/tấn. Áp biên đơn giá vào đây là kêu oan đều đặn, mà cảnh báo kêu oan thì
#: tới lúc sai thật người nhập cũng bỏ qua nốt. Web `priceBound` bỏ qua đúng 2 tên này.
NO_PRICE_BOUND_GRADES = frozenset({"Chủng loại khác", "Mủ ngoại lệ"})


def _vi(v: float) -> str:
    """Số kiểu Việt: chấm ngăn nghìn, phẩy thập phân (khớp `formatViNumber` của web)."""
    s = f"{v:,.10g}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s


def price_bound(ccy: str | None, grade: str | None = None) -> Bound | None:
    """Biên đơn giá theo LOẠI TIỀN của dòng. None = không có biên (không cảnh báo).

    Nội tệ đơn vị nước ngoài (LAK/KHR) có mặt bằng số hoàn toàn khác (1 USD ≈ 21.000 LAK) và chưa
    đủ dữ liệu thật để chốt biên → thà không cảnh báo còn hơn kêu oan mọi dòng.
    """
    if grade in NO_PRICE_BOUND_GRADES:
        return None
    if ccy == "USD":
        return PRICE_USD
    if ccy in ("LAK", "KHR"):
        return None
    return PRICE_VND


def bound_warning(v: float | None, b: Bound | None) -> str | None:
    """Lời cảnh báo cho một ô, hoặc None nếu số nằm trong khoảng — chữ y hệt bên web.

    Số 0 KHÔNG bị coi là "thấp hơn biên": mua 0 đồng là nghiệp vụ thật, và biên dưới sinh ra để bắt
    NHẦM ĐƠN VỊ TÍNH — mà nhầm đơn vị luôn lệch theo bội của 10, không bao giờ cho ra đúng 0.
    """
    if v is None or b is None:
        return None
    if b.hi is not None and v > b.hi:
        return (f"Vượt {_vi(b.hi)} {b.unit} — kiểm tra lại đơn vị tính "
                f"(ô này nhập theo {b.unit}).")
    if b.lo is not None and v != 0 and v < b.lo:
        return (f"Thấp hơn {_vi(b.lo)} {b.unit} — kiểm tra lại đơn vị tính "
                f"(ô này nhập theo {b.unit}).")
    return None


def fx_warning(ccy: str | None, fx: float | None) -> str | None:
    """Dòng chọn ngoại tệ mà bỏ trống tỷ giá → doanh thu dòng đó KHÔNG được tính."""
    ccy = ccy or "VND"
    if ccy == "VND" or (fx is not None and fx != 0):
        return None
    return f"Dòng chọn {ccy} nhưng chưa nhập tỷ giá — doanh thu dòng này sẽ không được tính."
