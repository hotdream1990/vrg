"""Rà lại SỐ ĐÃ LƯU của đơn vị thành viên: ô nào nhiều khả năng nhầm đơn vị tính / thiếu tỷ giá.

Vì sao có file này: các cảnh báo "N ô cần kiểm tra" vốn chỉ chạy TRONG form lúc đang nhập — lưu
xong đóng form là không ai thấy nữa, mà con số nhầm đơn vị tính (đồng/tấn thay vì triệu đồng/tấn)
vẫn nằm im và chảy thẳng vào báo cáo tổng hợp. Rà lại ở server rồi đưa lên bảng việc đầu màn thì
đơn vị thấy ngay khi vào hệ thống, không phải mở lại từng phiếu cũ mới biết.

Dùng CHUNG bộ biên với form (`app.core.entry_bounds` ↔ `entry-bounds.ts`) nên hai nơi nói cùng một
câu, cùng một ngưỡng. CHỈ NHẮC, không sửa gì và không chặn gì.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core import entry_bounds as eb
from app.core.db import session_scope

#: Trần số ô nhắc cho MỖI đơn vị — bảng việc là chỗ nhắc, không phải báo cáo chất lượng dữ liệu.
#: Quá dài thì người đọc bỏ qua cả bảng (đo prod 19/08/2026: cả năm chỉ 21 ô, trần này rất rộng).
MAX_PER_UNIT = 50

_DAILY_SQL = text("""
    SELECT kind, as_of, company, payload FROM unit_daily_report
     WHERE company = ANY(:units) AND as_of >= CAST(:a AS date)
     ORDER BY as_of DESC
""")

#: Đơn giá mủ nước / mủ chén đơn vị tự khai nằm ở kho giá (`fact_price`, lớp `vrg_unit`), KHÔNG nằm
#: trong payload biểu Thu mua — nhưng người nhập gõ chúng ngay trên màn Thu mua nên nhắc chung.
_PRICE_SQL = text("""
    SELECT as_of, grade AS company, price_type, price FROM fact_price
     WHERE source = 'vrg_unit' AND grade = ANY(:units) AND as_of >= CAST(:a AS date)
       AND price_type IN ('purchase', 'purchase_cup')
     ORDER BY as_of DESC
""")

_CONTRACT_SQL = text("""
    SELECT k.company, k.code, COALESCE(p.code, k.code) AS contract_code,
           COALESCE(k.delivered_at, k.sign_date, p.sign_date) AS as_of, k.lines
      FROM sales_contract k
      LEFT JOIN sales_contract p ON p.id = k.parent_id
     WHERE k.company = ANY(:units)
       AND COALESCE(k.delivered_at, k.sign_date, p.sign_date) >= CAST(:a AS date)
     ORDER BY 4 DESC
