"""Router màn "CHỈ SỐ ĐƠN VỊ" — một bảng hai cấp khu vực → đơn vị, nhiều tab chỉ số (chỉ đọc).

Khác họ `/api/unit-daily/analytics/*` (mỗi màn một chủ đề, nhóm theo MỘT chiều): ở đây luôn hiện
đồng thời dòng khu vực và dòng đơn vị, đổi tab không mất kỳ/bộ lọc đang xem. Số liệu lấy lại đúng
các bảng thống kê đó nên hai nơi không thể lệch nhau.

Danh mục cho các ô lọc dùng chung `/api/unit-daily/analytics/filters`.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_cap
from app.services import unit_scorecard, unit_scorecard_grade
from app.services.unit_scorecard_cols import GRADE_PARTIAL_TABS, GRADE_TABS, TABS

router = APIRouter(prefix="/api/unit-daily/scorecard", tags=["unit-scorecard"])
_require = require_cap("unit_daily")

_TAB_PATTERN = "^(" + "|".join(TABS) + ")$"
_MEASURE_PATTERN = "^(" + "|".join(unit_scorecard_grade.MEASURES) + ")$"


def stock_day(date_to: str, as_of: str | None) -> str:
    """Ngày chốt tồn kho — KHÔNG bao giờ vượt quá hôm nay.

    Kỳ mặc định "Tháng này" kết thúc ở ngày cuối tháng, tức là một ngày TƯƠNG LAI trong gần hết
    tháng. Lấy thẳng ngày đó làm ngày chốt thì tab Tồn kho luôn trống (chưa ai khai cho tương lai)
    và cột tồn ở tab Tổng quan cũng trống — trông như hỏng. Kẹp về hôm nay là số liệu mới nhất
    thật sự có, vẫn đúng nguyên tắc không mượn số ngày khác.
    """
    from app.core.edit_window import today

    chosen = as_of or date_to
    return min(chosen, today().isoformat())


def assert_dates(date_from: str, date_to: str, as_of: str | None) -> None:
    try:
        a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    if a > b:
        raise HTTPException(400, "Khoảng ngày không hợp lệ: từ ngày sau đến ngày.")
    if as_of:
        try:
            date.fromisoformat(as_of)
        except ValueError as exc:
            raise HTTPException(400, "Ngày chốt tồn kho không hợp lệ (YYYY-MM-DD).") from exc


@router.get("/tabs")
def tabs(username: str = Depends(_require)) -> dict:
    """Tab + cho biết tab nào lọc được chủng loại, kèm danh sách chỉ số của bảng chéo chủng loại."""
    return {
        "tabs": [{"key": k, "label": v["label"], "axis": v["axis"],
                  "grade_filter": ("full" if k in GRADE_TABS else
                                   "partial" if k in GRADE_PARTIAL_TABS else "none")}
                 for k, v in TABS.items()],
        "measures": [{"key": k, "label": m["label"], "unit": m["unit"], "axis": m["axis"],
                      "note": m.get("note", "")}
                     for k, m in unit_scorecard_grade.MEASURES.items()],
    }


@router.get("")
def scorecard(tab: str = Query("overview", pattern=_TAB_PATTERN),
              date_from: str = Query(..., description="Từ ngày YYYY-MM-DD"),
              date_to: str = Query(..., description="Đến ngày YYYY-MM-DD"),
              as_of: str | None = Query(None, description="Ngày chốt tồn kho; mặc định = đến ngày"),
              companies: str | None = Query(None, description="Đơn vị, phân cách dấu phẩy"),
              regions: str | None = Query(None, description="Khu vực, phân cách dấu phẩy"),
              grades: str | None = Query(None, description="Chủng loại (chỉ tab có thành phẩm)"),
              materials: str | None = Query(None, description="latex,cup,lace,finished"),
              contract: str | None = Query(None, description="spot,principle,long_term"),
              channel: str | None = Query(None, description="export,domestic,internal"),
              source: str | None = Query(None, description="exploit,purchase"),
              status_kind: str = Query("purchase", pattern="^(purchase|consumption)$"),
              split_merged: bool = Query(False, description="Tách riêng đơn vị đã sáp nhập"),
              username: str = Depends(_require)) -> dict:
    """Bảng chỉ số của một tab: dòng khu vực (kèm số đơn vị chưa có số) + dòng từng đơn vị."""
    assert_dates(date_from, date_to, as_of)
    return unit_scorecard.scorecard(
        tab, date_from=date_from, date_to=date_to, as_of=stock_day(date_to, as_of),
        companies=companies, regions=regions, grades=grades, materials=materials,
        contract=contract, channel=channel, source=source, status_kind=status_kind,
        split_merged=split_merged)


@router.get("/by-grade")
def by_grade(measure: str = Query("con_qty", pattern=_MEASURE_PATTERN),
             date_from: str = Query(...), date_to: str = Query(...),
             as_of: str | None = Query(None),
             companies: str | None = Query(None), regions: str | None = Query(None),
             contract: str | None = Query(None), channel: str | None = Query(None),
             source: str | None = Query(None),
             split_merged: bool = Query(False),
             username: str = Depends(_require)) -> dict:
    """Bảng chéo ĐƠN VỊ × CHỦNG LOẠI cho MỘT chỉ số — xem cơ cấu chủng loại của mọi đơn vị một lúc.

    Không nhận `grades`: cột ĐÃ là chủng loại, lọc thêm chỉ làm mất cột.
    """
    assert_dates(date_from, date_to, as_of)
    return unit_scorecard_grade.by_grade(
        measure, date_from=date_from, date_to=date_to, as_of=stock_day(date_to, as_of),
        companies=companies, regions=regions, grades=None, materials=None,
        contract=contract, channel=channel, source=source, status_kind="purchase",
        split_merged=split_merged)
