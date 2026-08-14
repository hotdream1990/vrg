"""Quy tắc & tiện ích DÙNG CHUNG cho các bảng thống kê (lọc · gộp nhóm · bình quân).

Quy tắc số liệu (giữ đúng như biểu mẫu & form nhập):
- Sản lượng, doanh thu: **cộng dồn**.
- Giá: **bình quân gia quyền theo sản lượng** (không phải trung bình cộng).
- Giá mủ nước/mủ chén tính theo **đồng/độ** (TSC hoặc DRC), giá thành phẩm & giá bán theo
  **triệu đ/tấn** — KHÔNG quy đổi chéo, mỗi loại một chỉ tiêu bình quân riêng.
- Dòng nhập USD mà thiếu tỷ giá → KHÔNG tính vào doanh thu/giá BQ và được **cảnh báo** (không đoán số).
"""

from __future__ import annotations

from typing import Callable

from app.services import member_unit_repo, unit_daily_repo
from app.services.unit_report_rows import MATERIAL_LABELS, SOURCE_LABELS

#: Nhãn cho ô CHƯA KHAI — hiện rõ là thiếu dữ liệu, thay vì để chuỗi rỗng hay đoán bừa một loại.
UNKNOWN_LABEL = "(chưa khai)"
#: Đơn vị chưa gán khu vực — cùng một nhãn cho cả gộp nhóm lẫn gộp kế hoạch, lệch chữ là dòng kế
#: hoạch không khớp được với dòng sản lượng và % hiện ra trống.
NO_REGION_LABEL = "(Chưa gán khu vực)"

CONTRACT_LABELS = {"long_term": "HĐ dài hạn", "spot": "HĐ chuyến"}
# Đủ 3 hình thức của cơ chế hợp đồng — thiếu "internal" thì tiêu thụ nội bộ hiện ra chuỗi thô.
CHANNEL_LABELS = {"export": "XK / UTXK", "domestic": "Tiêu thụ trong nước",
                  "internal": "Tiêu thụ nội bộ"}


def label_of(labels: dict[str, str], v: str | None) -> str:
    """Nhãn của một giá trị enum; giá trị lạ/thiếu → "(chưa khai)" chứ KHÔNG lọt chuỗi thô ra UI."""
    return labels.get(v or "", UNKNOWN_LABEL)


#: group_by → hàm lấy nhãn nhóm của 1 dòng chi tiết.
GROUPERS: dict[str, Callable[[dict], str | None]] = {
    "company": lambda r: r.get("company"),
    "region": lambda r: r.get("region") or NO_REGION_LABEL,
    "day": lambda r: r.get("as_of"),
    "grade": lambda r: r.get("grade"),
    "material": lambda r: MATERIAL_LABELS.get(r.get("material") or ""),
    "contract": lambda r: label_of(CONTRACT_LABELS, r.get("contract")),
    "channel": lambda r: label_of(CHANNEL_LABELS, r.get("channel")),
    "source": lambda r: SOURCE_LABELS.get(r.get("source") or ""),
}


def dmy(iso: str | None) -> str:
    """'2026-07-23' → '23/07/2026' (chuẩn VN) cho các câu cảnh báo người dùng đọc."""
    if not iso or len(iso) < 10:
        return iso or ""
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def split_csv(csv: str | None) -> list[str] | None:
    """'a,b' → ['a','b'] (rỗng/None → None = không lọc)."""
    if not csv:
        return None
    vals = [s.strip() for s in csv.split(",") if s.strip()]
    return vals or None


def filter_scope(rows: list[dict], companies: list[str] | None, regions: list[str] | None) -> list[dict]:
    """Lọc theo đơn vị + khu vực (dùng chung cho mọi bảng)."""
    out = rows
    if companies:
        keep = set(companies)
        out = [r for r in out if r["company"] in keep]
    if regions:
        keep = set(regions)
        out = [r for r in out if (r.get("region") or "") in keep]
    return out


def avg(total: float, qty: float) -> float | None:
    return (total / qty) if qty else None


#: Kế hoạch là chỉ tiêu NĂM của một ĐƠN VỊ → chỉ gắn được cho nhóm đơn vị/khu vực. Nhóm theo
#: ngày / loại mủ / chủng loại thì một chỉ tiêu năm không chia nhỏ ra được — để TRỐNG còn hơn chia bừa.
PLAN_DIMS = ("company", "region")


def year_plan_by_group(plan_key: str, group_by: str, companies: list[str] | None,
                       regions: list[str] | None, year: int) -> tuple[dict[str, float], float]:
    """Chỉ tiêu NĂM `plan_key` của màn "Kế hoạch năm" → ({khoá nhóm: tấn}, tổng theo bộ lọc).

    Mẫu số lấy theo DANH SÁCH ĐƠN VỊ khớp bộ lọc, không phải theo đơn vị có phát sinh số liệu:
    đơn vị được giao kế hoạch mà kỳ này chưa phát sinh gì vẫn phải nằm trong mẫu số — bỏ ra là %
    tự đẹp lên.
    """
    units = member_unit_repo.list_units(include_inactive=False)
    if companies:
        units = [u for u in units if u["name"] in set(companies)]
    if regions:
        units = [u for u in units if (u.get("region") or "") in set(regions)]
    plans = unit_daily_repo.year_plan(year)
    by_key: dict[str, float] = {}
    total = 0.0
    for u in units:
        n = (plans.get(u["name"]) or {}).get(plan_key) or 0.0
        if not n:
            continue
        total += n
        if group_by in PLAN_DIMS:
            k = u["name"] if group_by == "company" else (u.get("region") or NO_REGION_LABEL)
            by_key[k] = by_key.get(k, 0.0) + n
    return by_key, total


def sort_groups(groups: dict[str, dict], group_by: str) -> list[dict]:
    """Ngày → tăng dần; còn lại → theo nhãn (A→Z)."""
    key = "key" if group_by == "day" else "label"
    return sorted(groups.values(), key=lambda g: g[key])
