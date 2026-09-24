"""Phạm vi xem của màn "Dashboard đơn vị" — toàn Tập đoàn · một khu vực · một đơn vị.

MỘT chỗ duy nhất biến lựa chọn trên màn hình thành bộ lọc cho các bảng thống kê (`companies` ·
`regions` · `split_merged`) và danh sách đơn vị cho chuỗi tồn kho theo ngày. Tài khoản đơn vị bị ép
về đúng các đơn vị được gán NGAY Ở ĐÂY — web gửi phạm vi nào khác cũng không mở rộng được.

Đơn vị ĐÃ SÁP NHẬP xem ở chế độ TÁCH: chỉ số liệu của chính nó. Để chế độ gộp thì bộ lọc tự quy về
đơn vị nhận (`merge_view`) và dashboard của đơn vị cũ hiện nguyên số của đơn vị mới — với tài khoản
cũ của đơn vị đó là lộ số của đơn vị khác.
"""

from __future__ import annotations

from typing import Any

from app.services import member_region_repo, member_unit_merge, member_unit_repo
from app.services.unit_report_query import report_units

SCOPES = ("group", "region", "unit")
GROUP_LABEL = "Toàn Tập đoàn"
#: Chiều của phần "theo khu vực / theo đơn vị" ở từng mức phạm vi — mức đơn vị không có chiều con.
_CHILD = {"group": "region", "region": "company", "unit": None}
_CHILD_LABEL = {"region": "Khu vực", "company": "Đơn vị"}


class ScopeDenied(Exception):
    """Phạm vi nằm ngoài quyền của tài khoản (→ 403)."""


class ScopeNotFound(Exception):
    """Khu vực / đơn vị không tồn tại (→ 404)."""


def _own_units(own: list[str]) -> list[dict[str, Any]]:
    """Đơn vị được gán cho tài khoản, giữ đúng thứ tự gán (đơn vị đã xoá khỏi danh mục thì bỏ)."""
    by_name = {u["name"]: u for u in member_unit_repo.list_units()}
    return [by_name[n] for n in own if n in by_name]


def catalog(own: list[str] | None) -> dict[str, Any]:
    """Danh mục cho ô chọn phạm vi. `own=None` = tài khoản xem được mọi phạm vi."""
    if own is not None:
        units = [{"name": u["name"], "region": u.get("region")} for u in _own_units(own)]
        if not units:
            raise ScopeDenied("Tài khoản chưa được gán đơn vị thành viên — liên hệ quản trị.")
        return {"mode": "unit", "regions": [], "units": units,
                "default": {"scope": "unit", "key": units[0]["name"]}}
    units = report_units(split_merged=False)
    counts: dict[str, int] = {}
    for u in units:
        if u.get("region"):
            counts[u["region"]] = counts.get(u["region"], 0) + 1
    # Chỉ liệt kê khu vực ĐANG HOẠT ĐỘNG và có đơn vị — theo đúng thứ tự admin đã sắp.
    regions = [{"name": r, "units": counts[r]} for r in member_region_repo.active_names()
               if counts.get(r)]
    return {"mode": "group", "regions": regions,
            "units": [{"name": u["name"], "region": u.get("region")} for u in units],
            "default": {"scope": "group", "key": None}}


def _info(scope: str, key: str | None, label: str, *, companies: str | None = None,
          regions: str | None = None, split_merged: bool = False,
          units: list[str] | None = None, children: list[str] | None = None) -> dict[str, Any]:
    child = _CHILD[scope]
    return {
        "public": {"scope": scope, "key": key, "label": label, "child": child,
                   "child_label": _CHILD_LABEL.get(child or "")},
        # Bộ lọc truyền thẳng vào `unit_report_*` — cùng cách gọi của các màn thống kê.
        "filters": {"companies": companies, "regions": regions, "split_merged": split_merged},
        # Danh sách tên đơn vị (đã mở rộng theo sáp nhập) cho chuỗi tồn kho; None = mọi đơn vị.
        "units": units,
        "child": child,
        # Khung dòng của chiều con, đúng thứ tự admin đã sắp (khu vực · đơn vị) — kể cả dòng chưa
        # có số: bảng tiến độ chỉ tiêu phải hiện cả đơn vị được giao kế hoạch mà chưa thực hiện.
        "children": children or [],
    }


def resolve(scope: str, key: str | None, own: list[str] | None) -> dict[str, Any]:
    """Lựa chọn trên màn hình → bộ lọc số liệu. Ném `ScopeDenied` / `ScopeNotFound` / `ValueError`."""
    if scope not in SCOPES:
        raise ValueError(f"Phạm vi không hợp lệ: {scope}")
    key = (key or "").strip() or None
    if own is not None and (scope != "unit" or key not in own):
        raise ScopeDenied("Tài khoản đơn vị chỉ xem được dashboard của đơn vị được gán.")
    if scope == "group":
        return _info("group", None, GROUP_LABEL,
                     children=[r["name"] for r in catalog(None)["regions"]])
    if not key:
        raise ValueError("Chưa chọn khu vực / đơn vị.")
    if scope == "region":
        names = [u["name"] for u in report_units(split_merged=False) if u.get("region") == key]
        if not names and key not in member_region_repo.active_names():
            raise ScopeNotFound(f"Không có khu vực “{key}”.")
        return _info("region", key, f"Khu vực {key}", regions=key,
                     units=member_unit_merge.expand(names) or names, children=names)
    unit = {u["name"]: u for u in member_unit_repo.list_units()}.get(key)
    if not unit:
        raise ScopeNotFound(f"Không có đơn vị “{key}”.")
    if unit.get("merged_into"):
        return _info("unit", key, key, companies=key, split_merged=True, units=[key])
    return _info("unit", key, key, companies=key,
                 units=member_unit_merge.expand([key]) or [key])
