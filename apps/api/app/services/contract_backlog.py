"""SẢN LƯỢNG CÒN PHẢI GIAO của đơn vị tại một ngày — tách HĐ chuyến · HĐ dài hạn (26/09/2026).

Phản hồi của khách: phần "đã ký chưa giao" phải chia ra **HĐ chuyến đã ký chưa giao + HĐ dài hạn
còn phải giao = tổng phải giao** đến cuối năm, kèm HĐ dài hạn đã giao bao nhiêu trên số cam kết.

KHÁC "đã ký HĐ chưa giao" (khối 3 — `sales_contract_report.undelivered_on`) ở phần dài hạn: tính
theo CAM KẾT của hợp đồng mẹ (HĐDH/HĐNT), nên gồm cả sản lượng khách đã cam kết mà đơn vị chưa ký
phụ lục. Hai con số đo hai thứ khác nhau — giữ hai nhãn khác nhau (plan 260926 Q4).

Luật (plan 260926 Q1–Q3):
  - HĐ mẹ ĐƯỢC TÍNH = HĐ DÀI HẠN (HĐDH) có cam kết > 0, ký ≤ ngày tính, hết hạn KHÔNG trước 01/01 năm
    của ngày tính. HĐ NGUYÊN TẮC không tính (đổi 28/09/2026 — Cao su Tây Ninh chỉ bán HĐ chuyến dưới
    HĐNT mà bị hiện 3.427 t "HĐ dài hạn" = trọn cam kết HĐNT): phụ lục của nó tính theo loại HĐ của
    chính phụ lục như mọi hợp đồng không thuộc HĐ mẹ được tính.
  - Đã giao của HĐ mẹ = mọi lần giao ≤ ngày tính của phụ lục + đợt giao của phụ lục, LŨY KẾ từ ngày
    ký — cam kết là của cả đời hợp đồng, cắt theo năm là coi hàng giao năm ngoái như chưa giao.
  - Còn phải giao = max(cam kết − đã giao, Σ phụ lục đã ký chưa giao): phụ lục ký vượt cam kết thì
    hàng đã ký vẫn là nợ giao thật. HĐ mẹ HẾT HẠN → chỉ còn phụ lục đã ký chưa giao, phần cam kết
    chưa ký phụ lục báo riêng `master_expired_short`. HĐ mẹ còn hiệu lực sau 31/12 (hoặc không thời
    hạn) → phần còn lại của nó báo thêm ở `master_remaining_after_year` (chưa chắc giao trong năm).
  - KHÔNG đếm trùng: hợp đồng thuộc HĐ mẹ được tính chỉ góp ở cấp HĐ mẹ; mọi hợp đồng còn lại tính
    theo khối 3 của chính nó, chia theo NHÓM HĐ (chuyến · HĐ nguyên tắc · dài hạn · chưa khai —
    `sales_contract_group`, 01/10/2026): phụ lục của HĐNT vào ô HĐNT riêng, không vào "dài hạn".
Gốc số: trừ trên QUY KHÔ khi cả cam kết lẫn mọi lần giao của chủng loại đều có khai, không thì trên
mủ nước (`_master_totals`, cùng luật khối 3).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import sales_contract_report
from app.services.contract_backlog_sql import MASTER_SQL
from app.services.unit_report_query import roll_by_company

_EPS = 1e-9
#: Nhóm HĐ của hợp đồng KHÔNG thuộc HĐ mẹ được tính → ô cộng dồn. Chưa khai loại vào ô riêng,
#: không dồn vào nhóm nào — dồn là làm sai con số chuyến/dài hạn (cùng luật với báo cáo tiêu thụ).
_BUCKET = {"spot": "spot_undelivered", "principle": "principle_undelivered",
           "long_term": "lt_unlinked_undelivered"}


def _empty() -> dict[str, Any]:
    return {"spot_undelivered": 0.0, "principle_undelivered": 0.0,
            "lt_unlinked_undelivered": 0.0, "lt_missing_master_undelivered": 0.0,
            "lt_missing_master_items": [], "unknown_undelivered": 0.0,
            "master_committed": 0.0, "master_delivered": 0.0, "master_remaining": 0.0,
            "master_expired_short": 0.0, "master_remaining_after_year": 0.0,
            "masters": 0, "master_pct": None,
            "lt_remaining": 0.0, "to_deliver": 0.0, "items": []}


def _masters(as_of: str, companies: list[str] | None,
             grades: list[str] | None) -> list[dict[str, Any]]:
    """HĐ mẹ được tính kèm cam kết + đã giao — MỘT truy vấn cho mọi đơn vị, cộng ở Python."""
    ensure_schema()
    scope, params = "", {"d": as_of, "y0": f"{as_of[:4]}-01-01"}
    if companies is not None:
        scope, params["cs"] = "AND company = ANY(:cs)", list(companies)
    with session_scope() as db:
        # Cùng lý do với `undelivered_on`: `jsonb_array_elements` làm Postgres ước lượng số dòng
        # vống lên hàng trăm lần → JIT biên dịch lại mỗi lượt gọi. `SET LOCAL` chỉ áp giao dịch này.
        db.execute(text("SET LOCAL jit = off"))
        rows = db.execute(text(MASTER_SQL.format(scope=scope)), params).mappings().all()
    by_id: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        by_id.setdefault(r["id"], []).append(dict(r))
    keep = set(grades or ())
    out = []
    for lines in by_id.values():
        committed, delivered = _master_totals([r for r in lines if not keep or r["grade"] in keep])
        out.append({**lines[0], "committed": committed, "delivered": delivered})
    return out


def _master_totals(lines: list[dict[str, Any]]) -> tuple[float, float]:
    """(cam kết, đã giao) của MỘT HĐ mẹ — trừ trên CÙNG GỐC SỐ theo từng chủng loại.

    Cùng luật `sales_contract_report._remaining_by_grade`: chỉ trừ trên KHÔ khi cam kết CÓ khai quy
    khô VÀ mọi lần giao của chủng loại đó cũng có; còn lại trừ trên MỦ NƯỚC. Thành phẩm thì nước =
    khô nên không khác. Hàng đã giao của chủng loại KHÔNG có trong cam kết vẫn là hàng đã giao của hồ
    sơ → tính theo số tiêu thụ (khô nếu có).
    """
    committed = delivered = 0.0
    for r in lines:
        cw, cd = float(r["commit_wet"] or 0), float(r["commit_dry"] or 0)
        if cw <= _EPS and cd <= _EPS:
            delivered += float(r["done_sale"] or 0)
            continue
        on_dry = cd > _EPS and not int(r["done_no_dry"] or 0)
        committed += cd if on_dry else cw
        delivered += float((r["done_dry"] if on_dry else r["done_wet"]) or 0)
    return committed, delivered


def _master_item(m: dict[str, Any], as_of: date, annex_open: float) -> dict[str, Any] | None:
    """Một HĐ mẹ → dòng `items`. None khi lọc chủng loại làm nó không còn số nào để kể.

    Hết hạn: phần cam kết chưa ký phụ lục không còn phải giao, nhưng PHỤ LỤC ĐÃ KÝ chưa giao vẫn là
    nợ giao thật (hợp đồng đã ký) → còn phải giao = phần phụ lục đó; phần thiếu còn lại báo riêng.
    Bỏ luôn phụ lục thì "tổng phải giao" nhỏ hơn "đã ký HĐ chưa giao" — đúng loại lệch khách phản ánh.
    """
    committed, delivered = float(m["committed"] or 0), float(m["delivered"] or 0)
    expired = m["expiry_date"] is not None and m["expiry_date"] < as_of
    left = max(committed - delivered, 0.0)
    remaining = annex_open if expired else max(left, annex_open)
    if max(committed, delivered, remaining) <= _EPS:
        return None
    # Còn hiệu lực sau 31/12 năm đang xem (hoặc không thời hạn) → phần còn lại chưa chắc giao trong năm.
    after_year = not expired and (m["expiry_date"] is None
                                  or m["expiry_date"] > date(as_of.year, 12, 31))
    return {"id": m["id"], "code": m["code"], "master_type": m["master_type"],
            "customer_id": m["customer_id"],
            "sign_date": str(m["sign_date"]) if m["sign_date"] else None,
            "expiry_date": str(m["expiry_date"]) if m["expiry_date"] else None,
            "committed": committed, "delivered": delivered, "remaining": remaining,
            "pct": delivered / committed * 100 if committed > _EPS else None, "expired": expired,
            "expired_short": max(0.0, left - annex_open) if expired else 0.0,
            "after_year": after_year}


def finalize(b: dict[str, Any]) -> dict[str, Any]:
    """Tính lại các ô SUY RA từ số cộng dồn — gọi lại được sau khi gộp đơn vị sáp nhập.

    Tỷ lệ phải chia lại trên tổng: cộng hai tỷ lệ (như phép gộp `sum_deep` làm với mọi số) là sai.
    """
    lt_remaining = b["master_remaining"] + b["lt_unlinked_undelivered"]
    committed = b["master_committed"]
    return {**b, "lt_remaining": lt_remaining,
            "to_deliver": (b["spot_undelivered"] + b["principle_undelivered"] + lt_remaining
                           + b["unknown_undelivered"]),
            "master_pct": b["master_delivered"] / committed * 100 if committed > _EPS else None,
            "items": sorted(b["items"], key=lambda i: -i["remaining"]),
            "masters": len(b["items"])}


def backlog_on(as_of: str, companies: list[str] | None = None,
               grades: list[str] | None = None, *,
               block3: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: Backlog} tại ngày `as_of` (YYYY-MM-DD) — khuôn ở `plans/260926-…/api-contract.md`.

    `block3` = kết quả `undelivered_on(as_of, companies, grades)` CHƯA gộp sáp nhập, truyền vào khi
    nơi gọi đã có sẵn (router tiêu thụ cần cả hai) để khỏi quét lại khối 3 lần nữa.
    """
    if companies is not None and not companies:
        return {}
    if block3 is None:
        block3 = sales_contract_report.undelivered_on(as_of, companies, grades)
    masters = _masters(as_of, companies, grades)
    counted = {m["id"] for m in masters}

    out: dict[str, dict[str, Any]] = {}
    annex_open: dict[int, float] = {}
    for company, acc in block3.items():
        for it in acc.get("items") or []:
            mid = it.get("master_id")
            if mid in counted:          # phụ lục của HĐ mẹ được tính → chỉ góp ở cấp HĐ mẹ
                annex_open[mid] = annex_open.get(mid, 0.0) + it["remaining"]
                continue
            key = _BUCKET.get(it.get("contract_group") or "", "unknown_undelivered")
            acc = out.setdefault(company, _empty())
            acc[key] += it["remaining"]
            # HĐ loại dài hạn mà không có HĐ mẹ là lỗi dữ liệu: không thể đối chiếu lượng đã ký
            # với cam kết HĐDH. Vẫn cộng vào nghĩa vụ giao để không làm mất số, nhưng tách riêng
            # để Dashboard báo đỏ và đơn vị phải xử lý.
            if key == "lt_unlinked_undelivered" and mid is None:
                acc["lt_missing_master_undelivered"] += it["remaining"]
                acc["lt_missing_master_items"].append({
                    "id": it["id"], "code": it["code"], "remaining": it["remaining"],
                })

    day = date.fromisoformat(as_of)
    for m in masters:
        item = _master_item(m, day, annex_open.get(m["id"], 0.0))
        if item is None:
            continue
        b = out.setdefault(m["company"], _empty())
        b["master_committed"] += item["committed"]
        b["master_delivered"] += item["delivered"]
        b["master_remaining"] += item["remaining"]
        b["master_expired_short"] += item["expired_short"]
        if item["after_year"]:
            b["master_remaining_after_year"] += item["remaining"]
        b["items"].append(item)
    return {c: finalize(b) for c, b in out.items()}


def roll(by_company: dict[str, dict[str, Any]], split_merged: bool = False,
         ) -> dict[str, dict[str, Any]]:
    """Gộp đơn vị đã sáp nhập vào đơn vị hiện hành (như cột `undelivered`), rồi tính lại tỷ lệ."""
    return {c: finalize(b) for c, b in roll_by_company(by_company, split_merged).items()}
