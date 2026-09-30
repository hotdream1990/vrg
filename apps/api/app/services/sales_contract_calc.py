"""Chuẩn hoá + quy đổi DÒNG CHI TIẾT của hợp đồng bán hàng (tách khỏi repo cho gọn file).

Mỗi dòng: chủng loại · số lượng (tấn) · QUY KHÔ (tấn) · đơn giá · loại tiền · tỷ giá.
Quy đổi doanh thu về BASE = ĐỒNG, đúng quy ước đang dùng ở biểu tiêu thụ cũ:
  - `ccy = VND`  → đơn giá tính bằng TRIỆU ĐỒNG/TẤN  → doanh thu = qty × price × 1.000.000
  - `ccy` khác   → đơn giá tính bằng NGOẠI TỆ/TẤN     → doanh thu = qty × price × tỷ giá
Thiếu tỷ giá thì trả None (KHÔNG đoán) — số liệu ngày khác không được dùng thay, xem nguyên tắc
"không suy diễn dữ liệu" của dự án.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from app.core.market_meta import DRY_REQUIRED_GRADES, SALE_CURRENCIES, UNIT_GRADES
from app.services import sales_contract_line_dates as line_dates

TRIEU = 1_000_000
_CCY = frozenset(SALE_CURRENCIES)
_GRADES = frozenset(UNIT_GRADES)


def _num(v) -> float | None:
    """Số hợp lệ hoặc None. NaN/Infinity bị loại: `nan <= 0` là False nên lọt mọi kiểm tra
    lớn-hơn-0, rồi `json.dumps` sinh `NaN` mà jsonb của Postgres từ chối → lỗi 500."""
    try:
        f = None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
    return None if f is not None and not math.isfinite(f) else f


def clean_lines(lines, require_fx: bool = True, *, dated: bool = False,
                sign_date: date | None = None, delivered_at: date | None = None,
                expiry: date | None = None) -> list[dict[str, Any]]:
    """Lọc/kiểm tra danh sách dòng chi tiết. Raise ValueError với thông báo tiếng Việt.

    `dated` — dòng của HỢP ĐỒNG được mang NGÀY HIỆU LỰC (`from_date`, xem `line_dates.parse`),
    kiểm theo `sign_date`, `expiry` (thời hạn) và `delivered_at` (hợp đồng giao 1 lần đã giao).
    Đợt giao KHÔNG có: ngày của đợt chính là ngày giao, nên khoá này bị bỏ đi (lần chuyển giao 1
    lần → nhiều lần sao dòng của hợp đồng xuống đợt đầu tiên).

    Bán LATEX và 2 loại mủ nguyên liệu mới thì BẮT BUỘC nhập quy khô mới cho lưu — đúng chốt Q4
    (30/07/2026), áp cho MỌI lần ghi: tạo mới lẫn sửa, hợp đồng lẫn đợt giao, đã giao hay chưa.
    Trước đây chỉ ép khi đã giao, nên phần cam kết của hợp đồng giao-nhiều-lần vào sổ bằng số mủ
    nước còn phần đã giao bằng số khô: hai vế của phép trừ "đã ký chưa giao" khác đơn vị tính nhau.

    `require_fx` — TỶ GIÁ chỉ bắt buộc khi bản ghi GHI NHẬN MỘT LẦN GIAO, tức là đã có NGÀY GIAO
    (chốt 22/08/2026). Lúc ký hợp đồng chưa ai biết tỷ giá ngày giao hàng, ép nhập từ lúc đó là
    bắt đơn vị bịa một con số rồi con số bịa ấy đi thẳng vào doanh thu. Chưa có tỷ giá thì doanh
    thu dòng đó là KHÔNG BIẾT (`line_revenue_vnd` trả None) — không phải 0.
    ⚠ KHÁC quy khô: quy khô ép ở mọi trạng thái vì nó là cách khai SẢN LƯỢNG, không phụ thuộc
    ngày giao.
    """
    out: list[dict[str, Any]] = []
    for i, ln in enumerate(lines if isinstance(lines, list) else [], start=1):
        if not isinstance(ln, dict):
            continue
        grade = str(ln.get("grade") or "").strip()[:80]
        qty = _num(ln.get("qty"))
        if not grade and qty is None:
            continue  # dòng trống người dùng chưa điền — bỏ qua, không báo lỗi
        if not grade:
            raise ValueError(f"Dòng {i}: thiếu chủng loại.")
        if grade not in _GRADES:
            raise ValueError(f"Dòng {i}: chủng loại “{grade}” không có trong danh mục.")
        if qty is None or qty <= 0:
            raise ValueError(f"Dòng {i} ({grade}): số lượng phải lớn hơn 0.")
        qty_dry = _num(ln.get("qty_dry"))
        # Quy khô CHỈ có nghĩa với mủ còn nước (latex + 2 loại nguyên liệu). Thành phẩm SVR/RSS/CSR
        # bán ra đã là hàng khô — số lượng chính là khối lượng khô. Nhận bừa ô này cho mọi chủng
        # loại thì chỉ tiêu "quy khô" trên báo cáo cộng cả số vô nghĩa mà nhìn không ra.
        if grade not in DRY_REQUIRED_GRADES and qty_dry is not None:
            raise ValueError(f"Dòng {i} ({grade}): chủng loại này không có quy khô — số lượng bán "
                             "đã là khối lượng khô. Chỉ latex và mủ nguyên liệu mới khai quy khô.")
        if grade in DRY_REQUIRED_GRADES and (qty_dry is None or qty_dry <= 0):
            raise ValueError(f"Dòng {i} ({grade}): bắt buộc nhập quy khô mới lưu được.")
        if qty_dry is not None and qty_dry > qty + 1e-9:
            raise ValueError(f"Dòng {i} ({grade}): quy khô ({qty_dry:g} tấn) không thể lớn hơn "
                             f"số lượng ({qty:g} tấn).")
        # Loại tiền SAI phải BÁO LỖI, không được lặng lẽ về VNĐ: "usd" viết thường sẽ thành VNĐ,
        # đơn giá 1.600 USD/tấn bị đọc thành 1.600 TRIỆU đồng/tấn — doanh thu sai ~38 lần.
        ccy = str(ln.get("ccy") or "VND").strip().upper()
        if ccy not in _CCY:
            raise ValueError(f"Dòng {i} ({grade}): loại tiền “{ln.get('ccy')}” không hợp lệ "
                             f"(chỉ nhận {', '.join(SALE_CURRENCIES)}).")
        fx = _num(ln.get("fx"))
        # Tỷ giá đã nhập thì phải là số dương — kiểm ở MỌI trạng thái: tỷ giá âm/0 làm doanh thu
        # âm hoặc bằng 0 mà nhìn bảng không thấy gì bất thường.
        if fx is not None and fx <= 0:
            raise ValueError(f"Dòng {i} ({grade}): tỷ giá phải lớn hơn 0.")
        if ccy != "VND" and require_fx and fx is None:
            raise ValueError(f"Dòng {i} ({grade}): đã có ngày giao mà bán bằng {ccy} thì phải "
                             "nhập tỷ giá quy ra VNĐ.")
        price = _num(ln.get("price"))
        if price is not None and price < 0:
            raise ValueError(f"Dòng {i} ({grade}): đơn giá không được âm.")
        row = {
            "grade": grade,
            "qty": qty,
            "qty_dry": qty_dry,
            "price": price,
            "ccy": ccy,
            "fx": fx,
        }
        # Chỉ ghi khoá khi CÓ ngày riêng: lưu lại một hợp đồng cũ không được đổi JSON của nó (nhật ký
        # sẽ báo "đổi dòng hàng" cho một lần lưu không đổi gì).
        if dated and (fd := line_dates.parse(ln, f"Dòng {i} ({grade})", sign_date, delivered_at,
                                             expiry)):
            row["from_date"] = fd
        out.append(row)
    if not out:
        raise ValueError("Hợp đồng phải có ít nhất một dòng chi tiết.")
    return out


def line_revenue_vnd(line: dict) -> float | None:
    """Doanh thu 1 dòng, quy về ĐỒNG. None khi thiếu dữ kiện (không đoán, không lấy ngày khác)."""
    qty, price = _num(line.get("qty")), _num(line.get("price"))
    if qty is None or price is None:
        return None
    if (line.get("ccy") or "VND") == "VND":
        return qty * price * TRIEU
    fx = _num(line.get("fx"))
    return None if fx is None else qty * price * fx


def _sum(lines, key: str) -> float:
    return sum(_num(ln.get(key)) or 0.0 for ln in lines or [])


def total_qty(lines) -> float:
    """Tổng sản lượng theo HỢP ĐỒNG (tấn) — với latex/mủ NL là **mủ nước**.

    Dùng cho cam kết & tiến độ giao của hợp đồng và cho THÀNH TIỀN (đơn giá là giá theo tấn nước).
    """
    return _sum(lines, "qty")


def sale_qty(line: dict) -> float:
    """Sản lượng TIÊU THỤ THỰC TẾ của 1 dòng (tấn) — chốt PA1 ngày 04/08/2026.

    Latex và 2 loại mủ nguyên liệu bán theo **mủ nước** nhưng sản lượng tiêu thụ thực tế là phần
    **quy khô** → báo cáo lấy quy khô. Chủng loại thành phẩm không có quy khô thì chính SL là số khô.
    ⚠ KHÁC `total_qty`: tiền vẫn tính trên mủ nước, chỉ SẢN LƯỢNG BÁO CÁO đổi sang quy khô.
    """
    dry = _num(line.get("qty_dry"))
    return dry if dry else (_num(line.get("qty")) or 0.0)


def total_sale_qty(lines) -> float:
    """Tổng sản lượng tiêu thụ thực tế (tấn) — xem `sale_qty`."""
    return sum(sale_qty(ln) for ln in lines or [])


def total_qty_dry(lines) -> float:
    """Tổng quy khô (tấn)."""
    return _sum(lines, "qty_dry")


def total_wet_qty(lines) -> float:
    """Tổng SL **MỦ NƯỚC** (tấn) — CHỈ cộng dòng có khai quy khô.

    Sản lượng báo cáo đã lấy quy khô (xem `sale_qty`) nên số cân thực tế của latex/mủ nguyên liệu
    sẽ biến mất khỏi báo cáo; cột này giữ nó lại. Dòng thành phẩm KHÔNG cộng vào: số nước của
    chúng chính là số khô, cộng vào thì cột này chỉ chép lại cột sản lượng.
    """
    return sum(_num(ln.get("qty")) or 0.0 for ln in lines or [] if _num(ln.get("qty_dry")))


def total_revenue_vnd(lines) -> float | None:
    """Tổng doanh thu (đồng). None nếu CÓ dòng không quy đổi được — để báo cáo biết là thiếu."""
    total, missing = 0.0, False
    for ln in lines or []:
        rev = line_revenue_vnd(ln)
        if rev is None:
            missing = True
        else:
            total += rev
    return None if missing else total
