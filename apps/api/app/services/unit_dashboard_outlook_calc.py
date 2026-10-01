"""Phép tính của thẻ "Tiến độ bán hàng năm" — số từng đơn vị rồi cộng theo nhóm (tách khỏi
`unit_dashboard_outlook` cho mỗi file một việc).

Mọi tổng đều cộng từ số của TỪNG ĐƠN VỊ nên dòng Tập đoàn, dòng khu vực và dòng đơn vị không thể
kể ba câu chuyện khác nhau. Tỷ lệ luôn chia lại trên tổng, không cộng/bình quân các tỷ lệ con.
"""

from __future__ import annotations

from typing import Any, Callable

from app.services.unit_report_query import NO_REGION_LABEL
from app.services.weekly_ai_compose import vn

_EPS = 1e-9
#: Nêu tên tối đa ngần này đơn vị trong một câu ghi chú — toàn Tập đoàn có hơn 60 đơn vị.
_MAX_NAMES = 5


def unit_metrics(c: str, sold: dict[str, Any], back: dict[str, Any],
                 plans: dict[str, dict[str, float]], bought_goods: float = 0.0) -> dict[str, Any]:
    """Số của MỘT đơn vị. `sold` = dòng thống kê tiêu thụ lũy kế, `back` = Backlog tại ngày tính,
    `bought_goods` = tấn thành phẩm MUA NGOÀI lũy kế (biểu Thu mua) — để biết đơn vị có kinh doanh
    hàng hóa mà chưa nhập KH hàng hóa không."""
    delivered = sold.get("qty") or 0.0
    to_deliver = back.get("to_deliver") or 0.0
    avg = sold.get("avg_price_trieu")          # triệu đ/tấn; None = chưa có lần giao có doanh thu
    exploit = plans["exploit"].get(c)          # None = CHƯA NHẬP; 0 = đơn vị không khai thác
    purchase = plans["purchase"].get(c) or 0.0
    goods = plans["goods"].get(c)              # None = CHƯA NHẬP; 0 = không kinh doanh hàng hóa
    # Sản lượng bán gồm cả hàng hóa (thành phẩm mua ngoài bán lại) → kế hoạch phải đủ 3 nguồn, thiếu
    # nguồn nào là % KH bán hàng đội lên (Tân Biên 29/09/2026: bán 10.191 / KH 4.500 = 226%).
    plan_total = (exploit or 0.0) + purchase + (goods or 0.0)
    # Đơn giá nghi sai đơn vị tính (56.200 thay cho 56,2) kéo giá BQ lên cả nghìn lần — đem nhân với
    # phần còn phải giao là nhân cái sai lên thêm → phần đó CHƯA ĐỊNH GIÁ, giống đơn vị chưa có giá.
    bad = bool(sold.get("bad_price_lines"))
    priced = avg is not None and not bad
    # tấn × triệu đ/tấn = triệu đồng → ÷ 1.000 = tỷ đồng.
    rest = to_deliver * avg / 1000 if priced else 0.0
    revenue_ytd = sold.get("revenue_ty") or 0.0
    return {
        "company": c,
        "lt_committed": back.get("master_committed") or 0.0,
        "lt_delivered": back.get("master_delivered") or 0.0,
        "lt_remaining": back.get("master_remaining") or 0.0,
        "lt_expired_short": back.get("master_expired_short") or 0.0,
        "lt_remaining_after_year": back.get("master_remaining_after_year") or 0.0,
        "lt_masters": back.get("masters") or 0,
        "lt_unlinked_undelivered": back.get("lt_unlinked_undelivered") or 0.0,
        "spot_undelivered": back.get("spot_undelivered") or 0.0,
        "principle_undelivered": back.get("principle_undelivered") or 0.0,
        "unknown_undelivered": back.get("unknown_undelivered") or 0.0,
        "backlog_lt_remaining": back.get("lt_remaining") or 0.0,
        "to_deliver": to_deliver,
        "delivered_ytd": delivered,
        "projected": delivered + to_deliver,
        "exploit": exploit, "purchase": purchase, "goods": goods or 0.0, "plan_total": plan_total,
        "in_qty_basket": exploit is not None and plan_total > _EPS,
        "missing_exploit": exploit is None and (purchase > _EPS or (goods or 0.0) > _EPS),
        # Nhập 0 (hoặc bỏ trống) mà vẫn mua thành phẩm về bán → KH bán hàng thiếu phần hàng hóa.
        "missing_goods": bought_goods > _EPS and (goods or 0.0) <= _EPS,
        "plan_revenue": plans["revenue"].get(c) or 0.0,
        "revenue_ytd": revenue_ytd,
        "revenue_expected_rest": rest,
        "revenue_projected": revenue_ytd + rest,
        # Doanh thu lũy kế đang THIẾU (lần giao chưa có tỷ giá/đơn giá) hoặc SAI (đơn giá nghi nhầm
        # đơn vị tính) → giá BQ và mọi phép chiếu từ nó đều không đứng được.
        "revenue_blocked": bool(sold.get("no_revenue_lines")) or bad,
        "bad_price": bad,
        "unpriced": to_deliver if (to_deliver > _EPS and not priced) else 0.0,
    }


def _pct(num: float, den: float | None) -> float | None:
    return num / den * 100 if den and den > _EPS else None


def _names(ms: list[dict[str, Any]]) -> str:
    names = [m["company"] for m in ms]
    more = f" và {len(names) - _MAX_NAMES} đơn vị khác" if len(names) > _MAX_NAMES else ""
    return ", ".join(names[:_MAX_NAMES]) + more


