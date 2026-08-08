"""Router THỐNG KÊ số liệu đơn vị nhập — dashboard + biểu mẫu lọc (chỉ đọc).

Khác `unit_daily` (nhập liệu + biểu mẫu bám mẫu tuần), các endpoint ở đây trả bảng tổng hợp
LỌC ĐƯỢC tới mức chi tiết: đơn vị · khu vực · kỳ · loại mủ · chủng loại · loại HĐ · hình thức ·
nguồn mủ. Quyền: `unit_daily` mức Xem (chuyên viên/admin) — đơn vị thành viên dùng màn riêng.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.market_meta import UNIT_GRADES
from app.core.security import require_cap
from app.services import (
    member_region_repo, member_unit_repo, unit_analytics_excel as xls,
    unit_report_consumption as con, unit_report_purchase as pur, unit_report_query as q,
    unit_report_stock as st,
)

router = APIRouter(prefix="/api/unit-daily/analytics", tags=["unit-analytics"])
_require = require_cap("unit_daily")

# Một năm đủ để Ban TTKD rà soát theo kỳ/năm, đồng thời vẫn giữ kích thước phản hồi an toàn.
# Ma trận được cuộn ngang ở web nên không cần bó hẹp ở 3 tháng như phiên bản đầu.
MAX_STATUS_DAYS = 366


def assert_range(date_from: str, date_to: str) -> None:
    """Chặn khoảng ngày sai định dạng / ngược đầu (dùng chung cho mọi endpoint thống kê)."""
    try:
        a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    if a > b:
        raise HTTPException(400, "Khoảng ngày không hợp lệ: từ ngày sau đến ngày.")


def _xlsx(data: bytes, name: str) -> Response:
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _note(rep: dict) -> str:
    """Dòng ghi chú dưới tiêu đề file Excel: cách nhóm + cảnh báo dữ liệu thiếu."""
    parts = [f"Nhóm theo: {xls.GROUP_LABELS.get(rep['group_by'], rep['group_by'])}"]
    parts += rep.get("warnings") or []
    return " · ".join(parts)


@router.get("/filters")
def filters(username: str = Depends(_require)) -> dict:
    """Danh mục cho các ô lọc: đơn vị (kèm khu vực) · khu vực · chủng loại · loại mủ."""
    return {
        "units": [{"name": u["name"], "region": u.get("region"),
                   "has_factory": u.get("has_factory", True)}
                  for u in member_unit_repo.list_units(include_inactive=False)],
        "regions": member_region_repo.active_names(),
        "grades": list(UNIT_GRADES),
        "materials": [{"value": k, "label": v} for k, v in q.MATERIAL_LABELS.items()],
        "contracts": [{"value": k, "label": v} for k, v in q.CONTRACT_LABELS.items()],
        "channels": [{"value": k, "label": v} for k, v in q.CHANNEL_LABELS.items()],
        "sources": [{"value": k, "label": v} for k, v in q.SOURCE_LABELS.items()],
    }


# ── 1. Thu mua ────────────────────────────────────────────────────────────────
def _purchase(date_from: str, date_to: str, companies: str | None, regions: str | None,
              materials: str | None, grades: str | None, group_by: str) -> dict:
    assert_range(date_from, date_to)
    return pur.purchase_report(date_from, date_to, companies=companies, regions=regions,
                               materials=materials, grades=grades, group_by=group_by)


@router.get("/purchase")
def purchase(date_from: str = Query(...), date_to: str = Query(...),
             companies: str | None = Query(None, description="Danh sách đơn vị, phân cách dấu phẩy"),
             regions: str | None = Query(None, description="Danh sách khu vực, phân cách dấu phẩy"),
             materials: str | None = Query(None, description="latex,cup,finished"),
             grades: str | None = Query(None, description="Chủng loại (chỉ áp cho mủ thành phẩm)"),
             group_by: str = Query("company", pattern="^(company|region|grade|day|material)$"),
             username: str = Depends(_require)) -> dict:
    """Bảng Thu mua theo bộ lọc — cuối bảng có Tổng sản lượng + 3 đơn giá BQ (theo đơn vị tính riêng)."""
    return _purchase(date_from, date_to, companies, regions, materials, grades, group_by)


@router.get("/purchase.xlsx")
def purchase_xlsx(date_from: str = Query(...), date_to: str = Query(...),
                  companies: str | None = Query(None), regions: str | None = Query(None),
                  materials: str | None = Query(None), grades: str | None = Query(None),
                  group_by: str = Query("company", pattern="^(company|region|grade|day|material)$"),
                  username: str = Depends(_require)):
    rep = _purchase(date_from, date_to, companies, regions, materials, grades, group_by)
    data = xls.build_xlsx(title="THỐNG KÊ THU MUA", period=f"{date_from} → {date_to}",
                          note=_note(rep), group_by=group_by, columns=xls.PURCHASE_COLS,
                          rows=rep["rows"], totals=rep["totals"])
    return _xlsx(data, f"thong-ke-thu-mua-{date_from}-den-{date_to}.xlsx")


# ── 2. Tiêu thụ ───────────────────────────────────────────────────────────────
def _consumption(date_from: str, date_to: str, companies: str | None, regions: str | None,
                 grades: str | None, contract: str | None, channel: str | None,
                 source: str | None, group_by: str, limit: int | None = None,
                 offset: int = 0) -> dict:
    assert_range(date_from, date_to)
    return con.consumption_report(date_from, date_to, companies=companies, regions=regions,
                                  grades=grades, contract=contract, channel=channel,
                                  source=source, group_by=group_by, limit=limit, offset=offset)


_CONSUMPTION_GROUPS = "^(company|region|grade|contract|channel|source|day|none)$"


@router.get("/consumption")
def consumption(date_from: str = Query(...), date_to: str = Query(...),
                companies: str | None = Query(None), regions: str | None = Query(None),
                grades: str | None = Query(None),
                contract: str | None = Query(None, description="long_term,spot"),
                channel: str | None = Query(None, description="export,domestic"),
                source: str | None = Query(None, description="sales (mủ thu mua), sales_own (mủ khai thác)"),
                group_by: str = Query("company", pattern=_CONSUMPTION_GROUPS),
                page: int = Query(1, ge=1),
                page_size: int = Query(100, ge=1, le=500),
                username: str = Depends(_require)) -> dict:
    """Bảng Tiêu thụ theo bộ lọc — `group_by=none` trả từng dòng bán để đối chiếu chứng từ.

    Chế độ chi tiết CẮT TRANG (`page`/`page_size`, trả kèm `total`): số lần giao tăng theo ngày.
    Các chế độ gộp nhóm còn lại vốn đã bị chặn bởi số đơn vị/khu vực/chủng loại/ngày trong kỳ.
    Bản xuất Excel KHÔNG cắt trang — file phải đủ dữ liệu để đối chiếu.
    """
    return _consumption(date_from, date_to, companies, regions, grades, contract, channel,
                        source, group_by, limit=page_size, offset=(page - 1) * page_size)


@router.get("/consumption.xlsx")
def consumption_xlsx(date_from: str = Query(...), date_to: str = Query(...),
                     companies: str | None = Query(None), regions: str | None = Query(None),
                     grades: str | None = Query(None), contract: str | None = Query(None),
                     channel: str | None = Query(None), source: str | None = Query(None),
                     group_by: str = Query("company", pattern=_CONSUMPTION_GROUPS),
                     username: str = Depends(_require)):
    rep = _consumption(date_from, date_to, companies, regions, grades, contract, channel,
                       source, group_by)
    cols = xls.CONSUMPTION_DETAIL_COLS if rep["detail"] else xls.CONSUMPTION_COLS
    data = xls.build_xlsx(title="THỐNG KÊ TIÊU THỤ", period=f"{date_from} → {date_to}",
                          note=_note(rep), group_by=group_by, columns=cols,
                          rows=rep["rows"], totals=rep["totals"])
    return _xlsx(data, f"thong-ke-tieu-thu-{date_from}-den-{date_to}.xlsx")


# ── 3. Tồn kho (số thời điểm) ─────────────────────────────────────────────────
def _stock(date_from: str, date_to: str, companies: str | None, regions: str | None,
           grades: str | None, group_by: str) -> dict:
    assert_range(date_from, date_to)
    return st.stock_report(date_from, date_to, companies=companies, regions=regions,
                           grades=grades, group_by=group_by)


@router.get("/stock")
def stock(date_from: str = Query(...), date_to: str = Query(...),
          companies: str | None = Query(None), regions: str | None = Query(None),
          grades: str | None = Query(None),
          group_by: str = Query("company", pattern="^(company|region|grade|day)$"),
          username: str = Depends(_require)) -> dict:
    """Tồn kho tại MỐC cuối kỳ của từng đơn vị (kèm ngày đã lấy số — không cộng dồn)."""
    return _stock(date_from, date_to, companies, regions, grades, group_by)


@router.get("/stock.xlsx")
def stock_xlsx(date_from: str = Query(...), date_to: str = Query(...),
               companies: str | None = Query(None), regions: str | None = Query(None),
               grades: str | None = Query(None),
               group_by: str = Query("company", pattern="^(company|region|grade|day)$"),
               username: str = Depends(_require)):
    rep = _stock(date_from, date_to, companies, regions, grades, group_by)
    data = xls.build_xlsx(title="THỐNG KÊ TỒN KHO", period=f"{date_from} → {date_to}",
                          note=_note(rep), group_by=group_by, columns=xls.STOCK_COLS,
                          rows=rep["rows"], totals=rep["totals"])
    return _xlsx(data, f"thong-ke-ton-kho-{date_from}-den-{date_to}.xlsx")


# ── 4. Tình trạng nộp báo cáo (dashboard kiểm tra) ────────────────────────────
@router.get("/status")
def status(kind: str = Query(..., pattern="^(purchase|consumption)$"),
           date_from: str = Query(...), date_to: str = Query(...),
           companies: str | None = Query(None), regions: str | None = Query(None),
           username: str = Depends(_require)) -> dict:
    """Ma trận đơn vị × ngày: đã nhập / không tổ chức thu mua / chưa nhập."""
    assert_range(date_from, date_to)
    if (date.fromisoformat(date_to) - date.fromisoformat(date_from)).days + 1 > MAX_STATUS_DAYS:
        raise HTTPException(400, f"Khoảng ngày tối đa {MAX_STATUS_DAYS} ngày cho bảng tình trạng nộp.")
    return st.status_report(kind, date_from, date_to, companies=companies, regions=regions)
