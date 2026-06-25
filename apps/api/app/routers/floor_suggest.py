"""API gợi ý giá sàn + backtest + tương quan chỉ số (cho màn 'Gợi ý giá sàn')."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import floor_suggest

router = APIRouter(prefix="/api/floor-suggest", tags=["floor-suggest"])

_MODEL = Query("v1", pattern="^(v1|v2)$",
               description="v1=rổ 4 futures, đơn biến (khuyến nghị) · v2=đa biến ridge + mủ nước (đối chiếu)")


@router.get("/points")
def points() -> list[dict]:
    """Danh sách lần đã ban hành (cho dropdown chọn điểm so sánh)."""
    return floor_suggest.points()


@router.get("")
def suggest(
    as_of: str = Query(..., description="ngày 1 lần đã ban hành YYYY-MM-DD"),
    model: str = _MODEL,
    backtest: bool = Query(True, description="chỉ fit data trước lần đó (so sánh khách quan)"),
    alpha: float = Query(floor_suggest.DEFAULT_ALPHA, ge=0, description="hệ số ridge (v2)"),
) -> dict:
    """Gợi ý giá sàn theo grade tại 1 lần + so với giá đã ban hành."""
    return floor_suggest.suggest(as_of, model, backtest, alpha)


@router.get("/backtest")
def backtest(
    grade: str = Query("SVR 10"),
    model: str = _MODEL,
    alpha: float = Query(floor_suggest.DEFAULT_ALPHA, ge=0, description="hệ số ridge (v2)"),
) -> dict:
    """Backtest toàn chuỗi 1 grade: dự báo từng lần (fit data trước) vs giá sàn thực + metrics."""
    return floor_suggest.backtest(grade, model, alpha)


@router.get("/backtest/summary")
def backtest_summary(
    model: str = _MODEL,
    alpha: float = Query(floor_suggest.DEFAULT_ALPHA, ge=0, description="hệ số ridge (v2)"),
) -> list[dict]:
    """MAPE / % đúng hướng / n cho cả 13 grade (so độ khớp tổng quát giữa v1 và v2)."""
    return floor_suggest.backtest_summary(model, alpha)


@router.get("/correlation")
def correlation(grade: str = Query("SVR 10")) -> list[dict]:
    """Bảng tương quan giá sàn (1 grade) vs các chỉ số."""
    return floor_suggest.correlation(grade)


@router.get("/chart")
def chart(grade: str = Query("SVR 10")) -> dict:
    """Chuỗi (chuẩn hoá base-100) giá sàn + chỉ số để vẽ chart tương quan."""
    return floor_suggest.chart(grade)
