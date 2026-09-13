"""III.3 Báo cáo tuần — biên độ giá thu mua mủ nước (đồng/độ TSC) theo từng tuần của kỳ.

Nguồn "theo bản tin ngày" (logic 16.7): cùng lớp `vrg` (chuyên viên chốt), mủ nước `purchase`,
bỏ giá 0 và CHỈ đơn vị đã gán khu vực — y như `bulletin_service._build_raw_materials`. Mỗi tuần =
min–max "vùng lõi" (bỏ đơn vị lệch hẳn trung vị tuần). Người dùng ghi đè từng ô qua narrative
`latex_override` / `latex_change_override`; ô trống = số tự tính (không lưu seed).
"""

from __future__ import annotations

import re
import statistics
import sys
from typing import Any

from app.core.paths import bulletin_dir

_BULLETIN = bulletin_dir()
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import r0  # noqa: E402

Band = tuple[int, int]

# Đơn vị nhập lệch hẳn khỏi nhóm (nhập nhầm) làm sai biên độ tuần → loại theo trung vị tuần.
_LATEX_OUTLIER_LO = 0.85   # < 85% trung vị tuần → loại
_LATEX_OUTLIER_HI = 1.15   # > 115% trung vị tuần → loại (chặn cả nhập nhầm cao bất thường)
_LEGACY_KEYS = ("latex_prev", "latex_curr", "latex_change")


def core_range(xs: list[float]) -> Band | None:
    """Min–max 'vùng lõi' giá mủ nước trong tuần, bỏ đơn vị lệch hẳn khỏi trung vị."""
    if not xs:
        return None
    if len(xs) < 3:                                  # quá ít điểm → không đủ cơ sở lọc
        return r0(min(xs)), r0(max(xs))
    med = statistics.median(xs)
    core = [v for v in xs if _LATEX_OUTLIER_LO * med <= v <= _LATEX_OUTLIER_HI * med] or xs
    return r0(min(core)), r0(max(core))


def auto_bands(values: dict[str, dict[str, float]], weeks: list[dict[str, Any]]) -> list[Band | None]:
    """`values` = {đơn vị: {ngày ISO: giá}} (đã lọc đơn vị) → biên độ từng tuần."""
    return [core_range([p for dmap in values.values() for d, p in dmap.items()
                        if p and w["mon"] <= d <= w["fri"]]) for w in weeks]


def format_band(b: Band | None) -> str | None:
    return f"{b[0]} - {b[1]}" if b else None


def parse_band(s: str | None) -> Band | None:
    """'515 - 540' / '515 – 540' / '540' → (515, 540); chữ lạ → None."""
    nums = [int(n) for n in re.findall(r"\d+", s or "")]
    if len(nums) == 1:
        return nums[0], nums[0]
    return (nums[0], nums[1]) if len(nums) == 2 else None


def band_change(prev: Band | None, curr: Band | None) -> str | None:
    """'-20 /0' — định dạng v1 (0 không dấu)."""
    if not prev or not curr:
        return None
    dmin, dmax = curr[0] - prev[0], curr[1] - prev[1]
    return f"{dmin:+d} /{dmax:+d}".replace("+0", "0")


def _pick(lst: Any, i: int) -> str | None:
    v = lst[i] if isinstance(lst, list) and i < len(lst) else None
    return v.strip() if isinstance(v, str) and v.strip() else None


def overrides(nar: dict[str, Any], span: int) -> tuple[list | None, list | None]:
    """Override đang có hiệu lực. Báo cáo v1 (span 1, chưa có list override) → dùng latex_prev/
    latex_curr/latex_change đã lưu. Đã gửi list (kể cả toàn None) = chế độ v2, bỏ trường cũ."""
    ov, cov = nar.get("latex_override"), nar.get("latex_change_override")
    if span == 1 and not isinstance(ov, list) and not isinstance(cov, list) \
            and any(nar.get(k) for k in _LEGACY_KEYS):
        return [nar.get("latex_prev"), nar.get("latex_curr")], [nar.get("latex_change")]
    return ov, cov


def resolve(auto: list[Band | None], override: list | None,
            change_override: list | None) -> tuple[list[str | None], list[str | None]]:
    """Biên độ + biến động hiển thị: ô override (khác rỗng) thắng; biến động tự tính từ biên độ
    ĐANG HIỂN THỊ (nên sửa biên độ là biến động theo), trừ khi biến động cũng bị ghi đè."""
    bands = [_pick(override, i) or format_band(b) for i, b in enumerate(auto)]
    changes: list[str | None] = []
    for i in range(len(bands) - 1):
        manual = _pick(change_override, i)
        changes.append(manual or band_change(parse_band(bands[i]), parse_band(bands[i + 1])))
    return bands, changes


def load_values(date_from: str, date_to: str) -> dict[str, dict[str, float]]:
    """Giá mủ nước lớp `vrg` trong khoảng, chỉ đơn vị đã gán khu vực (như bản tin ngày)."""
    from app.services import member_unit_repo, price_repo

    values = price_repo.purchase_sheet(date_from, date_to).get("values", {})
    in_region = {u["name"] for u in member_unit_repo.list_units() if u.get("region")}
    return {unit: dmap for unit, dmap in values.items() if unit in in_region}
