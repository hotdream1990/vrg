"""Làm phẳng payload jsonb của báo cáo ngày thành DÒNG CHI TIẾT (để lọc & thống kê).

Báo cáo kỳ hiện có (`unit_period_report`) gộp thẳng lên mức đơn vị nên mất chủng loại /
loại HĐ / hình thức HĐ. Module này giữ nguyên chi tiết từng dòng để màn Thống kê lọc được:

- `purchase_rows`    → mỗi dòng = 1 loại mủ trong 1 ngày của 1 đơn vị (mủ nước · mủ chén ·
                       từng chủng loại thành phẩm). Đơn giá mủ nước/chén lấy từ kho giá
                       (đồng/độ), đơn vị nước ngoài quy từ nội tệ qua `fx_purchase`.
- `consumption_rows` → mỗi dòng bán (gồm cả nguồn mủ: thu mua `sales` / khai thác `sales_own`).
- `stock_rows`       → tồn kho là số THỜI ĐIỂM: lấy ngày CUỐI CÙNG có số liệu tồn của TỪNG
                       đơn vị trong kỳ (không cộng dồn, không mượn số ngày khác).
"""

from __future__ import annotations

from typing import Any

from app.core.market_meta import PURCHASE_SOURCE_UNIT as UNIT_SRC
from app.services import member_unit_repo, price_repo, unit_daily_repo

TRIEU = 1_000_000       # 1 triệu đồng

#: Loại mủ thu mua — 3 nhóm; nhóm `finished` còn tách tiếp theo chủng loại.
MATERIALS: tuple[str, ...] = ("latex", "cup", "cup_raw", "rss_pressed", "finished")
MATERIAL_LABELS = {
    "latex": "Mủ nước", "cup": "Mủ chén",
    # 2 loại bổ sung chốt 30/07/2026 — đơn giá nhập theo ĐỒNG/KG (khác đồng/độ của 2 loại trên).
    "cup_raw": "Mủ NL nước chưa cán vắt (chén)", "rss_pressed": "Mủ NL đã cán vắt (RSS)",
    "finished": "Thành phẩm",
}
#: Nguồn mủ tiêu thụ (2 bảng nhập tách riêng ở biểu Tiêu thụ).
# Từ 30/07/2026 tiêu thụ đến từ LẦN GIAO của hợp đồng, không còn tách 2 nguồn mủ. Hai nhãn cũ giữ
# lại để bản ghi lịch sử (nếu có nơi nào còn đọc) không hiện ra chuỗi thô.
SOURCE_LABELS = {"sales": "Mủ thu mua", "sales_own": "Mủ khai thác", "contract": "Theo hợp đồng"}
#: 2 khối tồn kho nhập tay (khối "đã ký HĐ" có màn riêng, khối nguyên liệu là ô đơn).
STOCK_BLOCKS = ("stock_not_warehoused", "stock_warehoused")


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def line_revenue_vnd(qty: Any, price: Any, ccy: str | None, fx: Any) -> float | None:
    """Doanh thu 1 dòng quy về BASE = đồng. GIỮ ĐÚNG quy tắc của form nhập
    (`lib/unit-daily-consumption.ts::lineRevenueVnd`): USD thiếu tỷ giá → None, KHÔNG đoán."""
    q, p = _num(qty), _num(price)
    if q is None or p is None:
        return None
    if (ccy or "VND") != "USD":
        return q * p * TRIEU
    f = _num(fx)
    return None if f is None else q * p * f


def unit_meta() -> dict[str, dict[str, Any]]:
    """{tên đơn vị: {region, country, has_factory}} — đơn vị đang hoạt động."""
    return {u["name"]: u for u in member_unit_repo.list_units(include_inactive=False)}


def _base(entry: dict, meta: dict[str, dict]) -> dict[str, Any]:
    """Phần đầu chung của mọi dòng chi tiết: ngày · đơn vị · khu vực."""
    company = entry["company"]
    return {"as_of": entry["as_of"], "company": company,
            "region": (meta.get(company) or {}).get("region")}


