"""VÒNG ĐỜI HỢP ĐỒNG: chốt HOÀN THÀNH và chuyển LOẠI GIAO (chốt 05/08/2026).

Hai thao tác này đổi trạng thái của cả hợp đồng nên tách khỏi `sales_contract_repo` (chỉ lo
thêm/sửa/xoá một bản ghi) — và để mỗi file giữ đúng một việc.

1. **Hoàn thành hợp đồng** — sản lượng thực giao lệch so với hợp đồng đã ký là bình thường
   (cân hàng, hao hụt, hai bên chốt lại). Vì vậy hệ thống KHÔNG tự coi hợp đồng là xong khi giao
   đủ số: đơn vị bấm hoàn thành để chốt thời điểm kết thúc, phần chênh còn lại rời khỏi
   "đã ký HĐ chưa giao" kể từ ngày đó. Bấm nhầm thì mở lại được.

2. **Chuyển loại giao** — hợp đồng lỡ khai "giao 1 lần" nhưng thực tế giao làm nhiều đợt thì
   chuyển tại chỗ, KHÔNG phải xoá đi nhập lại. Lần giao đang nằm trên chính hợp đồng được dời
   xuống thành ĐỢT GIAO đầu tiên (giữ nguyên ngày giao, hoá đơn, thanh toán, dòng chi
   tiết), còn hợp đồng giữ lại phần cam kết. Cả hai bước nằm trong MỘT giao dịch —
   nửa chừng lỗi thì không được để hợp đồng mất dữ liệu lần giao.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import DELIVERY_TYPES
from app.services import audit_repo, sales_contract_repo as repo

#: Các ô CHỈ thuộc về một lần giao — khi hợp đồng chuyển sang giao nhiều lần thì chúng đi theo
#: đợt giao, không được để lại trên hợp đồng (để lại là sản lượng bị đếm hai lần).
_BATCH_COLS = ("delivered_at", "channel", "to_company", "invoice_no", "invoice_docs",
               "payment_date", "payment_qty", "payment_docs", "start_date")

_CLEAR_BATCH = ("delivered = false, delivered_at = NULL, channel = NULL, to_company = NULL, "
                "invoice_no = NULL, invoice_docs = '[]'::jsonb, payment_date = NULL, "
                "payment_qty = NULL, payment_docs = '[]'::jsonb, start_date = NULL")


def _load(contract_id: int, companies: list[str] | None) -> dict[str, Any]:
    c = repo.get(contract_id)
    if not c or (companies is not None and c["company"] not in companies):
        raise LookupError("Không tìm thấy hợp đồng trong phạm vi tài khoản.")
    if c["parent_id"] is not None:
        raise ValueError("Thao tác này chỉ áp dụng cho hợp đồng, không áp dụng cho đợt giao.")
    return c


def _dmy(v: str) -> str:
    return f"{v[8:10]}/{v[5:7]}/{v[:4]}"


def _last_delivery(db, contract: dict[str, Any]) -> str | None:
    """Ngày giao muộn nhất của hợp đồng (kể cả các đợt) — mốc sớm nhất được phép hoàn thành."""
    kid = db.execute(text("SELECT max(delivered_at) FROM sales_contract WHERE parent_id = :i"),
                     {"i": contract["id"]}).scalar()
    days = [d for d in (contract.get("delivered_at"), str(kid) if kid else None) if d]
    return max(days) if days else None


def set_completion(contract_id: int, completed_at: str | None, companies: list[str] | None,
                   username: str | None) -> dict[str, Any]:
    """Chốt hoàn thành (`completed_at`) hoặc MỞ LẠI hợp đồng (`completed_at=None`)."""
    before = _load(contract_id, companies)
    day: date | None = None
    if completed_at:
        try:
            day = date.fromisoformat(str(completed_at)[:10])
        except ValueError as exc:
            raise ValueError("Ngày hoàn thành không hợp lệ (YYYY-MM-DD).") from exc
        if day > date.today():
            raise ValueError("Ngày hoàn thành không thể ở tương lai — hợp đồng chưa kết thúc.")
        if before["sign_date"] and day.isoformat() < before["sign_date"]:
            raise ValueError("Ngày hoàn thành không thể trước ngày ký hợp đồng.")
    ensure_schema()
    with session_scope() as db:
        if day is not None:
            last = _last_delivery(db, before)
            if last and day.isoformat() < last:
                raise ValueError(f"Hợp đồng đã có đợt giao ngày {_dmy(last)} — ngày hoàn thành "
                                 "phải từ ngày đó trở đi.")
        db.execute(text("UPDATE sales_contract SET completed_at = CAST(:d AS date), "
                        "updated_by = :by, updated_at = now() WHERE id = :i"),
                   {"d": day.isoformat() if day else None, "by": username, "i": contract_id})
    after = repo.get(contract_id) or before
    audit_repo.log("sales_contract", "update", f"HĐ {before['code']} — "
                   + ("hoàn thành" if day else "mở lại"),
                   before=before, after=after, as_of=after.get("completed_at"),
                   company=before["company"])
    return after


def set_delivery_type(contract_id: int, delivery_type: str, companies: list[str] | None,
                      username: str | None) -> dict[str, Any]:
    """Chuyển hợp đồng giữa giao-1-lần ↔ giao-nhiều-lần, giữ nguyên dữ liệu đã nhập."""
    if delivery_type not in DELIVERY_TYPES:
        raise ValueError(f"Loại giao “{delivery_type}” không hợp lệ.")
    before = _load(contract_id, companies)
    repo.assert_open(before, "chuyển loại giao")
    if before["delivery_type"] == delivery_type:
        return before

    ensure_schema()
    with session_scope() as db:
        kids = db.execute(text("SELECT count(*) FROM sales_contract WHERE parent_id = :i"),
                          {"i": contract_id}).scalar() or 0
        if delivery_type == "single":
            if kids:
                raise ValueError(f"Hợp đồng đang có {kids} đợt giao — xoá hết đợt giao rồi mới "
                                 "chuyển về giao 1 lần.")
            db.execute(text("UPDATE sales_contract SET delivery_type = 'single', "
                            "updated_by = :by, updated_at = now() WHERE id = :i"),
                       {"by": username, "i": contract_id})
        else:
            # Có dữ liệu của một lần giao trên chính hợp đồng thì phải DỜI xuống đợt giao đầu tiên,
            # nếu xoá đi là mất hẳn lần giao đã ghi (và tiêu thụ của kỳ đó hụt theo).
            if any(before.get(k) for k in _BATCH_COLS):
                _move_delivery_to_batch(db, before, username)
            db.execute(text(f"UPDATE sales_contract SET delivery_type = 'multi', {_CLEAR_BATCH}, "
                            "updated_by = :by, updated_at = now() WHERE id = :i"),
                       {"by": username, "i": contract_id})
    after = repo.get(contract_id) or before
    audit_repo.log("sales_contract", "update",
                   f"HĐ {before['code']} — chuyển sang {DELIVERY_TYPES[delivery_type].lower()}",
                   before=before, after=after, as_of=after.get("sign_date"),
                   company=before["company"])
    return after


def _unique_code(db, company: str, base: str) -> str:
    """Số đợt giao chưa dùng trong đơn vị — số hợp đồng/đợt giao không được trùng."""
    for i in range(1, 100):
        code = f"{base}{i}"
        taken = db.execute(text("SELECT 1 FROM sales_contract WHERE company = :c "
                                "AND lower(code) = lower(:k) LIMIT 1"),
                           {"c": company, "k": code}).scalar()
        if not taken:
            return code
    raise ValueError("Không tạo được số đợt giao (đã thử 99 số) — đổi số hợp đồng rồi thử lại.")


def _move_delivery_to_batch(db, contract: dict[str, Any], username: str | None) -> None:
    """Sao lần giao đang nằm trên hợp đồng xuống một ĐỢT GIAO mới (INSERT … SELECT cho gọn + đúng).

    Bản sao giữ nguyên dòng chi tiết: đây chính là hàng đã giao. Riêng `files` (hợp đồng đã ký)
    ở lại hợp đồng vì đó là chứng từ cấp hợp đồng, không phải của đợt.
    """
    cols = ", ".join(_BATCH_COLS)
    code = _unique_code(db, contract["company"], f"{contract['code']}-Đợt ")
    db.execute(text(
        f"INSERT INTO sales_contract (company, parent_id, code, delivery_type, lines, delivered, "
        f" {cols}, note, updated_by) "
        f"SELECT company, id, :code, 'single', lines, delivered, {cols}, :note, :by "
        f"FROM sales_contract WHERE id = :i"),
        {"code": code, "note": f"Tách từ hợp đồng {contract['code']} khi chuyển sang giao nhiều lần",
         "by": username, "i": contract["id"]})
