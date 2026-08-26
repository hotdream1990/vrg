"""Repository HỢP ĐỒNG MẸ (master_contract) — HĐ nguyên tắc (HĐNT) / HĐ dài hạn (HĐDH).

Hợp đồng mẹ là HỒ SƠ GỐC ký với khách hàng: khách hàng · cam kết chủng loại/số lượng/đơn giá ·
công thức giá · bản scan. Từng chuyến hàng vẫn nhập ở `sales_contract` (gọi là PHỤ LỤC khi có
`master_id`), và **mọi báo cáo sản lượng chỉ đọc `sales_contract`** — bảng này không góp số vào
tiêu thụ hay "đã ký HĐ chưa giao", nếu không sản lượng bị đếm hai lần.

Ràng buộc: số hợp đồng duy nhất trong đơn vị (unique index `ux_master_contract_code`), và không
xoá được khi còn phụ lục trỏ về (phụ lục sẽ mất khách hàng đang thừa kế).
Việc NỐI/GỠ phụ lục nằm ở `master_contract_annexes` (kể cả hàm liệt kê phụ lục của một hồ sơ).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core import vn_text
from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, contract_docs
from app.services.master_contract_clean import clean
from app.services.sales_contract_report import _QTY_SQL

_COLS = ("id", "company", "code", "master_type", "customer_id", "sign_date", "expiry_date",
         "lines", "price_formula", "files", "note", "certs", "premium", "premium_ccy")
_DATE_COLS = ("sign_date", "expiry_date")

#: Tiến độ ký phụ lục — đếm phụ lục và cộng sản lượng ĐÃ KÝ của chúng (số trên hợp đồng, dùng
#: `_QTY_SQL` để ra đúng con số `calc.total_qty`). Đợt giao (`parent_id` khác NULL) không tính:
#: nó nằm bên trong phụ lục, cộng vào là đếm hai lần.
_ANNEX_SQL = """
    SELECT master_id, count(*) AS annexes,
           COALESCE(sum(%s), 0) AS annex_qty
      FROM sales_contract
     WHERE master_id IS NOT NULL AND parent_id IS NULL
     GROUP BY master_id
""" % (_QTY_SQL % "lines")


def _row(r) -> dict[str, Any]:
    d = dict(r)
    d.pop("total", None)
    for k in _DATE_COLS:
        d[k] = str(d[k]) if d.get(k) else None
    d["lines"] = d.get("lines") or []
    d["certs"] = d.get("certs") or []
    d["files"] = contract_docs.normalize(d.get("files"), None, None)
    d["qty"] = sum(float(ln.get("qty") or 0) for ln in d["lines"])
    for k in ("annexes", "annex_qty"):
        if k in d:
            d[k] = (int(d[k] or 0) if k == "annexes" else float(d[k] or 0))
    return d


def list_masters(companies: list[str] | None = None, *, company: str | None = None,
                 q: str | None = None, master_type: str | None = None,
                 customer_ids: list[int] | None = None, ids: list[int] | None = None,
                 limit: int | None = None, offset: int = 0) -> dict[str, Any]:
    """MỘT TRANG hợp đồng mẹ kèm số phụ lục đã ký → `{items, total}`.

    `companies` là PHẠM VI QUYỀN do server ép (None = mọi đơn vị); `company` là bộ lọc người dùng
    chọn thêm. `ids` để tra lại nhãn của hợp đồng mẹ đang chọn ở ô tìm kiếm.
    """
    ensure_schema()
    where, params = ["1 = 1"], {}
    if companies is not None:
        if not companies:
            return {"items": [], "total": 0}
        where.append("m.company = ANY(:cs)")
        params["cs"] = list(companies)
    if company:
        where.append("m.company = :co")
        params["co"] = company
    if master_type:
        where.append("m.master_type = :mt")
        params["mt"] = master_type
    if customer_ids:
        where.append("m.customer_id = ANY(:cu)")
        params["cu"] = list(customer_ids)
    if ids is not None:
        if not ids:
            return {"items": [], "total": 0}
        where.append("m.id = ANY(:ids)")
        params["ids"] = [int(i) for i in ids]
    if q:
        # Tìm KHÔNG DẤU (giống ô khách hàng): số hợp đồng không dấu, nhưng ghi chú thì có dấu.
        cols = " OR ".join(f"{vn_text.fold_sql('m.' + c)} LIKE :q" for c in ("code", "note"))
        where.append(f"({cols})")
        params.update(vn_text.FOLD_PARAMS)
        params["q"] = f"%{vn_text.fold(q)}%"
    sql = (f"SELECT {', '.join('m.' + c for c in _COLS)}, "
           " COALESCE(a.annexes, 0) AS annexes, COALESCE(a.annex_qty, 0) AS annex_qty, "
           " count(*) OVER () AS total "
           f"FROM master_contract m LEFT JOIN ({_ANNEX_SQL}) a ON a.master_id = m.id "
           f"WHERE {' AND '.join(where)} ORDER BY m.sign_date DESC NULLS LAST, m.id DESC")
    if limit:
        sql += " LIMIT :lim OFFSET :off"
        params["lim"], params["off"] = int(limit), max(0, int(offset))
    with session_scope() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return {"items": [_row(r) for r in rows],
            "total": int(rows[0]["total"]) if rows else 0}


def get(master_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(f"SELECT {', '.join(_COLS)} FROM master_contract WHERE id = :i"),
                         {"i": master_id}).mappings().first()
    return _row(row) if row else None


def codes_by_id(companies: list[str] | None = None,
                ids: list[int] | None = None) -> dict[int, str]:
    """{id: số hợp đồng mẹ} — gắn nhãn vào danh sách hợp đồng mà không join thêm ở câu chính."""
    if not ids:
        return {}
    return {m["id"]: m["code"] for m in list_masters(companies, ids=ids)["items"]}


def companies_of_file(name: str) -> set[str]:
    """Các đơn vị có hợp đồng mẹ đính kèm file này — để chặn tải file chéo đơn vị.

    File dùng CHUNG thư mục lưu trữ với hợp đồng bán hàng, nên endpoint tải file phải hỏi cả hai
    bảng; thiếu hàm này thì bản scan của hợp đồng mẹ luôn trả 404.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT DISTINCT company FROM master_contract "
                 "WHERE files @> CAST(:f AS jsonb)"),
            {"f": json.dumps([{"file": name}])}).scalars().all()
    return set(rows)


