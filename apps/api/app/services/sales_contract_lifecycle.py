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
from app.services import audit_repo, sales_contract_lock, sales_contract_repo as repo

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
                   username: str | None, delivery: dict[str, Any] | None = None) -> dict[str, Any]:
    """Chốt hoàn thành (`completed_at`) hoặc MỞ LẠI hợp đồng (`completed_at=None`).

    HỢP ĐỒNG GIAO 1 LẦN CHƯA CÓ NGÀY GIAO (chốt 27/08/2026): chốt hoàn thành chính là ghi nhận
    ĐÃ GIAO — ghi luôn ngày giao (mặc định = ngày hoàn thành) + hình thức tiêu thụ, để đơn vị khỏi
    phải làm hai bước và khỏi hiểu nhầm "Hoàn thành" là cách khai đã giao. Đơn vị Thanh Hoá từng
    mất 198,66 tấn khỏi tiêu thụ vì hiểu nhầm đúng chỗ này.

    ⚠ Hợp đồng HUỶ / không giao nữa phải gửi `no_delivery=True`: tự gán ngày giao cho hợp đồng huỷ
    là đẻ ra tiêu thụ ảo — lỗi ngược lại, cũng sai như nhau. Thiếu cả hai thì BÁO LỖI chứ không tự
    chọn hộ.
    """
    before = _load(contract_id, companies)
    delivery = delivery or {}
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
    # Ghi lần giao TRƯỚC khi chốt: hợp đồng đã chốt thì `repo.save` khoá không cho sửa nữa.
    if (day is not None and before.get("delivery_type") == "single"
            and not before.get("delivered_at") and not before.get("parent_id")):
        if delivery.get("no_delivery"):
            pass                                   # huỷ/không giao — chốt suông, không ghi gì thêm
        elif not delivery.get("channel"):
            raise ValueError(
                "Hợp đồng giao 1 lần chưa có ngày giao. Chọn Hình thức tiêu thụ để chốt hoàn thành "
                "và ghi nhận đã giao; nếu hợp đồng huỷ / không giao nữa thì tích ô "
                "“không ghi lần giao”.")
        else:
            delivered_at = delivery.get("delivered_at") or day.isoformat()
            # Ghi ngày giao ở đây cũng là KHAI LẦN GIAO → phải qua đúng hai hàng rào thời gian như
            # khi nhập đợt giao bình thường (cửa sổ sửa + chốt số liệu). Trước 17/09/2026 bước này
            # không kiểm gì: đặt cửa sổ 0 ngày, đơn vị vẫn chốt được hợp đồng với ngày giao lùi
            # 10 ngày, tức là ghi sản lượng vào kỳ đã qua — kể cả kỳ đã chốt.
            if username:
                sales_contract_lock.assert_delivery_fences(
                    username, contract_id, delivered_at, before["company"], old=before)
            repo.save({**before,
                       "delivered_at": delivered_at,
                       "channel": delivery["channel"],
                       "to_company": delivery.get("to_company")},
                      before["company"], username)
            before = _load(contract_id, companies)

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


def assert_switchable(contract: dict[str, Any], delivery_type: str, kids: int | None = None) -> None:
    """Luật của việc CHUYỂN LOẠI GIAO — chỉ kiểm, KHÔNG ghi gì.

    Tách riêng để luồng «Đề nghị sửa» (`edit_request_ops_contract`) kiểm y hệt lúc đơn vị GỬI và
    lúc Ban mở đề nghị ra xem — không để bấm Duyệt rồi mới biết vướng. `kids` = số đợt giao đã đếm
    sẵn trong giao dịch ghi thật; None thì tự đếm.
    """
    if delivery_type not in DELIVERY_TYPES:
        raise ValueError(f"Loại giao “{delivery_type}” không hợp lệ.")
    if contract.get("parent_id") is not None:
        raise ValueError("Thao tác này chỉ áp dụng cho hợp đồng, không áp dụng cho đợt giao.")
    repo.assert_open(contract, "chuyển loại giao")
    if delivery_type == "single":
        n = len(repo.children(contract["id"])) if kids is None else kids
        if n:
            raise ValueError(f"Hợp đồng đang có {n} đợt giao — xoá hết đợt giao rồi mới "
                             "chuyển về giao 1 lần.")


def set_delivery_type(contract_id: int, delivery_type: str, companies: list[str] | None,
                      username: str | None) -> dict[str, Any]:
    """Chuyển hợp đồng giữa giao-1-lần ↔ giao-nhiều-lần, giữ nguyên dữ liệu đã nhập."""
    before = _load(contract_id, companies)
    if before["delivery_type"] == delivery_type:
        return before

    ensure_schema()
    with session_scope() as db:
        kids = db.execute(text("SELECT count(*) FROM sales_contract WHERE parent_id = :i"),
                          {"i": contract_id}).scalar() or 0
        assert_switchable(before, delivery_type, kids=kids)
        if delivery_type == "single":
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


def _unique_code(db, parent_id: int, base: str) -> str:
    """Số đợt giao chưa dùng TRONG HỢP ĐỒNG này — số đợt chỉ cần duy nhất ở phạm vi hợp đồng."""
    for i in range(1, 100):
        code = f"{base}{i}"
        taken = db.execute(text("SELECT 1 FROM sales_contract WHERE parent_id = :p "
                                "AND lower(code) = lower(:k) LIMIT 1"),
                           {"p": parent_id, "k": code}).scalar()
        if not taken:
            return code
    raise ValueError("Không tạo được số đợt giao (đã thử 99 số) — đổi số hợp đồng rồi thử lại.")


def _move_delivery_to_batch(db, contract: dict[str, Any], username: str | None) -> None:
    """Sao lần giao đang nằm trên hợp đồng xuống một ĐỢT GIAO mới (INSERT … SELECT cho gọn + đúng).

    Bản sao giữ nguyên dòng chi tiết: đây chính là hàng đã giao. Riêng `files` (hợp đồng đã ký)
    ở lại hợp đồng vì đó là chứng từ cấp hợp đồng, không phải của đợt. Ngày hiệu lực của dòng
    (`from_date`) cũng ở lại hợp đồng — đợt giao không có ô này, ngày của đợt là ngày giao.
    """
    cols = ", ".join(_BATCH_COLS)
    code = _unique_code(db, contract["id"], f"{contract['code']}-Đợt ")
    batch_lines = ("(SELECT COALESCE(jsonb_agg(e.v - 'from_date' ORDER BY e.n), '[]'::jsonb) "
                   "FROM jsonb_array_elements(COALESCE(lines, '[]'::jsonb)) "
                   "WITH ORDINALITY AS e(v, n))")
    db.execute(text(
        f"INSERT INTO sales_contract (company, parent_id, code, delivery_type, lines, delivered, "
        f" {cols}, note, updated_by) "
        f"SELECT company, id, :code, 'single', {batch_lines}, delivered, {cols}, :note, :by "
        f"FROM sales_contract WHERE id = :i"),
        {"code": code, "note": f"Tách từ hợp đồng {contract['code']} khi chuyển sang giao nhiều lần",
         "by": username, "i": contract["id"]})
