"""Làm phẳng payload jsonb của báo cáo ngày thành DÒNG CHI TIẾT (để lọc & thống kê).

Báo cáo kỳ hiện có (`unit_period_report`) gộp thẳng lên mức đơn vị nên mất chủng loại /
loại HĐ / hình thức HĐ. Module này giữ nguyên chi tiết từng dòng để màn Thống kê lọc được:

- `purchase_rows`    → mỗi dòng = 1 loại mủ trong 1 ngày của 1 đơn vị (mủ nước · mủ chén ·
                       từng chủng loại thành phẩm). Đơn giá mủ nước/chén lấy từ kho giá
                       (đồng/độ), đơn vị nước ngoài quy từ nội tệ qua `fx_purchase`.
- `consumption_rows` → mỗi dòng bán (gồm cả nguồn mủ: thu mua `sales` / khai thác `sales_own`).
- `stock_rows`       → tồn kho là số THỜI ĐIỂM tại NGÀY CHỐT: mỗi đơn vị lấy bản ghi mới nhất
                       ≤ ngày chốt (không cộng dồn), kèm ngày thật + số ngày đã cũ.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_UNIT as UNIT_SRC
from app.services import member_unit_repo, price_repo, unit_daily_repo

TRIEU = 1_000_000       # 1 triệu đồng

#: Loại mủ thu mua — 3 nhóm; nhóm `finished` còn tách tiếp theo chủng loại.
MATERIALS: tuple[str, ...] = ("latex", "cup", "finished")
MATERIAL_LABELS = {
    "latex": "Mủ nước", "cup": "Mủ chén",
    "finished": "Thành phẩm",
}
#: Nguồn mủ tiêu thụ (2 bảng nhập tách riêng ở biểu Tiêu thụ).
# Từ 30/07/2026 tiêu thụ đến từ LẦN GIAO của hợp đồng, không còn tách 2 nguồn mủ. Hai nhãn cũ giữ
# lại để bản ghi lịch sử (nếu có nơi nào còn đọc) không hiện ra chuỗi thô.
SOURCE_LABELS = {"sales": "Mủ thu mua", "sales_own": "Mủ khai thác", "contract": "Theo hợp đồng"}
#: 2 khối tồn kho nhập tay (khối nguyên liệu là ô đơn, không có chủng loại).
STOCK_BLOCKS = ("stock_not_warehoused", "stock_warehoused")
#: Khối TỰ TÍNH từ hợp đồng bán hàng: đã ký chưa giao = sản lượng hợp đồng − đã giao.
#: Nằm TRONG tồn kho thành phẩm (không cộng thêm) → dùng để suy ra phần còn bán được.
CONTRACT_BLOCK = "contract_undelivered"


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _price(v: Any) -> float | None:
    """Đơn giá thu mua — **0 = "không có giá"**, trả None (xem `core/market_meta`).

    Nhờ vậy dòng đó rơi vào cảnh báo "có sản lượng nhưng chưa có đơn giá" thay vì lặng lẽ
    kéo tụt giá bình quân gia quyền của cả nhóm.
    """
    n = _num(v)
    return None if n == 0 else n


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

    Dòng mủ nước có `price` theo **đồng/độ TSC**, mủ chén theo **đồng/độ DRC**
    (`market_meta.PURCHASE_PRICE_UNIT` — cố định từ 17/08/2026, không còn cho chọn);
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
        for material, qty_key, local_key, px_key in (
            ("latex", "latex_wet", "price_latex_local", "latex"),
            ("cup", "coagulum", "price_cup_local", "cup"),
        ):
            qty = _num(f.get(qty_key))
            if qty is None:
                continue
            # Đơn vị nước ngoài nhập giá nội tệ → quy về VND; còn lại lấy kho "Giá mủ nguyên liệu".
            local = _price(f.get(local_key))
            price = (local * fx_local) if (local is not None and fx_local) else _price(day_px.get(px_key))
            rows.append({**base, "material": material, "grade": MATERIAL_LABELS[material],
                         "qty": qty, "price": price, "price_unit": "dong_do",
                         "price_unit_label": PURCHASE_PRICE_UNIT[
                             "purchase_cup" if material == "cup" else "purchase"],
                         "ccy": "VND", "fx": None, "revenue_vnd": None,
                         "missing_fx": local is not None and not fx_local})
        for ln in f.get("finished") or []:
            qty = _num(ln.get("qty"))
            if qty is None:
                continue
            price = _price(ln.get("price"))   # đơn giá 0 = chưa có giá → không tính doanh thu
            rev = line_revenue_vnd(qty, price, ln.get("ccy"), ln.get("fx"))
            rows.append({**base, "material": "finished", "grade": str(ln.get("grade") or "").strip() or "—",
                         "qty": qty, "price": price, "price_unit": "per_tonne",
                         "price_unit_label": None, "ccy": ln.get("ccy") or "VND", "fx": _num(ln.get("fx")),
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
    from app.services import sales_contract_calc, sales_contract_report

    out: list[dict[str, Any]] = []
    for d in sales_contract_report.deliveries(date_from, date_to, companies):
        base = {"as_of": d.get("delivered_at"), "company": d["company"],
                "region": (meta.get(d["company"]) or {}).get("region")}
        for ln in d.get("lines") or []:
            ccy = ln.get("ccy") or "VND"
            fx = _num(ln.get("fx"))
            # Sản lượng BÁO CÁO = quy khô khi có (PA1); doanh thu vẫn tính trên MỦ NƯỚC.
            qty_wet = _num(ln.get("qty"))
            qty = sales_contract_calc.sale_qty(ln)
            rev = (qty_wet * _num(ln.get("price")) * TRIEU
                   if ccy == "VND" and qty_wet is not None and _num(ln.get("price")) is not None
                   else (qty_wet * _num(ln.get("price")) * fx
                         if qty_wet is not None and _num(ln.get("price")) is not None and fx else None))
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


def stock_rows(as_of: str, max_age_days: int, companies: list[str] | None = None,
               all_days: bool = False) -> dict[str, Any]:
    """Tồn kho tại NGÀY CHỐT `as_of`: mỗi đơn vị lấy bản ghi tồn MỚI NHẤT có ngày ≤ ngày chốt.

    `max_age_days` = số ngày được phép lùi: bản ghi cũ hơn thế coi như KHÔNG có số (thà thiếu còn
    hơn lấy số quá cũ đắp cho ngày chốt). Mỗi dòng mang `age_days` = số ngày đã cũ để người xem
    biết số thuộc ngày nào — không nơi nào được hiểu đây là số nhập đúng ngày chốt.

    Trả về:
    - `rows`     → mỗi dòng = 1 chủng loại trong 1 khối (chưa nhập kho / đã nhập kho / đã ký HĐ
                   chưa giao) + 1 dòng tồn nguyên liệu. `all_days=True` giữ TẤT CẢ các ngày trong
                   cửa sổ (xem diễn biến tồn), mỗi ngày vẫn là ảnh chụp độc lập — KHÔNG cộng dồn
                   giữa các ngày.
    - `no_stock` → {đơn vị: ngày mới nhất} đã khai "không phát sinh tồn kho để khai". Đơn vị này
                   ĐÃ NỘP nhưng KHÔNG có số để cộng: không được đếm là thiếu báo cáo, cũng không
                   được tự suy thành tồn = 0 (cờ chỉ nói "không có gì để khai", không nói hết hàng).
    """
    day = date.fromisoformat(as_of)
    start = (day - timedelta(days=max(max_age_days, 0))).isoformat()
    meta = unit_meta()
    entries = unit_daily_repo.in_range("consumption", start, as_of, companies)
    kept: dict[Any, dict[str, Any]] = {}
    no_stock: dict[str, str] = {}
    for e in entries:                      # in_range trả theo ngày TĂNG dần → ghi đè = ngày cuối
        if has_stock(e["fields"]):
            kept[(e["company"], e["as_of"]) if all_days else e["company"]] = e
        elif e["fields"].get("no_stock") is True:
            no_stock[e["company"]] = e["as_of"]

    undelivered = _undelivered_by_snapshot(kept.values())
    rows: list[dict[str, Any]] = []
    for e in kept.values():
        base = _base(e, meta)
        base["age_days"] = (day - date.fromisoformat(e["as_of"])).days
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
        for grade, qty in (undelivered.get((e["as_of"], e["company"])) or {}).items():
            rows.append({**base, "block": CONTRACT_BLOCK,
                         "grade": str(grade or "").strip() or "—", "qty": _num(qty)})
    return {"rows": rows, "no_stock": no_stock}


def _undelivered_by_snapshot(entries) -> dict[tuple[str, str], dict[str, float]]:
    """{(ngày, đơn vị): {chủng loại: đã ký chưa giao}} — tính tại ĐÚNG ngày của số tồn kho.

    Cùng ngày với số tồn thì phép trừ "tồn thành phẩm − đã ký chưa giao" mới có nghĩa: lấy hợp đồng
    của ngày chốt trừ tồn kho của ngày khác là ghép số hai thời điểm. Đơn vị nào KHÔNG có số tồn
    trong cửa sổ thì cũng không lấy hợp đồng của họ — nếu không, nhóm chỉ có phần trừ.
    """
    by_date: dict[str, list[str]] = {}
    for e in entries:
        by_date.setdefault(e["as_of"], []).append(e["company"])
    out: dict[tuple[str, str], dict[str, float]] = {}
    for d, comps in by_date.items():
        for company, data in unit_daily_repo.contracts_on(d, comps).items():
            out[(d, company)] = data.get("by_grade") or {}
    return out
