"""Loại nhập liệu của tài khoản đơn vị + nhóm người nhận thẻ Hỗ trợ & Thông báo (chốt 01/10/2026).

Một tài khoản `member` (nhập liệu của đơn vị) được giao MỘT HOẶC NHIỀU loại:
  - `purchase` — Thu mua: biểu Thu mua + giá mủ nguyên liệu đơn vị tự khai;
  - `stock`    — Tồn kho: biểu Tồn kho;
  - `contract` — Hợp đồng & tiêu thụ: khách hàng · hợp đồng mẹ · hợp đồng & đợt giao · báo cáo
                 tiêu thụ · nhu cầu thị trường.
Cột `app_user.entry_types` mặc định đủ 3 loại → tài khoản cũ không mất gì.

Hàng rào chặn GHI ở server (`assert_entry_type`). Đọc số liệu của chính đơn vị mình thì không chặn
— cùng đơn vị, không lộ chéo; giao diện tự ẩn màn ngoài phần việc.

Nhóm người nhận (`audience`) của một thẻ hỗ trợ = `leader` (lãnh đạo đơn vị) và/hoặc 3 loại trên:
thẻ chỉ hiện với đúng nhóm được chọn. Bản sao phía web: `apps/web/src/lib/entry-types.ts`.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException

PURCHASE = "purchase"
STOCK = "stock"
CONTRACT = "contract"
ENTRY_TYPES: tuple[str, ...] = (PURCHASE, STOCK, CONTRACT)
ENTRY_TYPE_LABEL = {PURCHASE: "Thu mua", STOCK: "Tồn kho", CONTRACT: "Hợp đồng & tiêu thụ"}

LEADER = "leader"
AUDIENCES: tuple[str, ...] = (LEADER, *ENTRY_TYPES)
AUDIENCE_LABEL = {
    LEADER: "Lãnh đạo đơn vị",
    PURCHASE: "CV Thu mua",
    STOCK: "CV Tồn kho",
    CONTRACT: "CV Hợp đồng & tiêu thụ",
}
#: Biểu ngày (`unit_daily_report.kind`) → loại nhập liệu phụ trách: biểu Thu mua · biểu Tồn kho.
DAILY_KIND_ENTRY_TYPE = {"purchase": PURCHASE, "consumption": STOCK}

#: Thẻ không ghi nhóm người nhận (dữ liệu cũ) = chỉ lãnh đạo — đúng luật trước 01/10/2026.
DEFAULT_AUDIENCE: list[str] = [LEADER]


def _pick(raw: Iterable[str] | None, allowed: tuple[str, ...]) -> list[str]:
    """Lọc + khử trùng, giữ THỨ TỰ CHUẨN của danh mục (không theo thứ tự client gửi)."""
    got = {str(x).strip() for x in (raw or []) if x is not None}
    return [k for k in allowed if k in got]


def clean_entry_types(raw: Iterable[str] | None) -> list[str]:
    return _pick(raw, ENTRY_TYPES)


def clean_audience(raw: Iterable[str] | None) -> list[str]:
    return _pick(raw, AUDIENCES)


def user_entry_types(user: dict) -> set[str]:
    """Loại nhập liệu THỰC của tài khoản. Chỉ role `member` có — vai trò khác trả rỗng."""
    if user.get("role") != "member":
        return set()
    return set(clean_entry_types(user.get("entry_types")))


def user_audiences(user: dict) -> set[str]:
    """Tài khoản này thuộc nhóm người nhận nào ở phía đơn vị (rỗng = không phải tài khoản đơn vị)."""
    if user.get("role") == "leader":
        return {LEADER}
    return user_entry_types(user)


def has_entry_type(user: dict, entry_type: str) -> bool:
    """Chỉ ràng buộc tài khoản `member`; vai trò khác đi theo hàng rào riêng của mình (quyền mục)."""
    return user.get("role") != "member" or entry_type in user_entry_types(user)


def assert_entry_type(user: dict, entry_type: str) -> None:
    """403 nếu tài khoản nhập liệu của đơn vị KHÔNG được giao loại này."""
    if not has_entry_type(user, entry_type):
        label = ENTRY_TYPE_LABEL.get(entry_type, entry_type)
        raise HTTPException(403, f"Tài khoản không được giao nhập liệu {label} — "
                                 "liên hệ quản trị để được phân công.")


# ── Kế hoạch năm: mỗi Ô thuộc một loại (một form chung cho cả hai loại) ──────────────────────────
def plan_field_type(field: str) -> str:
    """Ô Kế hoạch năm → loại phụ trách: kế hoạch THU MUA thuộc Thu mua; mọi ô còn lại (khai thác,
    hàng hoá, HĐ dài hạn, chuyển sang, tiêu thụ chuyến, doanh thu) thuộc Hợp đồng & tiêu thụ."""
    return PURCHASE if field == "plan_tonnes" else CONTRACT


def plan_values_allowed(user: dict, values: dict) -> dict:
    """Chỉ giữ ô Kế hoạch năm thuộc loại được giao; gửi ô mà không ô nào được phép → 403.

    BỎ ô ngoài loại thay vì báo lỗi cả form: web gửi nguyên form Kế hoạch năm, chặn cứng thì tài
    khoản chỉ có một loại không lưu nổi phần của mình. Ô bị bỏ = vắng mặt → `save_year_plan` giữ
    nguyên số đang lưu. Dùng chung cho ghi thẳng (`PUT /api/member/plan`) và Đề nghị sửa.
    """
    keep = {k: v for k, v in values.items() if has_entry_type(user, plan_field_type(k))}
    if values and not keep:
        assert_entry_type(user, PURCHASE if "plan_tonnes" in values else CONTRACT)
    return keep
