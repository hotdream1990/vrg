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
from app.services import member_unit_repo, price_repo, unit_daily_fields, unit_daily_repo

TRIEU = 1_000_000       # 1 triệu đồng

#: Loại mủ thu mua — 4 nhóm; nhóm `finished` còn tách tiếp theo chủng loại.
MATERIALS: tuple[str, ...] = ("latex", "cup", "lace", "finished")
MATERIAL_LABELS = {
    "latex": "Mủ nước", "cup": "Mủ chén", "lace": "Mủ dây",
    "finished": "Thành phẩm",
}

#: Mủ nguyên liệu nhập ô CỐ ĐỊNH ở biểu Thu mua — cả ba loại khai GIỐNG NHAU:
#: (loại mủ, ô sản lượng, ô đơn giá nội tệ, loại giá trong kho).
#: `qty` LUÔN là số QUY KHÔ → mọi chỉ tiêu tổng cùng một cơ sở DRC, cộng được với nhau.
PURCHASE_MATERIALS: tuple[tuple[str, str, str, str], ...] = (
    ("latex", "latex_wet", "price_latex_local", "purchase"),
    ("cup", "coagulum", "price_cup_local", "purchase_cup"),
    ("lace", "lace", "price_lace_local", "purchase_lace"),
)
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
    """{tên đơn vị: {region, country, has_factory}} — đơn vị đang hoạt động + đơn vị ĐÃ SÁP NHẬP.

    Đơn vị đã sáp nhập bị ẩn (`is_active = false`) nhưng số liệu cũ của họ vẫn phải tra được khu
    vực; thiếu ở đây thì mọi dòng trước sáp nhập rơi vào nhóm "(Chưa gán khu vực)".
    """
    return {u["name"]: u for u in member_unit_repo.list_units()
            if u.get("is_active") or u.get("merged_into")}


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
        # Loại mủ đơn vị đã khai rõ "ngày này không có giá" — vẫn để `price = None` (không kéo giá
        # bình quân) nhưng KHÔNG được đếm vào cảnh báo "chưa nhập đơn giá".
        no_price = unit_daily_fields.declared_no_price(f)
        for material, qty_key, local_key, price_type in PURCHASE_MATERIALS:
            qty = _num(f.get(qty_key))
            if qty is None:
                continue
            # Đơn vị nước ngoài nhập giá nội tệ → quy về VND; còn lại lấy kho "Giá mủ nguyên liệu".
            local = _price(f.get(local_key))
            price = (local * fx_local) if (local is not None and fx_local) else _price(day_px.get(material))
            common = {**base, "material": material, "price": price, "price_unit": "dong_do",
                      "price_unit_label": PURCHASE_PRICE_UNIT[price_type],
                      "ccy": "VND", "fx": None, "revenue_vnd": None,
                      "price_declared_none": material in no_price,
                      "missing_fx": local is not None and not fx_local}
            # Đơn vị đã tách chủng loại (từ 20/09/2026) → mỗi chủng loại một dòng, `grade` là
            # chủng loại THẬT. Ngày chưa tách thì vẫn một dòng với nhãn loại mủ như trước —
            # nhờ vậy bảng chéo chủng loại hiện rõ phần nào đã tách, phần nào còn gom chung,
            # thay vì im lặng làm biến mất sản lượng của các ngày cũ.
            table = unit_daily_fields.MATERIAL_GRADE_TABLES[material][0]
            breakdown = [r for r in (f.get(table) or []) if _num(r.get("qty")) is not None]
            if breakdown:
                for r in breakdown:
                    rows.append({**common, "grade": str(r.get("grade") or "").strip() or "—",
                                 "qty": _num(r.get("qty"))})
            else:
                rows.append({**common, "grade": MATERIAL_LABELS[material], "qty": qty})
        for ln in f.get("finished") or []:
            qty = _num(ln.get("qty"))
            if qty is None:
                continue
            price = _price(ln.get("price"))   # đơn giá 0 = chưa có giá → không tính doanh thu
            rev = line_revenue_vnd(qty, price, ln.get("ccy"), ln.get("fx"))
            rows.append({**base, "material": "finished", "grade": str(ln.get("grade") or "").strip() or "—",
                         "qty": qty, "price": price, "price_unit": "per_tonne",
                         "price_unit_label": None, "ccy": ln.get("ccy") or "VND", "fx": _num(ln.get("fx")),
                         "revenue_vnd": rev, "price_declared_none": False,
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


#: Đơn vị tick "không phát sinh tồn kho để khai" thì giữ nguyên số của LẦN KHAI GẦN NHẤT — quét lùi
#: tối đa ngần này ngày để tìm lần khai đó. Xa hơn nữa coi như đơn vị không có số: dựng tồn kho hôm
#: nay từ một con số hai tháng trước thì thà báo thiếu còn hơn.
CARRY_LOOKBACK_DAYS = 30


def stock_rows(as_of: str, companies: list[str] | None = None, all_days: bool = False,
               days_back: int = 0) -> dict[str, Any]:
    """Tồn kho tại NGÀY CHỐT `as_of` — ảnh chụp, KHÔNG cộng dồn giữa các ngày.

    Quy tắc lấy số của một đơn vị cho một ngày (chốt với chủ đề án 21/08/2026):

    1. Đơn vị **khai tồn** ngày đó → dùng đúng số ngày đó.
    2. Đơn vị tick **"hôm nay không phát sinh tồn kho để khai"** → giữ nguyên số của lần khai gần
       nhất (cờ đó nghĩa là tồn không đổi), quét lùi tối đa `CARRY_LOOKBACK_DAYS` ngày.
    3. Đơn vị **không khai gì** → KHÔNG có số. Trước đây số của ngày trước được đắp sang trong 7
       ngày, khiến biểu đồ hiện tồn kho cho cả những đơn vị chưa hề nộp.

    Mỗi dòng mang `age_days` = số ngày đã cũ (0 = khai đúng ngày) để người xem biết số thuộc ngày nào.

    `days_back` chỉ mở rộng PHẠM VI NGÀY trả về khi `all_days=True` (xem diễn biến tồn) — nó không
    còn dùng để đắp số cũ cho ngày thiếu.

    Trả về:
    - `rows`     → mỗi dòng = 1 chủng loại trong 1 khối (chưa nhập kho / đã nhập kho / đã ký HĐ
                   chưa giao) + 1 dòng tồn nguyên liệu.
    - `no_stock` → {đơn vị: ngày} đã tick "không phát sinh" mà KHÔNG tìm được lần khai nào trước đó
                   (đã nộp nhưng chưa từng có số) — không đếm là thiếu báo cáo, cũng không suy ra 0.
    """
    end_day = date.fromisoformat(as_of)
    first_day = end_day - timedelta(days=max(days_back, 0))
    scan_from = (first_day - timedelta(days=CARRY_LOOKBACK_DAYS)).isoformat()
    meta = unit_meta()
    entries = unit_daily_repo.in_range("consumption", scan_from, as_of, companies)

    declared: dict[str, dict[str, dict[str, Any]]] = {}   # ngày → {đơn vị: bản ghi có số}
    unchanged: dict[str, set[str]] = {}                   # ngày → đơn vị tick "không phát sinh"
    for e in entries:
        if has_stock(e["fields"]):
            declared.setdefault(e["as_of"], {})[e["company"]] = e
        elif e["fields"].get("no_stock") is True:
            unchanged.setdefault(e["as_of"], set()).add(e["company"])

    kept: dict[Any, dict[str, Any]] = {}
    no_stock: dict[str, str] = {}
    latest: dict[str, dict[str, Any]] = {}                # đơn vị → lần khai gần nhất đã gặp
    span = (end_day - date.fromisoformat(scan_from)).days
    for i in range(span + 1):
        day = (date.fromisoformat(scan_from) + timedelta(days=i)).isoformat()
        latest.update(declared.get(day, {}))
        if day < first_day.isoformat() or (not all_days and day != as_of):
            continue
        snap = dict(declared.get(day, {}))
        for company in unchanged.get(day, set()):
            carried = latest.get(company)                 # cờ "không đổi" → giữ số lần khai gần nhất
            if carried and company not in snap:
                snap[company] = carried
            elif not carried:
                no_stock[company] = day
        for company, entry in snap.items():
            kept[(company, day) if all_days else company] = (entry, day)

    undelivered = _undelivered_by_snapshot([e for e, _ in kept.values()])
    rows: list[dict[str, Any]] = []
    for entry, day in kept.values():
        base = _base(entry, meta)
        base["as_of"] = day                    # ngày của ẢNH CHỤP…
        base["source_as_of"] = entry["as_of"]  # …còn đây là ngày số liệu được khai
        base["age_days"] = (date.fromisoformat(day) - date.fromisoformat(entry["as_of"])).days
        f = entry["fields"]
        for block in STOCK_BLOCKS:
            for ln in f.get(block) or []:
                qty = _num(ln.get("qty"))
                if qty is None:
                    continue
                rows.append({**base, "block": block,
                             "grade": str(ln.get("grade") or "").strip() or "—", "qty": qty})
        rows.append({**base, "block": "stock_material", "grade": "Nguyên liệu chưa sản xuất",
                     "qty": _num(f.get("stock_material"))})
        for grade, qty in (undelivered.get((entry["as_of"], entry["company"])) or {}).items():
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