""")

_PRICE_LABEL = {"purchase": ("Mủ nước · Đơn giá thu mua", eb.PRICE_LATEX),
                "purchase_cup": ("Mủ chén · Đơn giá thu mua", eb.PRICE_CUP)}

#: 2 bảng tồn kho nhiều dòng — nhãn đúng như trên form để người đọc tìm được ô.
_STOCK_TABLES = (("stock_not_warehoused", "Tồn kho 1 · chưa nhập kho"),
                 ("stock_warehoused", "Tồn kho 2 · đã nhập kho"))


def _num(v) -> float | None:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _line_issues(rows, table: str) -> list[tuple[str, str]]:
    """Cảnh báo của một bảng nhiều dòng có {qty, price, ccy, fx} — thứ tự ô giống hệt form."""
    out: list[tuple[str, str]] = []
    for i, ln in enumerate(rows if isinstance(rows, list) else [], start=1):
        if not isinstance(ln, dict):
            continue
        at = f"{table} · dòng {i}"
        ccy, grade = ln.get("ccy"), ln.get("grade")
        checks = (
            (f"{at} · Sản lượng", eb.bound_warning(_num(ln.get("qty")), eb.TONNES_DAILY)),
            (f"{at} · Đơn giá", eb.bound_warning(_num(ln.get("price")),
                                                 eb.price_bound(ccy, grade))),
            # Thiếu tỷ giá quan trọng hơn tỷ giá ngoài biên → báo trước (giống form).
            (f"{at} · Tỷ giá", eb.fx_warning(ccy, _num(ln.get("fx")))
             or eb.bound_warning(_num(ln.get("fx")), eb.FX_USD_VND)),
        )
        out += [(w, m) for w, m in checks if m]
    return out


def _purchase(p: dict) -> list[tuple[str, str]]:
    """Biểu THU MUA. Bỏ qua ô của đơn vị nước ngoài (`price_*_local`, `fx_purchase`): mỗi nội tệ
    một thang giá khác hẳn, dùng biên USD là cảnh báo sai mọi dòng (xem `unit-daily-warnings.ts`)."""
    head = (("Mủ nước · Sản lượng thu mua",
             eb.bound_warning(_num(p.get("latex_wet")), eb.TONNES_DAILY)),
            ("Mủ chén · Sản lượng thu mua",
             eb.bound_warning(_num(p.get("coagulum")), eb.TONNES_DAILY)),
            ("Mủ dây · Sản lượng thu mua",
             eb.bound_warning(_num(p.get("lace")), eb.TONNES_DAILY)))
    return [*[(w, m) for w, m in head if m], *_line_issues(p.get("finished"), "Thu mua thành phẩm")]


def _stock(p: dict) -> list[tuple[str, str]]:
    """Biểu TỒN KHO. Hai mảng tiêu thụ cũ (`sales`/`sales_own`) CỐ Ý không rà: từ 30/07/2026 form
    không hiện chúng nữa (tiêu thụ tính từ hợp đồng), nhắc ô người dùng không nhìn thấy là bắt họ
    đi tìm một ô không tồn tại."""
    out: list[tuple[str, str]] = []
    for key, label in _STOCK_TABLES:
        for i, r in enumerate(p.get(key) or [], start=1):
            m = eb.bound_warning(_num((r or {}).get("qty")), eb.TONNES_STOCK)
            if m:
                out.append((f"{label} · dòng {i} · Số lượng", m))
    m = eb.bound_warning(_num(p.get("stock_material")), eb.TONNES_STOCK)
    if m:
        out.append(("Tồn kho · nguyên liệu chưa sản xuất", m))
    return out


def issues(units: list[str], date_from: str, editable_from: str,
           kind_editable_from: dict[str, str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """{đơn vị: các ô cần soát lại} từ `date_from`, mới nhất trước.

    `editable_from` = mốc cửa sổ nhập liệu: ô cũ hơn thì đơn vị KHÔNG tự sửa được nữa, đánh dấu
    `editable=False` để giao diện nói thẳng phải nhờ Ban TTKD — mời bấm rồi chặn ở form là hứa hão.
    `kind_editable_from` = mốc riêng theo nhóm ô (`purchase` · `stock` — hai biểu được nhập trễ hơn);
    nhóm không có mốc riêng thì dùng `editable_from`.
    """
    out: dict[str, list[dict[str, Any]]] = {u: [] for u in units}
    if not units:
        return out
    args = {"units": list(units), "a": date_from}
    with session_scope() as db:
        daily = db.execute(_DAILY_SQL, args).mappings().all()
        prices = db.execute(_PRICE_SQL, args).mappings().all()
        contracts = db.execute(_CONTRACT_SQL, args).mappings().all()

    kind_from = kind_editable_from or {}

    def add(company: str, as_of: str, kind: str, where: str, message: str,
            code: str | None = None) -> None:
        out.setdefault(company, []).append({
            "as_of": as_of, "kind": kind, "where": where, "message": message,
            "code": code, "editable": as_of >= kind_from.get(kind, editable_from),
        })

    for r in daily:
        payload = dict(r["payload"] or {})
        is_purchase = r["kind"] == "purchase"
        for where, message in (_purchase(payload) if is_purchase else _stock(payload)):
            add(r["company"], str(r["as_of"]), "purchase" if is_purchase else "stock",
                where, message)
    for r in prices:
        label, bound = _PRICE_LABEL[r["price_type"]]
        m = eb.bound_warning(_num(r["price"]), bound)
        if m:
            add(r["company"], str(r["as_of"]), "purchase", label, m)
    for r in contracts:
        for i, ln in enumerate(r["lines"] or [], start=1):
            # Tỷ giá thiếu ĐÃ có nhóm riêng trong bảng việc (rà cả năm) → ở đây chỉ soát đơn giá,
            # không nhắc hai lần cùng một lần giao.
            m = eb.bound_warning(_num(ln.get("price")),
                                 eb.price_bound(ln.get("ccy"), ln.get("grade")))
            if m:
                add(r["company"], str(r["as_of"]), "contract",
                    f"Hợp đồng {r['contract_code']} · dòng {i} · Đơn giá", m, r["code"])
    return {u: sorted(v, key=lambda x: x["as_of"], reverse=True)[:MAX_PER_UNIT]
            for u, v in out.items()}