_INSERT = text(
    "INSERT INTO master_contract (company, code, master_type, customer_id, sign_date, "
    " expiry_date, lines, price_formula, files, note, certs, premium, premium_ccy, updated_by) "
    "VALUES (:company, :code, :master_type, :customer_id, CAST(:sign_date AS date), "
    " CAST(:expiry_date AS date), CAST(:lines AS jsonb), :price_formula, CAST(:files AS jsonb), "
    " :note, CAST(:certs AS jsonb), :premium, :premium_ccy, :by) RETURNING id")

_UPDATE = text(
    "UPDATE master_contract SET code = :code, master_type = :master_type, "
    " customer_id = :customer_id, sign_date = CAST(:sign_date AS date), "
    " expiry_date = CAST(:expiry_date AS date), lines = CAST(:lines AS jsonb), "
    " price_formula = :price_formula, files = CAST(:files AS jsonb), note = :note, "
    " certs = CAST(:certs AS jsonb), premium = :premium, premium_ccy = :premium_ccy, "
    " updated_by = :by, updated_at = now() WHERE id = :id")


def save(row: dict, company: str, updated_by: str | None) -> dict[str, Any]:
    """Thêm mới (không có id) hoặc cập nhật 1 hợp đồng mẹ. Raise ValueError nếu sai nghiệp vụ."""
    from app.services.sales_contract_clean import assert_unit_can_sign, assert_unit_exists

    d = clean(row, company)
    assert_unit_exists(company, "Đơn vị")
    if d["id"] is None:      # hồ sơ MỚI — đơn vị đã sáp nhập thì mở hồ sơ ở đơn vị nhận
        assert_unit_can_sign(company, "Đơn vị")
    ensure_schema()
    before = get(d["id"]) if d["id"] is not None else None
    params = {**d, "lines": json.dumps(d["lines"]), "files": json.dumps(d["files"]),
              "certs": json.dumps(d["certs"]), "by": updated_by}
    try:
        with session_scope() as db:
            if d["id"] is not None:
                cur = db.execute(text("SELECT company FROM master_contract WHERE id = :i"),
                                 {"i": d["id"]}).scalar()
                if cur is None:
                    raise ValueError("Hợp đồng mẹ không còn tồn tại (có thể đã bị xoá).")
                if cur != company:
                    raise ValueError("Hợp đồng mẹ thuộc đơn vị khác.")
                db.execute(_UPDATE, params)
                new_id = d["id"]
            else:
                new_id = db.execute(_INSERT, params).scalar()
    except IntegrityError as exc:
        raise ValueError(f"Đơn vị đã có hợp đồng mẹ số “{d['code']}”.") from exc
    saved = get(new_id) or {**d, "id": new_id}
    audit_repo.log("master_contract", "update" if before else "create", f"HĐ mẹ {d['code']}",
                   before=before, after=saved, as_of=saved.get("sign_date"), company=company)
    return saved


def delete(master_id: int, companies: list[str] | None) -> bool:
    """Xoá 1 hợp đồng mẹ. Chặn khi còn phụ lục — gỡ nối ở từng phụ lục trước."""
    ensure_schema()
    before = get(master_id)
    with session_scope() as db:
        cur = db.execute(text("SELECT company FROM master_contract WHERE id = :i"),
                         {"i": master_id}).scalar()
        if cur is None or (companies is not None and cur not in companies):
            return False
        used = db.execute(text("SELECT count(*) FROM sales_contract WHERE master_id = :i"),
                          {"i": master_id}).scalar() or 0
        if used:
            raise ValueError(f"Hợp đồng mẹ đang có {used} phụ lục — bỏ chọn hợp đồng mẹ ở các "
                             "phụ lục đó trước khi xoá.")
        db.execute(text("DELETE FROM master_contract WHERE id = :i"), {"i": master_id})
    audit_repo.log("master_contract", "delete", (before or {}).get("code") or f"#{master_id}",
                   before=before, as_of=(before or {}).get("sign_date"), company=cur)
    return True
