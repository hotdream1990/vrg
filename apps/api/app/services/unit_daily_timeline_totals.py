"""Dòng lũy kế của bảng Tiêu thụ – Tồn kho theo ngày (biểu `consumption`).

Bảng này cắt trang Ở SERVER nên web không thể tự cộng: cộng trên màn hình chỉ ra tổng của 50 dòng
đang thấy. Service cộng trên TOÀN BỘ khoảng đang lọc rồi trả về đúng đơn vị hiển thị của bảng.

Ở đây chỉ còn khối TỒN KHO — chỉ tiêu **THỜI ĐIỂM**: lấy ẢNH CHỤP MỚI NHẤT của TỪNG đơn vị rồi
mới cộng ngang các đơn vị. Cộng tồn kho của nhiều ngày là đếm đi đếm lại cùng một lô hàng. Ngày
của ảnh chụp trả kèm (`stock_as_of`) vì có thể sớm hơn ngày cuối khoảng — đơn vị chưa cập nhật tồn.

Khối TIÊU THỤ (dòng chảy, cộng dồn) nằm ở `unit_daily_contract_consumption` — gom từ các lần giao
của hợp đồng; router trộn hai phần lại trước khi trả về.

Công thức phải khớp cột cùng tên ở `apps/web/src/lib/unit-daily-fields.ts` (CONSUMPTION), nếu
không dòng tổng sẽ cãi nhau với chính các dòng phía trên. Khoá của kết quả = khoá cột của bảng.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services import member_unit_merge, unit_daily_repo, unit_report_rows

#: Ảnh chụp cũ hơn ngần này ngày so với cuối khoảng thì ĐẾM RIÊNG và nói ra. KHÔNG loại khỏi tổng:
#: bỏ đơn vị chậm nộp là mất hàng thật của họ; giấu chuyện số đã cũ mới là cái sai (khoảng mặc định
#: của bảng là 90 ngày, đo prod 06/09/2026 có đơn vị ảnh chụp cũ 37 ngày vẫn nằm im trong dòng tổng).
STALE_DAYS = 7


def _num(v: Any) -> float:
    try:
        return 0.0 if v is None else float(v)
    except (TypeError, ValueError):
        return 0.0


def _tonnes(fields: dict, key: str) -> float:
    rows = fields.get(key)
    return sum(_num(r.get("qty")) for r in rows if isinstance(r, dict)) if isinstance(rows, list) else 0.0


def _latest_stock_per_company(entries: list[dict]) -> dict[str, dict]:
    """Bản ghi tồn MỚI NHẤT của từng đơn vị trong khoảng (bỏ qua ngày chỉ có dòng bán).

    Dùng chung quy tắc `has_stock` với màn Thống kê tồn kho và Báo cáo tổng hợp — ba nơi phải ra
    cùng một con số, nếu không người dùng không biết tin màn nào.
    """
    latest: dict[str, dict] = {}
    for e in entries:
        if not unit_report_rows.has_stock(e["fields"]):
            continue
        cur = latest.get(e["company"])
        if cur is None or e["as_of"] > cur["as_of"]:
            latest[e["company"]] = e
    return latest


def consumption_totals(date_from: str, date_to: str,
                       companies: list[str] | None = None) -> dict[str, Any]:
    """Lũy kế cả khoảng cho biểu Tiêu thụ – Tồn kho. Khoá = khoá cột của bảng ở web."""
    entries = unit_daily_repo.in_range("consumption", date_from, date_to, companies,
                                       attach_contracts=False)
    latest = _latest_stock_per_company(entries)
    # Đơn vị đã SÁP NHẬP mà đơn vị nhận đã khai tồn kể từ ngày hiệu lực → lô hàng đó đã nằm trong
    # số của bên nhận, cộng thêm ảnh chụp cuối của bên cũ là tính trùng (cùng luật với Thống kê
    # tồn kho và Báo cáo tổng hợp — bổ sung 06/09/2026, trước đó chỉ 2/4 màn áp luật này).
    for dead in member_unit_merge.stock_superseded({c: e["as_of"] for c, e in latest.items()}):
        latest.pop(dead, None)
    stale = [e["as_of"] for e in latest.values()
             if (date.fromisoformat(date_to) - date.fromisoformat(e["as_of"])).days > STALE_DAYS]
    not_wh = sum(_tonnes(e["fields"], "stock_not_warehoused") for e in latest.values())
    wh = sum(_tonnes(e["fields"], "stock_warehoused") for e in latest.values())
    material = sum(_num(e["fields"].get("stock_material")) for e in latest.values())
    # "Đã ký HĐ chưa giao" là CAM KẾT còn tồn tại NGÀY CUỐI KHOẢNG (không phụ thuộc đơn vị có nhập
    # số ngày đó hay không) — hỏi hợp đồng một lần, giống cách Báo cáo tổng hợp chốt khối này.
    signed = unit_daily_repo.contracts_on(date_to, companies)
    signed_qty = sum(_num(v.get("qty")) for v in signed.values())

    z = lambda v: v or None                                    # noqa: E731 — 0 hiện "—", không phải "0"
    return {
        # Tiêu thụ KHÔNG còn ở đây: nhóm cột số cũ đã gỡ 20/08/2026, số hiện hành do
        # `unit_daily_contract_consumption.totals()` cộng từ các lần giao và trộn vào ở router.
        "stock_not_warehoused_t": z(not_wh),
        "stock_warehoused_t": z(wh),
        "stock_finished_t": z(not_wh + wh),
        "stock_signed_t": z(signed_qty),
        "stock_material": z(material),
        # Ngày của ảnh chụp tồn mới nhất — web ghi ra cạnh nhãn để không ai tưởng là số cộng dồn.
        "stock_as_of": max((e["as_of"] for e in latest.values()), default=None),
        # …và độ cũ của phần còn lại: `stock_as_of` một mình chỉ khoe đơn vị nộp sớm nhất, che mất
        # việc trong tổng còn số của đơn vị đã lâu không nộp.
        "stock_units": len(latest) or None,
        "stock_stale_units": len(stale) or None,
        "stock_stale_days": STALE_DAYS,          # web ghi đúng ngưỡng đang dùng, không gõ lại số
        "stock_oldest_as_of": min(stale, default=None),
    }