# ── Thu mua ────────────────────────────────────────────────────────────────────
def purchase_rows(date_from: str, date_to: str,
                  companies: list[str] | None = None) -> dict[str, Any]:
    """Dòng chi tiết thu mua + danh sách (đơn vị, ngày) KHÔNG tổ chức thu mua.

    Dòng mủ nước/mủ chén có `price` theo **đồng/độ** (TSC hoặc DRC — xem `cup_basis`);
    dòng thành phẩm có `price` theo loại tiền của dòng + `revenue_vnd` đã quy đổi.
    """
    meta = unit_meta()
    entries = unit_daily_repo.in_range("purchase", date_from, date_to, companies)
    px = price_repo.purchase_prices_in_range(date_from, date_to, UNIT_SRC)
    rows: list[dict[str, Any]] = []
    no_purchase: list[dict[str, str]] = []

    for e in entries:
        f = e["fields"]
        base = _base(e, meta)
        if f.get("no_purchase") is True:
            no_purchase.append({"company": base["company"], "as_of": base["as_of"]})
        day_px = px.get((base["company"], base["as_of"])) or {}
        fx_local = _num(f.get("fx_purchase"))
        cup_basis = f.get("cup_basis") or "tsc"
        for material, qty_key, local_key, px_key in (
            ("latex", "latex_wet", "price_latex_local", "latex"),
            ("cup", "coagulum", "price_cup_local", "cup"),
        ):
            qty = _num(f.get(qty_key))
            if qty is None:
                continue
            # Đơn vị nước ngoài nhập giá nội tệ → quy về VND; còn lại lấy kho "Giá mủ nguyên liệu".
            local = _num(f.get(local_key))
            price = (local * fx_local) if (local is not None and fx_local) else _num(day_px.get(px_key))
            rows.append({**base, "material": material, "grade": MATERIAL_LABELS[material],
                         "qty": qty, "price": price, "price_unit": "dong_do",
                         "cup_basis": cup_basis if material == "cup" else None,
                         "ccy": "VND", "fx": None, "revenue_vnd": None,
                         "missing_fx": local is not None and not fx_local})
        # 2 loại nguyên liệu bổ sung — đơn giá lưu THẲNG trong payload (đồng/kg), không qua kho giá.
        for material in ("cup_raw", "rss_pressed"):
            qty = _num(f.get(material))
            if qty is None:
                continue
            rows.append({**base, "material": material, "grade": MATERIAL_LABELS[material],
                         "qty": qty, "price": _num(f.get(f"{material}_price")),
                         "price_unit": "dong_kg", "cup_basis": None,
                         "ccy": "VND", "fx": None, "revenue_vnd": None, "missing_fx": False})
        for ln in f.get("finished") or []:
            qty = _num(ln.get("qty"))
            if qty is None:
                continue
            rev = line_revenue_vnd(qty, ln.get("price"), ln.get("ccy"), ln.get("fx"))
            rows.append({**base, "material": "finished", "grade": str(ln.get("grade") or "").strip() or "—",
                         "qty": qty, "price": _num(ln.get("price")), "price_unit": "per_tonne",
                         "cup_basis": None, "ccy": ln.get("ccy") or "VND", "fx": _num(ln.get("fx")),
                         "revenue_vnd": rev,
                         "missing_fx": (ln.get("ccy") == "USD" and _num(ln.get("fx")) is None)})
    return {"rows": rows, "no_purchase": no_purchase}


# ── Tiêu thụ ───────────────────────────────────────────────────────────────────
def consumption_rows(date_from: str, date_to: str,
                     companies: list[str] | None = None) -> dict[str, Any]:
    """Dòng bán chi tiết — nguồn DUY NHẤT là các LẦN GIAO của hợp đồng (chốt 02/08/2026).

    Mỗi dòng: loại HĐ · hình thức · chủng loại · SL · giá · doanh thu quy VND.
    Hai mảng `sales`/`sales_own` cũ KHÔNG còn dựng dòng: chưa chạy script chuyển đổi thì chúng chỉ
    là dữ liệu tra cứu, trộn vào đây làm lệch chỉ tiêu (loại HĐ, hình thức, mốc ghi nhận đều khác).
    """
    return {"rows": _delivery_rows(date_from, date_to, companies, unit_meta())}


