"""Chặn TRÙNG SỐ hợp đồng / đợt giao — phân biệt THÊM MỚI với SỬA để không báo trùng nhầm.

Phạm vi kiểm theo đúng cấp: số hợp đồng là duy nhất trong ĐƠN VỊ, còn số đợt giao đánh lại từ 1 ở
MỖI hợp đồng (đợt "2" của hợp đồng này không đụng đợt "2" của hợp đồng khác). Chặn vì lưu lại do
mạng chập chờn sẽ nhân đôi sản lượng.

- THÊM MỚI trùng số ⇒ chặn. Câu báo nêu bản ghi đang có (ngày · sản lượng) và chỉ đường nếu thật ra
  người dùng muốn SỬA bản ghi đó — hai đề nghị bị kẹt 17–18/09/2026 đều là đơn vị bấm Thêm rồi gõ
  lại số của một đợt/hợp đồng đã có.
- SỬA mà GIỮ NGUYÊN số ⇒ không kiểm: dữ liệu cũ có sẵn 20 hợp đồng trùng số (3 nhóm, đo 18/09/2026),
  kiểm lại là khoá cứng mọi lần sửa ô khác của chúng dù không sinh thêm bản trùng nào.
- SỬA mà ĐỔI sang số đã có ⇒ chặn.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.services import sales_contract_calc as calc

_FIND = text(
    "SELECT code, sign_date, delivered_at, lines FROM sales_contract WHERE lower(code) = lower(:k) "
    " AND company = :c "   # đợt giao luôn cùng đơn vị với hợp đồng cha — lọc thêm để không lộ số đơn vị khác
    " AND ((CAST(:p AS bigint) IS NULL AND parent_id IS NULL) "
    "   OR (CAST(:p AS bigint) IS NOT NULL AND parent_id = CAST(:p AS bigint))) "
    " AND (CAST(:i AS bigint) IS NULL OR id <> CAST(:i AS bigint)) ORDER BY id LIMIT 1")


def assert_code_free(db, d: dict[str, Any], company: str, old_code: str | None) -> None:
    """`d` = bản ghi đã `clean`; `old_code` = số đang lưu của chính bản ghi khi SỬA (None khi thêm)."""
    is_update = d["id"] is not None
    if is_update and _norm(old_code) == _norm(d["code"]):
        return
    hit = db.execute(_FIND, {"c": company, "p": d["parent_id"], "k": d["code"],
                             "i": d["id"]}).mappings().first()
    if hit is not None:
        raise ValueError(_message(hit, is_child=d["parent_id"] is not None, is_update=is_update))


def _message(hit: dict[str, Any], *, is_child: bool, is_update: bool) -> str:
    code, facts = hit["code"], _facts(hit, is_child)
    if is_update:
        where = "một đợt giao khác của hợp đồng này" if is_child else "một hợp đồng khác của đơn vị"
        return f"Số “{code}” đã dùng cho {where} ({facts}) — chọn số khác."
    if is_child:
        return (f"Hợp đồng này đã có đợt giao số “{code}” ({facts}). Nếu đây là lần giao mới, hãy đặt "
                "số đợt khác; nếu muốn sửa đợt đã có, mở đúng đợt đó rồi bấm Sửa.")
    return (f"Đơn vị đã có hợp đồng số “{code}” ({facts}). Nếu đây là hợp đồng mới, hãy dùng số "
            "khác; nếu muốn sửa hợp đồng đã có, mở đúng hợp đồng đó rồi bấm Sửa.")


def _facts(hit: dict[str, Any], is_child: bool) -> str:
    """"giao 24/08/2026 · 60,48 tấn" — đủ để người dùng nhận ra bản ghi đang có là bản nào."""
    if hit["delivered_at"]:
        when = f"giao {_dmy(hit['delivered_at'])}"
    elif hit["sign_date"] and not is_child:
        when = f"ký {_dmy(hit['sign_date'])}"
    else:
        when = "chưa giao"
    return f"{when} · {_tan(calc.total_qty(hit['lines'] or []))} tấn"


def _norm(code: str | None) -> str:
    return (code or "").strip().lower()


def _dmy(value: Any) -> str:
    s = str(value)
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}"


def _tan(v: float) -> str:
    """60.48 → "60,48" · 1234.5 → "1.234,5" — kiểu số Việt, bỏ số 0 thừa sau dấu phẩy."""
    s = f"{v:,.3f}".rstrip("0").rstrip(".")
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
