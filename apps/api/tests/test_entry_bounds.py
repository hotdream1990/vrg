"""Biên cảnh báo ô nhập: bản Python và bản web PHẢI khớp từng con số.

Web cảnh báo lúc ĐANG NHẬP, server rà lại SỐ ĐÃ LƯU để nhắc trên bảng việc của đơn vị. Hai bên
lệch nhau thì đơn vị sửa xong theo form mà bảng việc vẫn kêu (hoặc ngược lại) — không ai biết
tin bên nào.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core import entry_bounds as eb

_TS = Path(__file__).resolve().parents[3] / "apps/web/src/lib/entry-bounds.ts"


def _web_bounds() -> dict[str, tuple[float | None, float | None, str]]:
    src = _TS.read_text("utf-8")
    out: dict[str, tuple[float | None, float | None, str]] = {}
    for name, body in re.findall(r"export const (\w+): Bound = \{([^}]*)\}", src):
        def num(key: str) -> float | None:
            m = re.search(rf"\b{key}:\s*([\d_.]+)", body)
            return float(m.group(1).replace("_", "")) if m else None
        unit = re.search(r'unit:\s*"([^"]*)"', body)
        out[name] = (num("lo"), num("hi"), unit.group(1) if unit else "")
    return out


def test_entry_bounds_match_web() -> None:
    web = _web_bounds()
    assert web, "Không đọc được biên nào từ entry-bounds.ts — đổi cách khai báo thì sửa test này."
    for name, (lo, hi, unit) in web.items():
        py = getattr(eb, name, None)
        assert py is not None, f"`{name}` có ở web nhưng thiếu ở app/core/entry_bounds.py."
        assert (py.lo, py.hi, py.unit) == (lo, hi, unit), (
            f"Biên `{name}` lệch: web ({lo}, {hi}, {unit}) ≠ python {tuple(py)} — sửa cả 2 nơi.")

    # Danh sách chủng loại KHÔNG áp biên đơn giá cũng phải khớp (bên nào thiếu là bên đó kêu oan).
    block = re.search(r"export const NO_PRICE_BOUND_GRADES = \[(.*?)\];",
                      _TS.read_text("utf-8"), re.S).group(1)
    assert set(re.findall(r'"([^"]+)"', block)) == set(eb.NO_PRICE_BOUND_GRADES)


def test_zero_is_never_out_of_bounds_and_catch_all_grades_are_skipped() -> None:
    """Hai luật dễ mất khi sửa biên: số 0 là nghiệp vụ thật, và chủng loại 'gom' không có mặt bằng giá."""
    assert eb.bound_warning(0, eb.PRICE_VND) is None
    assert eb.bound_warning(0.7, eb.price_bound("VND", "Chủng loại khác")) is None
    assert eb.bound_warning(0.7, eb.price_bound("VND", "SVR 10 / CSR 10")) is not None
    assert eb.price_bound("LAK") is None                      # chưa đủ dữ liệu → không cảnh báo
    assert eb.fx_warning("USD", None) and eb.fx_warning("VND", None) is None