def _delivery_rows(date_from: str, date_to: str, companies: list[str] | None,
                   meta: dict[str, dict]) -> list[dict[str, Any]]:
    """Dòng bán lấy từ các LẦN GIAO của hợp đồng (nguồn tiêu thụ hiện hành từ 30/07/2026).

    Không có 2 mảng cũ nữa nên `source` để trống và `contract` lấy theo loại giao của hợp đồng;
    các cột còn lại giữ đúng khuôn dòng cũ để màn Thống kê tiêu thụ dùng chung một bảng.
    """
    from app.services import sales_contract_report

    out: list[dict[str, Any]] = []
    for d in sales_contract_report.deliveries(date_from, date_to, companies):
        base = {"as_of": d.get("delivered_at"), "company": d["company"],
                "region": (meta.get(d["company"]) or {}).get("region")}
        for ln in d.get("lines") or []:
            ccy = ln.get("ccy") or "VND"
            fx = _num(ln.get("fx"))
            qty = _num(ln.get("qty"))
            rev = (qty * _num(ln.get("price")) * TRIEU
                   if ccy == "VND" and qty is not None and _num(ln.get("price")) is not None
                   else (qty * _num(ln.get("price")) * fx
                         if qty is not None and _num(ln.get("price")) is not None and fx else None))
            out.append({
                **base, "source": "contract", "code": d.get("code"),
                # Loại HỢP ĐỒNG (dài hạn/chuyến) — KHÔNG lấy `delivery_type` (loại GIAO): suy từ đó
                # thì mọi hợp đồng đều rơi vào "HĐ chuyến". Chưa khai loại → để trống, không đoán.
                "contract": d.get("contract_type") or "",
                "channel": d.get("channel") or "domestic",
                "grade": str(ln.get("grade") or "").strip() or "—",
                "qty": qty, "price": _num(ln.get("price")),
                "ccy": ccy, "fx": fx, "revenue_vnd": rev,
                "missing_fx": (ccy != "VND" and fx is None),
                "warehouse_date": None, "invoice_date": d.get("payment_date"),
            })
    return out


# ── Tồn kho (số THỜI ĐIỂM) ─────────────────────────────────────────────────────
def has_stock(fields: dict) -> bool:
    """Bản ghi ngày này có nhập tồn kho hay không (chỉ có dòng bán thì không tính).

    Quy tắc DÙNG CHUNG cho mọi nơi lấy "mốc tồn kho" (màn Thống kê tồn kho + Báo cáo tổng hợp)
    → hai màn luôn ra cùng một số. Đơn vị thường nhập dòng bán trước, khối tồn để trống.
    """
    return bool(fields.get("stock_not_warehoused") or fields.get("stock_warehoused")
                or fields.get("stock_material") is not None)


def stock_rows(date_from: str, date_to: str, companies: list[str] | None = None,
               all_days: bool = False) -> list[dict[str, Any]]:
    """Tồn kho tại MỐC: ngày cuối cùng CÓ số liệu tồn của từng đơn vị trong kỳ.

    Mỗi dòng = 1 chủng loại trong 1 khối (chưa nhập kho / đã nhập kho) + 1 dòng tồn nguyên liệu.
    `all_days=True` → giữ TẤT CẢ các ngày có số liệu (xem diễn biến tồn theo ngày), mỗi ngày vẫn
    là một ảnh chụp độc lập — KHÔNG cộng dồn giữa các ngày.
    """
    meta = unit_meta()
    entries = unit_daily_repo.in_range("consumption", date_from, date_to, companies)
    kept: dict[Any, dict[str, Any]] = {}
    for e in entries:                      # in_range trả theo ngày TĂNG dần → ghi đè = ngày cuối
        if has_stock(e["fields"]):
            kept[(e["company"], e["as_of"]) if all_days else e["company"]] = e

    rows: list[dict[str, Any]] = []
    for e in kept.values():
        base = _base(e, meta)
        f = e["fields"]
        for block in STOCK_BLOCKS:
            for ln in f.get(block) or []:
                qty = _num(ln.get("qty"))
                if qty is None:
                    continue
                rows.append({**base, "block": block,
                             "grade": str(ln.get("grade") or "").strip() or "—", "qty": qty})
        rows.append({**base, "block": "stock_material", "grade": "Nguyên liệu chưa sản xuất",
                     "qty": _num(f.get("stock_material"))})
    return rows
