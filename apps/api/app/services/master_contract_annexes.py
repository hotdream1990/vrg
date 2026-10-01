"""NỐI / GỠ PHỤ LỤC cho hợp đồng mẹ (chốt 22/08/2026) — chiều ngược của ô "Hợp đồng mẹ" ở form.

Hai đường vào cùng một quan hệ `sales_contract.master_id`:
  1. Lúc nhập hợp đồng: chọn hợp đồng mẹ ngay trên form (xem `sales_contract_clean`).
  2. Ở màn hợp đồng mẹ: **chọn hợp đồng ĐÃ CÓ rồi gắn vào** — cần cho việc dọn hồ sơ cũ, vì
     prod đang có hàng nghìn hợp đồng nhập trước khi có cấp hợp đồng mẹ.

⚠ Gắn/gỡ KHÔNG đụng tới số liệu của hợp đồng (khách hàng, sản lượng…). Bản đầu từng ghi đè khách
hàng theo hợp đồng mẹ — gắn một hợp đồng cũ vào hồ sơ là lặng lẽ đổi số liệu "theo khách hàng" của
một kỳ đã chốt. NGOẠI LỆ duy nhất là LOẠI hợp đồng (chốt 01/10/2026): GẮN thì thành "Phụ lục hợp đồng
mẹ" — HĐ chuyến không có hợp đồng mẹ; để nguyên "HĐ chuyến" thì form sửa chặn mà không có ô nào gỡ
(76 hợp đồng từng kẹt như vậy). GỠ thì về "chưa khai loại" (hiện riêng trên báo cáo, đơn vị chọn lại)
— để nguyên "Phụ lục" là lặng lẽ dồn hợp đồng vào cột dài hạn. Loại cũ ghi vào nhật ký hoạt động.
Báo cáo xếp nhóm theo hồ sơ mẹ (`sales_contract_group`) nên gắn/gỡ có thể dời sản lượng giữa cột chuyến ·
HĐNT · dài hạn → hợp đồng có lần giao trong kỳ đã chốt thì tài khoản đơn vị bị chặn.

Tách khỏi `master_contract_repo` cho mỗi file một việc (giống `sales_contract_lifecycle` tách khỏi
`sales_contract_repo`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo
from app.services import sales_contract_group as grp

_MAX_LINK = 200      # trần một lượt gắn — tránh bấm nhầm kéo cả nghìn hợp đồng vào một hồ sơ


def annexes(master_id: int) -> list[dict[str, Any]]:
    """Các PHỤ LỤC đã nối về hợp đồng mẹ này (KHÔNG gồm đợt giao bên trong từng phụ lục)."""
    from app.services.sales_contract_repo import _COLS, _row

    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT {', '.join(_COLS)} FROM sales_contract "
                 "WHERE master_id = :m AND parent_id IS NULL "
                 "ORDER BY sign_date DESC NULLS LAST, id DESC"), {"m": master_id}).mappings().all()
    return [_row(r) for r in rows]


def _ids(contract_ids) -> list[int]:
    """Danh sách id hợp lệ, bỏ trùng, giữ thứ tự người dùng chọn."""
    out: list[int] = []
    for v in contract_ids or []:
        s = str(v if v is not None else "").strip()
        if not s.isdigit() or int(s) <= 0:
            raise ValueError("Danh sách hợp đồng có mã không hợp lệ.")
        if int(s) not in out:
            out.append(int(s))
    if not out:
        raise ValueError("Chưa chọn hợp đồng nào.")
    if len(out) > _MAX_LINK:
        raise ValueError(f"Mỗi lượt chỉ gắn được tối đa {_MAX_LINK} hợp đồng.")
    return out


def _assert_linkable(rows, master: dict[str, Any], attach: bool) -> None:
    """Kiểm từng hợp đồng trước khi ghi — sai một cái là dừng cả lượt (không gắn nửa vời)."""
    for r in rows:
        code = r["code"]
        if r["company"] != master["company"]:
            raise ValueError(f"Hợp đồng “{code}” thuộc đơn vị khác — hợp đồng mẹ và phụ lục phải "
                             "cùng một đơn vị.")
        if r["parent_id"] is not None:
            raise ValueError(f"“{code}” là ĐỢT GIAO nằm trong một hợp đồng, không gắn thẳng vào "
                             "hợp đồng mẹ được.")
        if attach and r["master_id"] not in (None, master["id"]):
            raise ValueError(f"Hợp đồng “{code}” đang là phụ lục của một hợp đồng mẹ khác — gỡ ở "
                             "hồ sơ đó trước khi gắn sang đây.")
        if not attach and r["master_id"] != master["id"]:
            raise ValueError(f"Hợp đồng “{code}” không phải phụ lục của hợp đồng mẹ này.")


def link(master_id: int, contract_ids, attach: bool, companies: list[str] | None,
         updated_by: str | None) -> dict[str, Any]:
    """Gắn (`attach=True`) hoặc gỡ các hợp đồng khỏi hợp đồng mẹ. Raise ValueError nếu sai."""
    from app.services import master_contract_repo

    master = master_contract_repo.get(master_id)
    if not master or (companies is not None and master["company"] not in companies):
        raise LookupError("Không tìm thấy hợp đồng mẹ trong phạm vi tài khoản.")
    ids = _ids(contract_ids)
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT id, company, code, parent_id, master_id, customer_id, "
                               "contract_type FROM sales_contract WHERE id = ANY(:ids)"),
                          {"ids": ids}).mappings().all()
    if len(rows) != len(ids):
        raise ValueError("Có hợp đồng không còn tồn tại (danh sách đã cũ) — tải lại rồi thử lại.")
    _assert_linkable(rows, master, attach)
    # Nhóm báo cáo sau thao tác: gắn → theo loại hồ sơ này; gỡ → chưa khai loại.
    new_group = master["master_type"] if attach else ""
    mt = grp.master_types(r["master_id"] for r in rows)
    moved = [r["id"] for r in rows
             if grp.group_of(r["contract_type"], mt.get(r["master_id"])) != new_group]
    if updated_by:
        grp.assert_regroup_fences(updated_by, master["company"], moved)
    with session_scope() as db:
        # Đổi liên kết hồ sơ + loại (Phụ lục khi GẮN, chưa khai khi GỠ). Khách hàng, số lượng… giữ
        # NGUYÊN — gắn vào hồ sơ không được phép sửa số liệu của một kỳ đã chốt (chốt 24/08/2026).
        db.execute(text("UPDATE sales_contract SET master_id = CAST(:m AS bigint), "
                        "contract_type = :t, updated_by = :by, updated_at = now() "
                        "WHERE id = ANY(:ids)"),
                   {"m": master_id if attach else None, "t": "long_term" if attach else None,
                    "by": updated_by, "ids": ids})
    codes = ", ".join(r["code"] for r in rows)
    audit_repo.log("master_contract", "update", f"HĐ mẹ {master['code']}",
                   before={"annexes": "—",
                           # Loại cũ của từng hợp đồng — gắn/gỡ ghi đè loại, đây là chỗ duy nhất còn giữ.
                           "contract_types": "; ".join(f"{r['code']}: {r['contract_type'] or '—'}"
                                                       for r in rows)},
                   after={"action": "gắn phụ lục" if attach else "gỡ phụ lục", "contracts": codes},
                   as_of=master.get("sign_date"), company=master["company"],
                   note=f"{'Gắn' if attach else 'Gỡ'} {len(ids)} phụ lục: {codes}"[:500])
    return {"master_id": master_id, "count": len(ids), "attached": attach}
