"""Soát "chữ nhận định lệch dữ liệu HIỆN TẠI" của Báo cáo tuần — trước khi xuất PDF.

Tình huống thật: AI viết giữa tuần khi mới có dữ liệu 1 ngày rồi lưu; cuối tuần dữ liệu đủ nên bảng
tự tính đổi, chữ đã lưu thì không ("Sàn SGX RSS3 (-0,92%)" trong khi bảng hiện +1,30%). Bộ soát CHỈ
CẢNH BÁO, không sửa chữ, không ghi DB, không gọi mạng/LLM.

`check_report(rep, prev_period=None)` — hàm thuần trên kết quả `build_report`:
  a/b/e. III.1: % · giá TB · cao/thấp · sàn thiếu/thừa (`weekly_consistency_exchange`)
  c.     I (cặp tuần mốc — cần `prev_period`), II, IV: chiều tăng/giảm (`weekly_consistency_direction`)
  d.     III.3: biên độ mủ nước đang dùng số đã lưu khác số tự tính hiện tại
`check_week(week_key)` — dựng báo cáo + bảng của tuần mốc rồi soát.
Kết quả: {"warnings": {key ô: [câu]}, "count": n, "summary": str}; key ô giống cảnh báo AI
(`summary_prev`, `movement`, `exchange_notes`, `macro:<i>`) + `latex_bands` cho bảng III.3.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.weekly_consistency_direction import check_direction
from app.services.weekly_consistency_exchange import check_exchange_notes
from app.services.weekly_report_latex import parse_band

logger = logging.getLogger(__name__)

_SECTION_LABELS = {"summary_prev": "I", "movement": "II", "exchange_notes": "III.1", "latex_bands": "III.3"}


def _norm_change(s: str | None) -> str:
    return "".join((s or "").split()).replace("–", "-")


def check_latex(rep: dict[str, Any]) -> list[str]:
    """III.3 — ô đang hiển thị (ghi đè/số v1 đã lưu) khác số tự tính theo dữ liệu hiện tại.
    Tuần chưa có dữ liệu tự tính (ô ghi đè để lấp chỗ trống) → không báo."""
    weeks = rep.get("weeks") or []
    shown, auto = rep.get("latex_bands") or [], rep.get("latex_auto_bands") or []
    out, bands_differ = [], False
    for i, (s, a) in enumerate(zip(shown, auto)):
        if a and parse_band(s) != parse_band(a):
            bands_differ = True
            out.append(f"Biên độ mủ nước Tuần {weeks[i]['week_no']} đang dùng số đã lưu {s or '(trống)'}; "
                       f"số tự tính theo dữ liệu hiện tại {a}.")
    if bands_differ:   # biến động tính theo biên độ đang hiển thị → lệch theo, không báo trùng
        return out
    ch_shown, ch_auto = rep.get("latex_changes") or [], rep.get("latex_auto_changes") or []
    for i, (s, a) in enumerate(zip(ch_shown, ch_auto)):
        if a and _norm_change(s) != _norm_change(a) and i + 1 < len(weeks):
            out.append(f"Biến động mủ nước Tuần {weeks[i + 1]['week_no']} đang dùng số đã lưu "
                       f"{s or '(trống)'}; số tự tính theo dữ liệu hiện tại {a}.")
    return out


def check_report(rep: dict[str, Any], prev_period: dict[str, Any] | None = None) -> dict[str, Any]:
    """`prev_period` = {"weeks": [tuần trước tuần mốc, tuần mốc], "exchange_rows": …} để soát Phần I."""
    nar = rep.get("narrative") or {}
    weeks, rows = rep.get("weeks") or [], rep.get("exchange_rows") or []
    warnings: dict[str, list[str]] = {
        "exchange_notes": check_exchange_notes(rep),
        "movement": check_direction(nar.get("movement") or [], rows, weeks),
        "latex_bands": check_latex(rep),
    }
    if prev_period and len(prev_period.get("weeks") or []) >= 2:
        warnings["summary_prev"] = check_direction(nar.get("summary_prev") or [],
                                                   prev_period.get("exchange_rows") or [],
                                                   prev_period["weeks"], fixed_pairs=[0])
    for i, m in enumerate(nar.get("macro") or []):
        warnings[f"macro:{i}"] = check_direction((m or {}).get("bullets") or [], rows, weeks)
    warnings = {k: v for k, v in warnings.items() if v}
    count = sum(len(v) for v in warnings.values())
    return {"warnings": warnings, "count": count, "summary": _summary(warnings, count)}


def _summary(warnings: dict[str, list[str]], count: int) -> str:
    if not count:
        return "Không thấy chỗ lệch giữa nhận định và dữ liệu hiện tại."
    parts = [f"{_SECTION_LABELS.get(k) or 'IV.' + str(int(k.split(':')[1]) + 1)}: {len(v)}"
             for k, v in warnings.items()]
    return f"Có {count} chỗ cần soát ({', '.join(parts)})."


def prev_period_tables(rep: dict[str, Any]) -> dict[str, Any] | None:
    """Bảng sàn 1 tuần của TUẦN MỐC (so tuần liền trước nó) — Phần I tóm tắt tuần này."""
    from app.services import weekly_period, weekly_report_tables as tables

    weeks = rep.get("weeks") or []
    if not weeks:
        return None
    per = weekly_period.period(weeks[0]["mon"], 1)
    market = tables.load_market(per)
    return {"weeks": per["weeks"], "exchange_rows": tables.exchange_rows(market, per["weeks"])}


def check_week(week_key: str) -> dict[str, Any]:
    """Dựng báo cáo đã lưu + soát. Không ghi gì."""
    from app.services import weekly_report_service

    rep = weekly_report_service.build_report(week_key)
    prev = None
    if any(s.strip() for s in (rep.get("narrative") or {}).get("summary_prev") or []):
        try:
            prev = prev_period_tables(rep)
        except Exception as exc:  # noqa: BLE001 — thiếu bảng tuần mốc thì bỏ soát Phần I, không chặn
            logger.warning("Soát báo cáo tuần %s: không dựng được bảng tuần mốc: %s", week_key, exc)
    return check_report(rep, prev)
