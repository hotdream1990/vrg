"""Repository HỢP ĐỒNG BÁN HÀNG 2 CẤP (sales_contract) — nguồn duy nhất tính TIÊU THỤ.

  - `parent_id` NULL = HỢP ĐỒNG. Loại giao 'single' (giao trọn 1 lần) hoặc 'multi' (giao nhiều
    lần — hợp đồng giữ TỔNG sản lượng cam kết, nhập ĐỢT GIAO tới khi hết).
  - `parent_id` khác NULL = ĐỢT GIAO (tên cũ: phụ lục): hoá đơn · ngày giao · dòng chi tiết
    (chủng loại/số lượng/đơn giá) + 1 lần thanh toán.
  - `master_id` khác NULL = bản ghi này là PHỤ LỤC của một HỢP ĐỒNG MẸ (HĐNT/HĐDH, bảng
    `master_contract` — chốt 21/08/2026): số ở ô `code` là SỐ PHỤ LỤC và khách hàng thừa kế của
    hợp đồng mẹ. `master_id` NULL = hợp đồng đứng một mình, khai khách hàng như trước.
    ⚠ Cấp hợp đồng mẹ CHỈ là hồ sơ: tiêu thụ và "đã ký HĐ chưa giao" vẫn tính trên bảng này.

Chốt 05/08/2026 — sản lượng thực giao được phép LỆCH so với hợp đồng đã ký:
  - Tổng các đợt giao được vượt cam kết, nhưng KHÔNG quá `MAX_OVER_RATIO` (110%).
  - Giao thiếu thì đơn vị bấm **Hoàn thành hợp đồng** (`completed_at`) để phần chênh còn lại rời
    khỏi "đã ký HĐ chưa giao" — xem `sales_contract_lifecycle` và `sales_contract_report`.
Tiêu thụ = tổng các đợt ĐÃ GIAO trong kỳ (`delivered_at`); đợt chưa điền ngày giao = ĐANG CHỜ GIAO.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, contract_docs, sales_contract_calc as calc
from app.services.sales_contract_clean import clean, assert_unit_exists

logger = logging.getLogger("vrg.sales_contract")

_COLS = ("id", "company", "parent_id", "master_id", "code", "customer_id",
         "delivery_type", "contract_type",
         "sign_date", "expiry_date", "start_date", "lines", "delivered", "delivered_at", "channel",
         "to_company", "invoice_no", "invoice_docs", "payment_date", "payment_qty",
         "payment_docs", "files", "note", "completed_at")
_DATE_COLS = ("sign_date", "expiry_date", "start_date", "delivered_at", "payment_date",
              "completed_at")
_DOC_COLS = ("files", "payment_docs", "invoice_docs")

#: Trần sản lượng thực giao so với hợp đồng đã ký. Thực tế lệch quanh 5%, chặn ở 10% để vẫn bắt
#: được lỗi nhập nhầm (thêm một số 0) mà không cản nghiệp vụ bình thường.
MAX_OVER_RATIO = 1.10


def _row(r) -> dict[str, Any]:
    d = dict(r)
    for k in _DATE_COLS:
        d[k] = str(d[k]) if d.get(k) else None
    d["lines"] = d.get("lines") or []
    for k in _DOC_COLS:
        d[k] = contract_docs.normalize(d.get(k), None, None)
    d["qty"] = calc.total_qty(d["lines"])
    d["qty_dry"] = calc.total_qty_dry(d["lines"])
    d["revenue"] = calc.total_revenue_vnd(d["lines"])
    return d


def _parent_of(db, parent_id: int) -> dict[str, Any]:
    row = db.execute(text(f"SELECT {', '.join(_COLS)} FROM sales_contract WHERE id = :i"),
                     {"i": parent_id}).mappings().first()
    if row is None:
        raise ValueError("Hợp đồng không còn tồn tại (có thể đã bị xoá).")
    if row["parent_id"] is not None:
        raise ValueError("Không thể thêm đợt giao cho một đợt giao (hợp đồng chỉ có 2 cấp).")
    return _row(row)


def _batches_qty(db, parent_id: int, exclude_id: int | None) -> float:
    """Tổng sản lượng các ĐỢT GIAO đã nhập của hợp đồng (trừ chính đợt đang sửa)."""
    rows = db.execute(text("SELECT id, lines FROM sales_contract WHERE parent_id = :p"),
                      {"p": parent_id}).mappings().all()
    return sum(calc.total_qty(r["lines"] or []) for r in rows if r["id"] != exclude_id)


def assert_open(contract: dict[str, Any], what: str) -> None:
    """Hợp đồng đã HOÀN THÀNH thì khoá lại — sửa tiếp là đổi số của một kỳ đã chốt.

    Chặn ở đây (không chỉ ở nút bấm) vì đây là chỗ duy nhất mọi đường ghi đi qua.
    """
    if contract.get("completed_at"):
        d = str(contract["completed_at"])
        raise ValueError(
            f"Hợp đồng {contract.get('code')} đã hoàn thành ngày "
            f"{d[8:10]}/{d[5:7]}/{d[:4]} — bấm “Mở lại hợp đồng” trước khi {what}.")


_INSERT = text(
    "INSERT INTO sales_contract (company, parent_id, master_id, code, customer_id, "
    " delivery_type, contract_type, sign_date, "
    " expiry_date, start_date, lines, delivered, delivered_at, channel, to_company, "
    " invoice_no, invoice_docs, payment_date, "
    " payment_qty, payment_docs, files, note, updated_by) "
    "VALUES (:company, :parent_id, :master_id, :code, :customer_id, :delivery_type, "
    " :contract_type, "
    " CAST(:sign_date AS date), "
    " CAST(:expiry_date AS date), CAST(:start_date AS date), CAST(:lines AS jsonb), :delivered, "
    " CAST(:delivered_at AS date), "
    " :channel, :to_company, :invoice_no, CAST(:invoice_docs AS jsonb), "
    " CAST(:payment_date AS date), :payment_qty, "
    " CAST(:payment_docs AS jsonb), CAST(:files AS jsonb), :note, :by) RETURNING id")

_UPDATE = text(
    "UPDATE sales_contract SET code = :code, master_id = :master_id, "
    " customer_id = :customer_id, "
    " delivery_type = :delivery_type, contract_type = :contract_type, "
    " sign_date = CAST(:sign_date AS date), "
    " expiry_date = CAST(:expiry_date AS date), start_date = CAST(:start_date AS date), "
    " lines = CAST(:lines AS jsonb), "
    " delivered = :delivered, delivered_at = CAST(:delivered_at AS date), channel = :channel, "
    " to_company = :to_company, invoice_no = :invoice_no, "
    " invoice_docs = CAST(:invoice_docs AS jsonb), "
    " payment_date = CAST(:payment_date AS date), "
    " payment_qty = :payment_qty, "
    " payment_docs = CAST(:payment_docs AS jsonb), files = CAST(:files AS jsonb), note = :note, "
    " updated_by = :by, updated_at = now() WHERE id = :id")


def _params(d: dict, updated_by: str | None) -> dict[str, Any]:
    docs = {k: json.dumps(d[k]) for k in _DOC_COLS}
    return {**d, **docs, "lines": json.dumps(d["lines"]), "by": updated_by}


def _tan(v: float) -> str:
    """Số tấn theo kiểu Việt: dấu chấm ngăn nghìn, dấu phẩy thập phân.
    Đổi thẳng ',' → '.' như trước làm 50,000.000 thành 50.000.000 → người đọc hiểu là 50 TRIỆU tấn."""
    return f"{v:,.3f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _assert_within_cap(total: float, committed: float, what: str) -> None:
    """Sản lượng thực giao được vượt hợp đồng, nhưng không quá `MAX_OVER_RATIO`.

    Thực tế cân hàng lệch quanh 5% so với hợp đồng ký nên chặn đúng 100% là chặn nghiệp vụ thật
    (chốt 05/08/2026). Vẫn phải có trần: không có trần thì gõ nhầm 1.000 thành 10.000 tấn cũng lọt.
    """
    cap = committed * MAX_OVER_RATIO
    if total > cap + 1e-9:
        raise ValueError(
            f"{what} ({_tan(total)} tấn) vượt quá {MAX_OVER_RATIO:.0%} sản lượng hợp đồng "
            f"({_tan(committed)} tấn — tối đa {_tan(cap)} tấn). Sửa lại số lượng, hoặc sửa sản "
            "lượng trên hợp đồng nếu hai bên đã thống nhất tăng.")


def save(row: dict, company: str, updated_by: str | None) -> dict[str, Any]:
    """Thêm mới (không có id) hoặc cập nhật. Raise ValueError nếu vi phạm nghiệp vụ."""
    d = clean(row, company)
    assert_unit_exists(company, "Đơn vị")
    ensure_schema()
    before = get(d["id"]) if d["id"] is not None else None
    with session_scope() as db:
        if d["id"] is not None:
            cur = db.execute(text("SELECT company, parent_id, delivery_type, code, completed_at "
                                  "FROM sales_contract WHERE id = :i"),
                             {"i": d["id"]}).mappings().first()
            if cur is None:
                raise ValueError("Hợp đồng không còn tồn tại (có thể đã bị xoá).")
            if cur["company"] != company:
                raise ValueError("Hợp đồng thuộc đơn vị khác.")
            assert_open(dict(cur), "sửa")
            # Cấp bậc KHÔNG đổi được khi sửa: `_UPDATE` không ghi `parent_id`, nên nhận `parent_id`
            # khác trong payload sẽ kiểm hạn mức trên HỢP ĐỒNG KHÁC rồi vẫn nằm ở hợp đồng cũ —
            # lách được giới hạn sản lượng. Muốn chuyển sang hợp đồng khác thì xoá rồi nhập lại.
            if (d["parent_id"] or None) != (cur["parent_id"] or None):
                raise ValueError("Không đổi được hợp đồng của đợt giao — xoá rồi nhập lại đợt giao.")
            kids = db.execute(text("SELECT count(*) FROM sales_contract WHERE parent_id = :i"),
                              {"i": d["id"]}).scalar() or 0
            # Đổi loại giao khi ĐÃ có đợt giao phải đi qua `sales_contract_lifecycle` (nó dời lần
            # giao vào một đợt), không để form sửa thẳng — sửa thẳng là mất/đếm đôi sản lượng.
            if kids and d["delivery_type"] != cur["delivery_type"]:
                raise ValueError(f"Hợp đồng đang có {kids} đợt giao — dùng nút “Chuyển loại giao” "
                                 "ở màn chi tiết hợp đồng.")
            if kids and d["delivered"]:
                raise ValueError("Hợp đồng giao nhiều lần đã có đợt giao — không tự đánh dấu đã "
                                 "giao (sản lượng sẽ bị tính hai lần).")
            if kids:
                _assert_within_cap(_batches_qty(db, d["id"], None), calc.total_qty(d["lines"]),
                                   "Tổng các đợt giao")
        # Trùng số → chặn: lưu lại do mạng chập chờn sẽ nhân đôi sản lượng. Phạm vi kiểm phải theo
        # ĐÚNG cấp: số hợp đồng là duy nhất trong ĐƠN VỊ, còn số đợt giao đánh lại từ 1 ở MỖI hợp
        # đồng — kiểm cả đơn vị thì đợt "2" của hợp đồng này đụng đợt "2" của hợp đồng khác.
        dup = db.execute(text(
            "SELECT 1 FROM sales_contract WHERE lower(code) = lower(:k) "
            " AND ((CAST(:p AS bigint) IS NULL AND parent_id IS NULL AND company = :c) "
            "   OR (CAST(:p AS bigint) IS NOT NULL AND parent_id = CAST(:p AS bigint))) "
            " AND (CAST(:i AS bigint) IS NULL OR id <> CAST(:i AS bigint)) LIMIT 1"),
            {"c": company, "p": d["parent_id"], "k": d["code"], "i": d["id"]}).scalar()
        if dup:
            raise ValueError(f"Hợp đồng này đã có đợt giao số “{d['code']}”."
                             if d["parent_id"] is not None else
                             f"Đơn vị đã có hợp đồng số “{d['code']}”.")

        if d["parent_id"] is not None:
            parent = _parent_of(db, d["parent_id"])
            if parent["company"] != company:
                raise ValueError("Hợp đồng thuộc đơn vị khác.")
            if parent["delivery_type"] != "multi":
                raise ValueError("Chỉ hợp đồng loại “giao nhiều lần” mới thêm được đợt giao.")
            assert_open(parent, "thêm/sửa đợt giao")
            if parent["sign_date"] and d["delivered_at"] and d["delivered_at"] < parent["sign_date"]:
                raise ValueError("Ngày giao của đợt không thể trước ngày ký hợp đồng.")
            done = _batches_qty(db, d["parent_id"], d["id"])
            _assert_within_cap(done + calc.total_qty(d["lines"]), parent["qty"], "Tổng các đợt giao")
        if d["id"] is not None:
            db.execute(_UPDATE, _params(d, updated_by))
            new_id = d["id"]
        else:
            new_id = db.execute(_INSERT, _params(d, updated_by)).scalar()
    saved = get(new_id) or {**d, "id": new_id}
    label = ("Đợt giao " if d["parent_id"] else "HĐ ") + d["code"]
    audit_repo.log("sales_contract", "update" if before else "create", label,
                   before=before, after=saved, as_of=saved.get("delivered_at") or saved.get("sign_date"),
                   company=company)
    _sync_group_inventory()
    return saved


def get(contract_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(f"SELECT {', '.join(_COLS)} FROM sales_contract WHERE id = :i"),
                         {"i": contract_id}).mappings().first()
    return _row(row) if row else None


def companies_of_file(name: str) -> set[str]:
    """Các đơn vị có hợp đồng/đợt giao đính kèm file này — để chặn tải chéo đơn vị.

    File lưu chung một thư mục phẳng theo tên uuid; không kiểm thì bất kỳ tài khoản nào biết tên
    file đều tải được bản scan hợp đồng của đơn vị khác. Phải quét ĐỦ 4 ô đính kèm — thiếu ô nào
    thì file của ô đó không tải được (endpoint trả 404 "không tìm thấy file hợp đồng").
    """
    ensure_schema()
    match = " OR ".join(f"{c} @> CAST(:f AS jsonb)" for c in _DOC_COLS)
    with session_scope() as db:
        rows = db.execute(text(f"SELECT DISTINCT company FROM sales_contract WHERE {match}"),
                          {"f": json.dumps([{"file": name}])}).scalars().all()
    return set(rows)


def children(parent_id: int) -> list[dict[str, Any]]:
    """Các ĐỢT GIAO của 1 hợp đồng, sắp theo ngày giao (đợt chưa giao xuống cuối)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT {', '.join(_COLS)} FROM sales_contract WHERE parent_id = :p "
                 "ORDER BY delivered_at NULLS LAST, id"), {"p": parent_id}).mappings().all()
    return [_row(r) for r in rows]


