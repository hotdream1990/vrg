"""Xuất Excel cho **Báo cáo tiêu thụ** — 3 sheet: TỔNG HỢP theo đơn vị · THEO HỢP ĐỒNG · CHI TIẾT dòng bán.

Bảng tổng hợp chỉ trả lời "đơn vị này bao nhiêu tấn"; muốn soát "số đó gồm những gì, dòng nào làm
lệch" thì phải có bản ghi chi tiết để lọc/pivot ngay trong Excel. Sheet chi tiết vì thế mở tới mức
DÒNG BÁN (mỗi chủng loại của một lần giao là một dòng), kèm sẵn bộ lọc của Excel.

Sheet **Theo hợp đồng** đứng giữa hai mức đó: mỗi dòng là MỘT CHỦNG LOẠI của MỘT HỢP ĐỒNG, cộng
các lần giao trong kỳ — hợp đồng bán nhiều chủng loại thì tách thành nhiều dòng, để lấy được sản
lượng quy khô của từng loại mà không phải tự pivot (yêu cầu 27/08/2026).

Cả ba sheet đọc CÙNG `sales_contract_report` với bảng trên web và cùng bộ lọc, nên tổng cột sản
lượng của chúng luôn khớp nhau — không thể lệch.
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


#: Mỗi dòng = MỘT chủng loại của MỘT hợp đồng (cộng các lần giao trong kỳ). Chỉ giữ thông tin
#: nhận diện hợp đồng, phần còn lại là sản lượng — thứ người đọc cần lấy ra.
CONTRACT_COLS: list[Col] = [
    ("company", "Đơn vị", ""),
    ("contract_code", "Số hợp đồng", ""),
    ("customer", "Khách hàng", ""),
    ("contract_type", "Loại HĐ", ""),
    ("channel", "Hình thức tiêu thụ", ""),
    ("to_company", "Đơn vị nhận (nội bộ)", ""),
    ("grade", "Chủng loại", ""),
    ("deliveries", "Số lần giao", "lần"),
    ("first_at", "Giao từ ngày", ""),
    ("last_at", "Giao đến ngày", ""),
    ("qty_wet", "SL mủ nước", "tấn"),
    ("qty", "Sản lượng", "tấn quy khô"),
    ("revenue_vnd", "Doanh thu", "đồng"),
    ("avg_price", "Đơn giá bình quân", "tr.đ/tấn quy khô"),
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


def _by_contract(deliveries: list[dict[str, Any]], names: dict[str, str]) -> list[dict]:
    """Gom các lần giao thành dòng (hợp đồng × chủng loại) — sắp theo đơn vị · hợp đồng · chủng loại.

    Hình thức tiêu thụ nằm ở TỪNG lần giao, nên một hợp đồng có thể giao vừa xuất khẩu vừa trong
    nước: gom lại mà chọn bừa một giá trị là nói sai, nên ghi rõ "Nhiều hình thức".
    """
    acc: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in deliveries:
        code = r.get("parent_code") or r.get("code")
        for ln in r.get("lines") or []:
            grade = (ln.get("grade") or "").strip() or "(chưa khai)"
            key = (r["company"], code or "", grade)
            g = acc.get(key)
            if g is None:
                g = acc[key] = {
                    "company": r["company"], "contract_code": code, "grade": grade,
                    "customer": names.get(str(r.get("customer_id") or 0)) or "(chưa gán khách hàng)",
                    "contract_type": CONTRACT_TYPES.get(r.get("contract_type") or ""),
                    "to_company": r.get("to_company"),
                    "qty_wet": 0.0, "qty": 0.0, "revenue_vnd": 0.0,
                    "_channels": set(), "_ids": set(), "_days": set(),
                }
            g["_channels"].add(r.get("channel") or "")
            g["_ids"].add(r["id"])
            if r.get("delivered_at"):
                g["_days"].add(r["delivered_at"])
            if grade in DRY_REQUIRED_GRADES and ln.get("qty") is not None:
                g["qty_wet"] += ln["qty"]
            g["qty"] += calc.sale_qty(ln) or 0.0
            rev = calc.line_revenue_vnd(ln)
            # Thiếu tỷ giá/đơn giá ở BẤT KỲ dòng nào → doanh thu cả nhóm để trống, không cộng phần
            # còn lại rồi coi như đủ (cùng luật với mọi chỗ khác của báo cáo).
            g["revenue_vnd"] = None if rev is None or g["revenue_vnd"] is None else g["revenue_vnd"] + rev

    out = []
    for g in acc.values():
        chans = {c for c in g.pop("_channels") if c}
        days = sorted(g.pop("_days"))
        rev = g["revenue_vnd"]
        out.append({
            **g,
            "channel": (SALE_CHANNELS.get(next(iter(chans))) if len(chans) == 1
                        else ("Nhiều hình thức" if chans else None)),
            "deliveries": len(g.pop("_ids")),
            "first_at": days[0] if days else None,
            "last_at": days[-1] if days else None,
            "qty_wet": g["qty_wet"] or None,
            "revenue_vnd": _dong(rev),
            "avg_price": (rev / g["qty"] / 1_000_000) if rev and g["qty"] else None,
        })
    return sorted(out, key=lambda r: (r["company"], r["contract_code"] or "", r["grade"]))


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
    by_contract = _by_contract(deliveries, rep.get("customers") or {})
    contract_note = (
        f"{len(by_contract)} dòng — mỗi dòng là MỘT chủng loại của MỘT hợp đồng, cộng các lần giao "
        "trong kỳ. Hợp đồng bán nhiều chủng loại tách thành nhiều dòng. Cộng cột “Sản lượng” ra "
        "đúng sản lượng tiêu thụ của sheet tổng hợp. Doanh thu để trống khi hợp đồng có lần giao "
        "thiếu tỷ giá.")
    return unit_analytics_excel.build_xlsx(
        title="BÁO CÁO TIÊU THỤ", period=f"{date_from} → {date_to}", note=note,
        group_by="company", columns=SUMMARY_COLS, rows=rows, totals=totals,
        sheets=[{"name": "Theo hợp đồng", "title": "SẢN LƯỢNG THEO HỢP ĐỒNG & CHỦNG LOẠI",
                 "note": contract_note, "columns": CONTRACT_COLS, "rows": by_contract},
                {"name": "Chi tiết lần giao", "title": "CHI TIẾT TỪNG DÒNG BÁN",
                 "note": detail_note, "columns": DETAIL_COLS, "rows": detail}])
