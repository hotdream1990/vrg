"""Cầu MỘT CHIỀU: giá mủ nguyên liệu ĐƠN VỊ tự khai (`vrg_unit`) → lớp CHUYÊN VIÊN (`vrg`).

Trước đây chuyên viên phải gõ lại vào lưới "Giá mủ nguyên liệu" đúng con số đơn vị vừa nộp.
Bật cầu này thì mỗi lần đơn vị thêm/sửa/xoá giá của mình, số chảy thẳng sang lớp chuyên viên —
tức là vào bản tin ngày, báo cáo tuần, gợi ý giá sàn.

Hai công tắc ĐỘC LẬP, đều do chuyên viên (quyền `raw_material` mức Sửa) bật ngay trong màn của mình:
  1. Công tắc TỔNG (`app_config.PURCHASE_AUTO_SYNC`) — tắt là dừng toàn bộ, KHÔNG mất danh sách đã chọn.
  2. Cờ TỪNG ĐƠN VỊ (`member_unit.auto_price_sync`) — chỉ đơn vị được chọn mới chảy.
Mặc định TẮT: không có thao tác cố ý của chuyên viên thì lớp `vrg` không bao giờ tự đổi.

⚠ Cầu chảy MỘT CHIỀU và số đơn vị LÀ số DUY NHẤT ở các đơn vị đang bật: ô của họ **khoá hẳn với
chuyên viên** (chỉ xem) — xem `assert_manual_allowed`. Trước đây chuyên viên vẫn gõ đè được nhưng
lần đơn vị nộp sau lại ghi đè ngược, thành ra con số nhìn thấy tuỳ thuộc ai ghi sau cùng. Muốn tự
nhập lại thì bỏ đơn vị đó ra khỏi danh sách. Chiều ngược lại KHÔNG bao giờ xảy ra — chuyên viên
sửa lưới của mình không ghi gì vào số đơn vị đã khai.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.edit_window import today
from app.core.market_meta import PURCHASE_PRICE_TYPES, PURCHASE_SOURCE_HQ, PURCHASE_SOURCE_UNIT
from app.services import config_repo, member_unit_repo, price_repo

#: Công tắc tổng — để ở app_config (KHÔNG khai trong `CONFIG_SPEC`: đây là công tắc của chuyên
#: viên trong màn nghiệp vụ, không phải cấu hình hệ thống của admin).
AUTO_SYNC_KEY = "PURCHASE_AUTO_SYNC"
_ON, _OFF = "on", "off"

#: Ghi vào nhật ký để phân biệt số máy đẩy sang với số chuyên viên tự gõ.
NOTE = "tự động lấy từ số đơn vị tự khai"

#: Số ngày mặc định của nút "Lấy số đã có" (đồng bộ ngược cho các ngày đơn vị đã nộp trước đó).
DEFAULT_BACKFILL_DAYS = 7
MAX_BACKFILL_DAYS = 90


def enabled() -> bool:
    """Công tắc tổng đang bật?"""
    return (config_repo.get_value(AUTO_SYNC_KEY) or _OFF).strip().lower() == _ON


def auto_companies() -> list[str]:
    """Các đơn vị ĐANG thực sự được đồng bộ (công tắc tổng tắt → rỗng)."""
    return member_unit_repo.auto_price_sync_names() if enabled() else []


def is_auto(company: str) -> bool:
    """Giá của đơn vị này có được đẩy sang lớp chuyên viên không?"""
    return company in set(auto_companies())


def assert_manual_allowed(company: Any, price_type: Any) -> None:
    """Chặn chuyên viên ghi/xoá tay ô của đơn vị ĐANG lấy số tự động (raise ValueError).

    Khoá ở tầng service chứ không chỉ ẩn nút trên web: cùng một ô còn vào được qua nhiều màn và
    qua API, mà đã hứa "số của đơn vị là số duy nhất" thì phải đúng ở mọi
    đường vào — nếu không con số cuối cùng lại tuỳ ai ghi sau.
    """
    if price_type in PURCHASE_PRICE_TYPES and isinstance(company, str) and is_auto(company):
        raise ValueError(
            f"“{company}” đang bật tự động lấy số từ đơn vị — ô này chỉ xem, số do đơn vị tự khai. "
            "Muốn nhập tay thì bỏ đơn vị khỏi danh sách ở nút “Tự động lấy số từ đơn vị”.")


def config() -> dict[str, Any]:
    """Trạng thái cho màn cấu hình: công tắc tổng + từng đơn vị (kèm cờ đang bật)."""
    units = member_unit_repo.list_units(include_inactive=False)
    return {
        "enabled": enabled(),
        "backfill_days": DEFAULT_BACKFILL_DAYS,
        "units": [{"name": u["name"], "auto": bool(u.get("auto_price_sync"))} for u in units],
    }


def save_config(on: bool, companies: list[str], by: str | None = None) -> dict[str, Any]:
    """Lưu công tắc tổng + danh sách đơn vị được đồng bộ. Chỉ ghi đơn vị THỰC SỰ đổi trạng thái
    (mỗi lần ghi là một dòng nhật ký — lưu lại cả danh sách sẽ làm nhật ký ngập rác)."""
    ensure_schema()
    config_repo.set_value(AUTO_SYNC_KEY, _ON if on else _OFF, by)
    wanted = {c.strip() for c in companies if c and c.strip()}
    for u in member_unit_repo.list_units():
        want = u["name"] in wanted
        if bool(u.get("auto_price_sync")) != want:
            member_unit_repo.set_auto_price_sync(u["name"], want)
    return config()


# ── Cầu: gọi từ `price_repo` mỗi khi lớp `vrg_unit` đổi ────────────────────────────────────
def mirror_upsert(rec: dict[str, Any]) -> None:
    """Đơn vị vừa ghi 1 ô giá → chép sang lớp chuyên viên (nếu đơn vị đó đang bật cầu)."""
    if not _should_mirror(rec.get("grade"), rec.get("price_type")):
        return
    price_repo.upsert_record({**rec, "source": PURCHASE_SOURCE_HQ}, note=NOTE)


def mirror_delete(as_of: str, company: str, contract: str, price_type: str) -> None:
    """Đơn vị vừa xoá/để trống 1 ô giá → xoá luôn ô tương ứng ở lớp chuyên viên.

    Giữ lại số cũ sẽ thành số "ma": đơn vị đã rút mà bản tin vẫn in giá của ngày đó.
    """
    if not _should_mirror(company, price_type):
        return
    price_repo.delete_record(as_of, PURCHASE_SOURCE_HQ, company, contract, price_type)


def _should_mirror(company: Any, price_type: Any) -> bool:
    return (isinstance(company, str) and price_type in PURCHASE_PRICE_TYPES
            and is_auto(company))


# ── Lấy số đã có (đồng bộ ngược N ngày) — chạy khi chuyên viên vừa bật thêm đơn vị ─────────
def backfill(days: int = DEFAULT_BACKFILL_DAYS, by: str | None = None) -> dict[str, Any]:
    """Chép số đơn vị đã nộp trong `days` ngày gần nhất sang lớp chuyên viên.

    Bật cầu chỉ ảnh hưởng các lần nộp SAU đó, nên các ngày đơn vị đã nộp trước khi bật vẫn trống
    bên lưới chuyên viên — nút này để lấp đúng phần đó. Chỉ chép ngày ĐƠN VỊ CÓ SỐ; ngày đơn vị
    không nộp thì để nguyên ô của chuyên viên (không xoá — người dùng bấm để LẤY số, không phải
    để dọn lưới).
    """
    companies = auto_companies()
    days = max(0, min(int(days), MAX_BACKFILL_DAYS))
    if not companies:
        return {"companies": [], "days": days, "copied": 0}
    date_from = (today() - timedelta(days=days)).isoformat()
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("""
                SELECT as_of, grade, contract, price_type, price, currency, unit
                FROM fact_price
                WHERE source = :src AND price_type = ANY(:types)
                  AND grade = ANY(:companies) AND as_of >= CAST(:dfrom AS date)
                ORDER BY as_of
            """),
            {"src": PURCHASE_SOURCE_UNIT, "types": list(PURCHASE_PRICE_TYPES),
             "companies": companies, "dfrom": date_from},
        ).mappings().all()
    for r in rows:
        price_repo.upsert_record(
            {"as_of": str(r["as_of"]), "source": PURCHASE_SOURCE_HQ, "grade": r["grade"],
             "contract": r["contract"] or "", "price_type": r["price_type"],
             "price": float(r["price"]), "currency": r["currency"], "unit": r["unit"]},
            note=f"{NOTE} ({days} ngày gần nhất)")
    return {"companies": companies, "days": days, "copied": len(rows), "by": by}
