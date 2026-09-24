"""Tồn kho Tập đoàn THEO NGÀY cho màn Gợi ý giá sàn + Trợ lý AI (thay chuỗi tuần `fact_inventory`).

Chốt với chủ dự án 24/09/2026: giá sàn và AI KHÔNG còn đọc tồn kho tuần. Bảng tuần dừng ở
07/08/2026 trên prod nên AI đang nói số cũ 7 tuần mà vẫn gọi là "tuần gần nhất". Số ở đây cộng
thẳng từ biểu Tồn kho đơn vị tự khai, CÙNG luật với biểu đồ tồn kho Command Center
(`unit_series_stock`) để số AI nói khớp số trên báo cáo:

- tồn thành phẩm = "đã nhập kho" + "chưa nhập kho"; phần đã ký HĐ cắt trần theo tồn từng đơn vị;
- đơn vị cũ đã sáp nhập thôi được cộng khi đơn vị nhận cũng có số hôm đó;
- các ngày CUỐI đang nhập dở bị bỏ (9h sáng mới vài đơn vị nhập, đọc thẳng thì thành "tồn sụt").

So sánh hai mốc chỉ tính trên các đơn vị có số ở CẢ HAI mốc — thiếu người nhập không được biến thành
"tồn kho giảm". Trước `STOCK_START` chưa đủ đơn vị nhập nên không có số; KHÔNG lấy số tuần bù vào.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core import edit_window
from app.services import member_unit_merge, unit_daily_repo, unit_report_rows
from app.services.unit_series_stock import STOCK_START, trim_pending

Snapshots = dict[str, dict[str, float]]   # ngày → {đơn vị: tồn thành phẩm (tấn)}


def load(date_from: str = STOCK_START, date_to: str | None = None) -> Snapshots:
    """Tồn thành phẩm từng đơn vị theo ngày trong [date_from, date_to] (mặc định tới hôm nay)."""
    date_to = date_to or edit_window.today().isoformat()
    date_from = max(date_from, STOCK_START)
    if date_to < date_from:
        return {}
    days_back = (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days
    # Không kèm hợp đồng: phần đắt nhất (1 truy vấn/ngày) — chỉ hỏi ở vài mốc cần, xem `signed_capped`.
    raw = unit_report_rows.stock_rows(date_to, all_days=True, days_back=days_back, with_contracts=False)
    snaps: Snapshots = {}
    for r in raw["rows"]:
        if r["block"] in unit_report_rows.STOCK_BLOCKS and r["qty"]:
            day = snaps.setdefault(r["as_of"], {})
            day[r["company"]] = day.get(r["company"], 0.0) + r["qty"]
    pairs = member_unit_merge.merge_pairs()
    for day, units in snaps.items():
        for dead in member_unit_merge.superseded_in(pairs, dict.fromkeys(units, day)):
            units.pop(dead, None)
    rows = [{"as_of": d, "units_counted": len(u)} for d, u in sorted(snaps.items()) if u]
    kept, _ = trim_pending(rows)
    return {r["as_of"]: snaps[r["as_of"]] for r in kept}


def series(snaps: Snapshots) -> list[tuple[str, float]]:
    """[(ngày, tổng tồn Tập đoàn)] tăng theo ngày."""
    return [(d, sum(u.values())) for d, u in sorted(snaps.items())]


def day_at(snaps: Snapshots, as_of: str | None) -> str | None:
    """Ngày có số gần nhất ≤ `as_of` (None nếu trước ngày đầu tiên có số)."""
    if not as_of:
        return None
    return max((d for d in snaps if d <= as_of), default=None)


def signed_capped(day: str, units: dict[str, float]) -> dict[str, float]:
    """Đã ký HĐ chưa giao của từng đơn vị tại `day`, cắt trần theo tồn của chính đơn vị đó.

    Cắt trần vì hợp đồng ký cả cho hàng chưa sản xuất — lấy nguyên thì phần "tự do" âm.
    """
    got = unit_daily_repo.contracts_on(day, list(units))
    return {c: min(sum(((got.get(c) or {}).get("by_grade") or {}).values()), q)
            for c, q in units.items()}


def free_series(snaps: Snapshots, dates: list[str]) -> list[tuple[str, float]]:
    """[(ngày, tồn tự do)] chỉ tại các mốc `dates` — hỏi hợp đồng cho cả chuỗi ngày thì quá nặng."""
    out: dict[str, float] = {}
    for d in dates:
        day = day_at(snaps, d)
        if day and day not in out:
            units = snaps[day]
            out[day] = sum(units.values()) - sum(signed_capped(day, units).values())
    return sorted(out.items())


def at(snaps: Snapshots, as_of: str, base_as_of: str | None = None) -> dict[str, Any] | None:
    """Tồn kho tại ngày có số gần nhất ≤ `as_of`, kèm thay đổi so với mốc `base_as_of`.

    `d_*` chỉ cộng các đơn vị có số ở CẢ HAI ngày (`units_compared`), nên có thể khác hiệu của hai
    con số tổng — hai tổng lệch nhau vì số đơn vị nhập khác nhau thì không phải tồn kho thay đổi.
    """
    day = day_at(snaps, as_of)
    if not day:
        return None
    units = snaps[day]
    signed = signed_capped(day, units)
    total, done = sum(units.values()), sum(signed.values())
    out: dict[str, Any] = {
        "day": day, "ton_kho": round(total), "ton_kho_hd": round(done), "ton_free": round(total - done),
        "units_counted": len(units), "base_day": None, "units_compared": 0,
        "d_ton_kho": None, "d_ton_kho_pct": None, "d_free": None, "d_free_pct": None,
    }
    base = day_at(snaps, base_as_of)
    common = sorted(set(units) & set(snaps[base])) if base and base != day else []
    if not common:
        return out
    before = {c: snaps[base][c] for c in common}
    base_total = sum(before.values())
    cur_total = sum(units[c] for c in common)
    base_free = base_total - sum(signed_capped(base, before).values())
    cur_free = cur_total - sum(signed[c] for c in common)
    out.update(base_day=base, units_compared=len(common), d_ton_kho=round(cur_total - base_total),
               d_ton_kho_pct=round((cur_total - base_total) / base_total * 100, 2) if base_total else None,
               d_free=round(cur_free - base_free),
               d_free_pct=round((cur_free - base_free) / base_free * 100, 2) if base_free > 0 else None)
    return out
