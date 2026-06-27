"""API gợi ý giá sàn + backtest + tương quan chỉ số (cho màn 'Gợi ý giá sàn')."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.services import floor_suggest, to_trinh, to_trinh_html

router = APIRouter(prefix="/api/floor-suggest", tags=["floor-suggest"])

_MODEL = Query("v1", pattern="^(v1|v1i|v1f|v2)$",
               description="v1=rổ futures · v1i=rổ+tồn kho tổng · v1f=rổ+tồn kho tự do · v2=đa biến+mủ nước")


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


@router.get("/scenarios")
def scenarios(
    as_of: str = Query(..., description="ngày YYYY-MM-DD (lần ban hành hoặc ngày bất kỳ)"),
    model: str = _MODEL,
    shock_pct: float | None = Query(None, ge=0, description="cú sốc % rổ (bỏ trống = 1σ lịch sử)"),
) -> dict:
    """Ma trận kịch bản Giảm/Cơ sở/Tăng cho từng grade (sốc ±shock lên rổ chỉ số)."""
    return floor_suggest.scenarios(as_of, model, shock_pct)


@router.get("/correlation")
def correlation(grade: str = Query("SVR 10")) -> list[dict]:
    """Bảng tương quan giá sàn (1 grade) vs các chỉ số."""
    return floor_suggest.correlation(grade)


@router.get("/chart")
def chart(grade: str = Query("SVR 10")) -> dict:
    """Chuỗi (chuẩn hoá base-100) giá sàn + chỉ số để vẽ chart tương quan."""
    return floor_suggest.chart(grade)


@router.get("/to-trinh", response_class=HTMLResponse)
def to_trinh_doc(
    as_of: str = Query(..., description="ngày 1 lần đã ban hành YYYY-MM-DD"),
    model: str = _MODEL,
) -> HTMLResponse:
    """Sinh TỜ TRÌNH giá sàn (HTML A4) từ đề xuất mô hình + dữ liệu thị trường — để preview & in."""
    return HTMLResponse(to_trinh_html.render(to_trinh.build(as_of, model)))


@router.get("/to-trinh/data")
def to_trinh_data(as_of: str = Query(...), model: str = _MODEL) -> dict:
    """Dữ liệu thô 4 khối tờ trình (JSON) — để đối chiếu/sửa trước khi xuất."""
    return to_trinh.build(as_of, model)