def _qty_note(qb: list[dict]) -> str:
    # Rổ và số cả phạm vi là các ô số riêng (`units_planned`, `basket_projected`, `projected`) —
    # web tự đặt cạnh nhau; ghi lại thành câu ở đây là nói hai lần.
    if not qb:
        return "Chưa đơn vị nào nhập đủ KH khai thác + KH thu mua — chưa so được với KH bán hàng."
    if miss := [m for m in qb if m["missing_goods"]]:
        return (f"{_names(miss)} có mua thành phẩm bên ngoài nhưng KH hàng hóa đang trống hoặc bằng "
                f"0 — sản lượng bán có phần hàng hóa mà kế hoạch thì không, nên % KH bán hàng có "
                f"thể cao hơn thực tế.")
    return ""


def _revenue_note(ms: list[dict], rb: list[dict]) -> str:
    parts = []
    if stop := [m for m in rb if m["revenue_blocked"]]:
        parts.append(f"Chưa tính % vì {len(stop)} đơn vị có dòng bán thiếu tỷ giá/đơn giá hoặc đơn "
                     f"giá nghi sai đơn vị tính: {_names(stop)}.")
    if unpriced := [m for m in ms if m["unpriced"] > _EPS and not m["bad_price"]]:
        tonnes = sum(m["unpriced"] for m in unpriced)
        parts.append(f"{vn(tonnes)} tấn còn phải giao chưa định giá (đơn vị chưa có lần giao nào năm "
                     f"nay để lấy giá BQ): {_names(unpriced)}.")
    return " ".join(parts)


def aggregate(ms: list[dict[str, Any]]) -> dict[str, Any]:
    """Cộng số của một nhóm đơn vị (cả phạm vi · một khu vực · một đơn vị) → các ô của thẻ."""
    def total(key: str) -> float:
        return sum(m[key] for m in ms)

    qb = [m for m in ms if m["in_qty_basket"]]
    rb = [m for m in ms if m["plan_revenue"] > _EPS]
    qty_basket = sum(m["projected"] for m in qb)
    plan_total = sum(m["plan_total"] for m in qb)
    rev_basket = sum(m["revenue_projected"] for m in rb)
    plan_rev = sum(m["plan_revenue"] for m in rb)
    rev_stop = any(m["revenue_blocked"] or m["unpriced"] > _EPS for m in rb)
    projected, rev_projected = total("projected"), total("revenue_projected")
    return {
        "lt_committed": total("lt_committed"), "lt_delivered": total("lt_delivered"),
        "lt_remaining": total("lt_remaining"), "lt_expired_short": total("lt_expired_short"),
        "lt_remaining_after_year": total("lt_remaining_after_year"),
        "lt_masters": int(total("lt_masters")),
        "lt_unlinked_undelivered": total("lt_unlinked_undelivered"),
        "lt_pct": _pct(total("lt_delivered"), total("lt_committed")),
        "spot_undelivered": total("spot_undelivered"),
        "principle_undelivered": total("principle_undelivered"),
        "unknown_undelivered": total("unknown_undelivered"),
        "backlog_lt_remaining": total("backlog_lt_remaining"), "to_deliver": total("to_deliver"),
        "delivered_ytd": total("delivered_ytd"), "projected": projected,
        "plan_exploit": sum(m["exploit"] or 0.0 for m in qb) if qb else None,
        "plan_purchase": sum(m["purchase"] for m in qb) if qb else None,
        "plan_goods": sum(m["goods"] for m in qb) if qb else None,
        "plan_total": plan_total if qb else None,
        "qty_basket_projected": qty_basket if qb else None,
        "qty_pct": _pct(qty_basket, plan_total) if qb else None,
        "qty_units_planned": len(qb),
        "units_missing_exploit": sum(1 for m in ms if m["missing_exploit"]),
        "qty_note": _qty_note(qb),
        "revenue_ytd": total("revenue_ytd"), "revenue_expected_rest": total("revenue_expected_rest"),
        "revenue_projected": rev_projected,
        "plan_revenue": plan_rev if rb else None,
        "revenue_basket_projected": rev_basket if rb else None,
        "revenue_pct": None if (not rb or rev_stop) else _pct(rev_basket, plan_rev),
        "revenue_units_planned": len(rb),
        "revenue_note": _revenue_note(ms, rb),
        "bad_price_warning": _bad_price_warning(ms),
    }


def _bad_price_warning(ms: list[dict[str, Any]]) -> str | None:
    """Cảnh báo cho CẢ phạm vi, không chỉ rổ có KH: đơn vị không được giao KH doanh thu vẫn góp số
    vào "đã thực hiện + dự kiến" của cả phạm vi."""
    bad = [m for m in ms if m["bad_price"]]
    if not bad:
        return None
    return (f"Có dòng bán đơn giá nghi sai đơn vị tính ở {_names(bad)} — doanh thu đã thực hiện đang "
            f"bị đội lên; phần còn phải giao của các đơn vị này chưa định giá.")


def label_fn(sc: dict[str, Any], region_of: dict[str, str | None]) -> Callable[[str], str]:
    """Đơn vị → nhãn dòng của chiều con (chính nó khi xem một khu vực, khu vực khi xem Tập đoàn)."""
    if sc["child"] == "company":
        return lambda c: c
    return lambda c: region_of.get(c) or NO_REGION_LABEL
