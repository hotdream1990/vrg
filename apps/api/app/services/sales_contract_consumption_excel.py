"""Xuất Excel cho **Báo cáo tiêu thụ** — 2 sheet: TỔNG HỢP theo đơn vị + CHI TIẾT từng dòng bán.

Bảng tổng hợp chỉ trả lời "đơn vị này bao nhiêu tấn"; muốn soát "số đó gồm những gì, dòng nào làm
lệch" thì phải có bản ghi chi tiết để lọc/pivot ngay trong Excel. Sheet chi tiết vì thế mở tới mức
DÒNG BÁN (mỗi chủng loại của một lần giao là một dòng), kèm sẵn bộ lọc của Excel.

Cả hai sheet đọc CÙNG `sales_contract_report` với bảng trên web và cùng bộ lọc, nên tổng cột
"SL tính tiêu thụ" ở sheet chi tiết luôn khớp cột sản lượng của sheet tổng hợp — không thể lệch.
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import CONTRACT_TYPES, DRY_REQUIRED_GRADES, SALE_CHANNELS
from app.services import sales_contract_calc as calc, sales_contract_report, unit_analytics_excel
from app.services.unit_analytics_excel import Col

SUMMARY_COLS: list[Col] = [
    ("deliveries", "Số lần giao", "lần"),
    # Sản lượng tiêu thụ đã là QUY KHÔ (xem `sales_contract_calc.sale_qty`) → nói rõ ngay ở tiêu đề,
    # và cột kế bên trả lại số cân mủ nước của latex/mủ nguyên liệu thay vì lặp lại số khô.
    ("qty", "Sản lượng tiêu thụ", "tấn quy khô"),
    ("qty_wet", "Trong đó: SL mủ nước", "tấn"),
    ("qty_export", SALE_CHANNELS["export"], "tấn"),
    ("qty_domestic", SALE_CHANNELS["domestic"], "tấn"),
    ("qty_internal", SALE_CHANNELS["internal"], "tấn"),
    ("revenue_ty", "Doanh thu", "tỷ đồng"),
    ("remaining", "Đã ký HĐ chưa giao (cuối kỳ)", "tấn quy khô"),
]

#: Mỗi dòng = MỘT chủng loại của MỘT lần giao. Thứ tự cột theo mạch soát số: giao khi nào · của ai ·
#: theo hợp đồng nào · hàng gì · bao nhiêu · giá nào · chứng từ nào.
DETAIL_COLS: list[Col] = [
    ("delivered_at", "Ngày giao", ""),
    ("company", "Đơn vị", ""),
    ("contract_code", "Số hợp đồng", ""),
    ("batch_code", "Đợt giao", ""),
    ("customer", "Khách hàng", ""),
    ("contract_type", "Loại HĐ", ""),
    ("channel", "Hình thức tiêu thụ", ""),
    ("to_company", "Đơn vị nhận (nội bộ)", ""),
    ("grade", "Chủng loại", ""),
    # 3 cột sản lượng đứng cạnh nhau để đọc được ngay quan hệ nước → khô → số vào báo cáo.
    # Ô "Quy khô" TRỐNG ở dòng latex/mủ nguyên liệu = đơn vị chưa khai (lọc ra là thấy hết).
    ("qty_wet", "SL mủ nước", "tấn"),
    ("qty_dry", "Quy khô", "tấn"),
    ("qty", "SL tính tiêu thụ", "tấn quy khô"),
    ("price", "Đơn giá", "tr.đ/tấn nếu VNĐ · nguyên tệ/tấn nếu ngoại tệ"),
    ("ccy", "Loại tiền", ""),
    ("fx", "Tỷ giá → VNĐ", ""),
    ("amount", "Thành tiền", "nguyên tệ"),
    ("revenue_vnd", "Doanh thu", "đồng"),
    ("invoice_no", "Số hoá đơn", ""),
    ("payment_date", "Ngày thanh toán", ""),
    ("record_id", "Mã bản ghi", ""),
]


def _dong(v: float | None) -> float | None:
    return None if v is None else round(v, 2)


def _summary(rep: dict[str, Any]) -> tuple[list[dict], dict, bool]:
    """Dòng theo đơn vị + dòng Tổng cộng của sheet tổng hợp (đúng bảng đang hiện trên web)."""
    rows, totals = [], {k: 0.0 for k, _, _ in SUMMARY_COLS}
    missing_fx = False
    for name in sorted(set(rep["by_company"]) | set(rep["undelivered"])):
        c = rep["by_company"].get(name) or {}
        ch = c.get("by_channel") or {}
        rev = c.get("revenue")
        missing_fx = missing_fx or (name in rep["by_company"] and rev is None)
        row = {
            "label": name, "deliveries": c.get("deliveries", 0),
            "qty": c.get("qty", 0.0), "qty_wet": c.get("qty_wet", 0.0),
            "qty_export": ch.get("export", 0.0), "qty_domestic": ch.get("domestic", 0.0),
            "qty_internal": ch.get("internal", 0.0),
            # Doanh thu để TRỐNG khi thiếu tỷ giá — không quy về 0 để khỏi đọc nhầm là "bán không thu tiền".
            "revenue_ty": None if rev is None else rev / 1_000_000_000,
            "remaining": (rep["undelivered"].get(name) or {}).get("qty", 0.0),
        }
        rows.append(row)
        for k, _, _ in SUMMARY_COLS:
            v = row.get(k)
            if isinstance(v, (int, float)):
                totals[k] += v
    return rows, totals, missing_fx


def _detail(deliveries: list[dict[str, Any]], names: dict[str, str]) -> list[dict]:
    """Bung từng lần giao thành các dòng bán, mới nhất trước (giống Lịch sử đợt giao trên web)."""
    out: list[dict] = []
    for r in sorted(deliveries, key=lambda x: (x.get("delivered_at") or "", x["id"]), reverse=True):
        is_batch = r.get("parent_id") is not None
        for ln in r.get("lines") or []:
            grade = (ln.get("grade") or "").strip() or "(chưa khai)"
            qty, dry = ln.get("qty"), ln.get("qty_dry")
            price, fx = ln.get("price"), ln.get("fx")
            out.append({
                "delivered_at": r.get("delivered_at"),
                "company": r["company"],
                # Mã đợt giao chỉ là số thứ tự trong hợp đồng nên tự nó vô nghĩa — luôn kèm mã HĐ mẹ.
                "contract_code": r.get("parent_code") or r.get("code"),
                "batch_code": r.get("code") if is_batch else None,
                "customer": names.get(str(r.get("customer_id") or 0)) or "(chưa gán khách hàng)",
                "contract_type": CONTRACT_TYPES.get(r.get("contract_type") or ""),
                "channel": SALE_CHANNELS.get(r.get("channel") or ""),
                "to_company": r.get("to_company"),
                "grade": grade,
                # Mủ nước chỉ có nghĩa với latex + 2 loại mủ nguyên liệu; thành phẩm bán ra đã là
                # hàng khô nên để trống, hiện lại số lượng ở đây là mời người đọc cộng hai lần.
                "qty_wet": qty if grade in DRY_REQUIRED_GRADES else None,
                "qty_dry": dry,
                "qty": calc.sale_qty(ln),
                "price": price,
                "ccy": ln.get("ccy"),
                "fx": fx,
                "amount": None if qty is None or price is None else qty * price,
                # Thiếu tỷ giá → để TRỐNG, không quy về 0 (giống mọi chỗ khác của báo cáo).
                # Làm tròn về ĐỒNG: nhân với 1.000.000 làm sai số dấu phẩy động nở ra, ô hiện
                # 441.674.999,9999999 trông như số bịa dù chỉ là cách máy lưu số thực.
                "revenue_vnd": _dong(calc.line_revenue_vnd(ln)),
                "invoice_no": r.get("invoice_no"),
                "payment_date": r.get("payment_date"),
                "record_id": r["id"],
            })
    return out


def build(date_from: str, date_to: str, rep: dict[str, Any], companies: list[str] | None,
          customer_ids: list[int] | None, grades: list[str] | None) -> bytes:
    """Dựng file Excel của Báo cáo tiêu thụ: sheet tổng hợp + sheet chi tiết dòng bán."""
    rows, totals, missing_fx = _summary(rep)
    # Đọc lại các lần giao cho sheet chi tiết (bảng tổng hợp đã cộng mất chi tiết). Cùng tham số lọc
    # nên chắc chắn cùng tập dữ liệu; xuất file là thao tác lẻ nên một lượt đọc nữa không đáng kể.
    deliveries = sales_contract_report.deliveries(date_from, date_to, companies, customer_ids, grades)
    detail = _detail(deliveries, rep.get("customers") or {})

    note = "Nguồn: các lần giao ghi trên hợp đồng & đợt giao."
    if grades:
        note += f" Chỉ tính chủng loại: {', '.join(grades)}."
    if missing_fx:
        note += " ⚠ Có lần giao thiếu tỷ giá → doanh thu để trống, KHÔNG tính là 0."
    detail_note = (
        f"{len(detail)} dòng bán của {len(deliveries)} lần giao — cùng bộ lọc với sheet tổng hợp nên "
        "cộng cột “SL tính tiêu thụ” ra đúng sản lượng tiêu thụ. SL tính tiêu thụ = quy khô nếu dòng "
        "có khai, không khai thì lấy số lượng. Ô “Quy khô” trống ở latex/mủ nguyên liệu = chưa khai.")
    return unit_analytics_excel.build_xlsx(
        title="BÁO CÁO TIÊU THỤ", period=f"{date_from} → {date_to}", note=note,
        group_by="company", columns=SUMMARY_COLS, rows=rows, totals=totals,
        sheets=[{"name": "Chi tiết lần giao", "title": "CHI TIẾT TỪNG DÒNG BÁN",
                 "note": detail_note, "columns": DETAIL_COLS, "rows": detail}])