def delete(contract_id: int, companies: list[str] | None) -> bool:
    """Xoá 1 hợp đồng / đợt giao. Hợp đồng còn đợt giao thì phải xoá các đợt trước."""
    ensure_schema()
    before = get(contract_id)
    with session_scope() as db:
        cur = db.execute(text("SELECT company FROM sales_contract WHERE id = :i"),
                         {"i": contract_id}).scalar()
        if cur is None or (companies is not None and cur not in companies):
            return False
        if before:
            assert_open(before, "xoá")
            # Xoá một đợt của hợp đồng đã chốt cũng bị chặn — nếu không, sản lượng đã hoàn thành
            # tự dưng hụt đi mà hợp đồng vẫn ở trạng thái "đã xong".
            if before.get("parent_id"):
                assert_open(get(before["parent_id"]) or {}, "xoá đợt giao")
        kids = db.execute(text("SELECT count(*) FROM sales_contract WHERE parent_id = :i"),
                          {"i": contract_id}).scalar() or 0
        if kids:
            raise ValueError(f"Hợp đồng còn {kids} đợt giao — xoá các đợt giao trước.")
        db.execute(text("DELETE FROM sales_contract WHERE id = :i"), {"i": contract_id})
    audit_repo.log("sales_contract", "delete", (before or {}).get("code") or f"#{contract_id}",
                   before=before, as_of=(before or {}).get("sign_date"), company=cur)
    _sync_group_inventory()
    return True


def _sync_group_inventory() -> None:
    """Hợp đồng/đợt giao đổi → tính lại phần "đã có HĐ" của tuần đang chạy ở Tồn kho Tập đoàn.

    Chỉ chạy khi chuyên viên đã bật tự tính; lỗi ở đây không được làm hỏng thao tác lưu hợp đồng.
    """
    from app.services import inventory_auto

    try:
        inventory_auto.sync_current_week()
    except Exception as exc:                       # noqa: BLE001 - không chặn luồng nhập liệu
        logger.warning("Không cập nhật được tồn kho Tập đoàn: %s", exc)
