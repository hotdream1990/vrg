"""Tiêu thụ THEO HỢP ĐỒNG gom về (đơn vị × ngày) — cho bảng Tồn kho hiện SONG SONG với số cũ.

Vì sao có file này: nhóm cột "Tiêu thụ (số cũ đã khai)" trên bảng Tồn kho đọc ô `revenue` được
chốt cứng lúc lưu phiếu, nên nó KHÔNG đổi theo khi hợp đồng được sửa. Đợt sửa đơn giá 10/08/2026
chỉnh trên hợp đồng nhưng ô `revenue` vẫn giữ số sai — hai màn từ đó nói khác nhau mà người dùng
không có cách nào lần ra bản ghi lệch.

Module này gom CÙNG một nguồn với Báo cáo tiêu thụ (`unit_report_rows.consumption_rows` → các LẦN
GIAO của hợp đồng) nên hai màn không thể cãi nhau số.

Số gắn vào bản ghi dưới các khoá `c_*`. Đây là số CHỈ ĐỌC: chúng không nằm trong danh sách ô được
phép lưu (`unit_daily_fields.CONSUMPTION_FIELDS`) nên dù form có gửi ngược lên cũng bị loại, không
bao giờ ghi đè vào payload.
"""

from __future__ import annotations

from typing import Any

from app.services import unit_report_rows

TY = 1_000_000_000      # doanh thu base = đồng, dòng lũy kế hiện "tỷ đồng"
TRIEU = 1_000_000       # giá bán bình quân hiện "triệu đ/tấn"

#: Hình thức giao → ô cộng dồn. Hình thức lạ/thiếu chỉ vào tổng, KHÔNG dồn bừa vào một ô nào —
#: dồn nhầm thì chỉ tiêu XK/nội tiêu sai mà không ai biết.
_CHANNEL_KEY = {"export": "c_qty_export", "domestic": "c_qty_domestic",
                "internal": "c_qty_internal"}

#: Khoá công khai gắn vào `fields` — phải khớp key cột ở `apps/web/src/lib/unit-daily-fields.ts`.
KEYS: tuple[str, ...] = ("c_qty", "c_qty_export", "c_qty_domestic", "c_qty_internal",
                         "c_revenue", "c_avg_price", "c_lines")

#: Ngày đơn vị có nộp phiếu tồn kho nhưng KHÔNG có lần giao nào → mọi ô để trống (hiện "—"),
#: không phải số 0: "không giao gì" và "chưa có dữ liệu" là hai chuyện khác nhau.
_EMPTY: dict[str, Any] = dict.fromkeys(KEYS)


def _new() -> dict[str, Any]:
    return {"c_qty": 0.0, "c_qty_export": 0.0, "c_qty_domestic": 0.0, "c_qty_internal": 0.0,
            "c_revenue": 0.0, "c_lines": 0, "_rev_qty": 0.0}


def _feed(acc: dict, row: dict) -> None:
    """Cộng 1 dòng giao vào ô tích luỹ. Dòng thiếu tỷ giá KHÔNG vào doanh thu (không đoán số)."""
    qty = row.get("qty") or 0.0
    acc["c_qty"] += qty
    if key := _CHANNEL_KEY.get(row.get("channel") or ""):
        acc[key] += qty
    acc["c_lines"] += 1
    if row.get("revenue_vnd") is not None:
        acc["c_revenue"] += row["revenue_vnd"]
        acc["_rev_qty"] += qty


def _close(acc: dict) -> dict[str, Any]:
    """Chốt một ô tích luỹ → giá trị BASE (tấn · đồng · đồng/tấn). 0 trả None để bảng hiện "—"."""
    rev_qty = acc.pop("_rev_qty")
    # Giá BQ chia cho sản lượng CÓ doanh thu, không chia tổng: dòng thiếu tỷ giá mà nằm ở mẫu số
    # sẽ kéo giá bình quân tụt xuống một cách vô lý. Cùng quy ước với `unit_report_consumption`.
    out: dict[str, Any] = {k: (v or None) for k, v in acc.items()}
    out["c_avg_price"] = (acc["c_revenue"] / rev_qty) if rev_qty else None
    return out


def by_company_day(date_from: str, date_to: str,
                   companies: list[str] | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    """{(đơn vị, ngày): số tiêu thụ theo hợp đồng} — giá trị ở BASE (đồng cho tiền)."""
    rows = unit_report_rows.consumption_rows(date_from, date_to, companies)["rows"]
    acc: dict[tuple[str, str], dict] = {}
    for r in rows:
        if not r.get("company") or not r.get("as_of"):
            continue
        _feed(acc.setdefault((r["company"], r["as_of"]), _new()), r)
    return {k: _close(v) for k, v in acc.items()}


def attach(entries: list[dict], by_key: dict[tuple[str, str], dict[str, Any]]) -> None:
    """Gắn số theo hợp đồng vào từng bản ghi của trang timeline (tại chỗ)."""
    for e in entries:
        e["fields"].update(by_key.get((e["company"], e["as_of"])) or _EMPTY)


def attach_day(entries: dict[str, dict], as_of: str,
               by_key: dict[tuple[str, str], dict[str, Any]]) -> None:
    """Như `attach` nhưng cho lưới MỘT NGÀY của chuyên viên ({đơn vị: bản ghi})."""
    for company, e in entries.items():
        e["fields"].update(by_key.get((company, as_of)) or _EMPTY)


def totals(by_key: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    """Lũy kế cả khoảng cho dòng tổng — trả ĐÚNG ĐƠN VỊ HIỂN THỊ của bảng (tấn · tỷ đồng · triệu).

    Cộng trên TOÀN BỘ khoảng đang lọc, không phải trang đang xem (bảng cắt trang ở server).
    """
    qty = exp = dom = internal = revenue = rev_qty = 0.0
    for v in by_key.values():
        qty += v.get("c_qty") or 0.0
        exp += v.get("c_qty_export") or 0.0
        dom += v.get("c_qty_domestic") or 0.0
        internal += v.get("c_qty_internal") or 0.0
        rev = v.get("c_revenue")
        if rev is not None:
            revenue += rev
            # Sản lượng có doanh thu suy ngược từ giá BQ của chính ô đó — giữ đúng mẫu số khi
            # trong khoảng có ngày thiếu tỷ giá.
            price = v.get("c_avg_price")
            rev_qty += (rev / price) if price else 0.0
    z = lambda v: v or None                                    # noqa: E731 — 0 hiện "—", không phải "0"
    return {
        "c_qty": z(qty), "c_qty_export": z(exp), "c_qty_domestic": z(dom),
        "c_qty_internal": z(internal),
        "c_revenue": z(revenue / TY),
        "c_avg_price": (revenue / rev_qty / TRIEU) if rev_qty else None,
    }


def summarize(date_from: str, date_to: str,
              companies: list[str] | None = None) -> dict[str, Any]:
    """Gọi MỘT lần cho cả trang: bản đồ theo (đơn vị, ngày) + dòng lũy kế cả khoảng."""
    by_key = by_company_day(date_from, date_to, companies)
    return {"by_key": by_key, "totals": totals(by_key)}
