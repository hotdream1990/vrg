"""Nhà máy thông minh — Chỉ số điện · nước · số bành THEO NGÀY, đọc thẳng SCADA (không lưu DB).

Quyền: `smart_factory` (gắn ở main.py). Endpoint là `def` đồng bộ → FastAPI chạy trong threadpool,
truy vấn SQL Server chậm không chặn event loop; khoá theo nhà máy + cache 60s ở `scada_read_guard`
(bận quá lâu → 429). SCADA lỗi → 502 theo vai trò — xem `smart_factory_shared.guarded_read`.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.security import get_current_user
from app.core.vn_text import fold
from app.routers.smart_factory_shared import enabled_factory, guarded_read
from app.services import scada_client, scada_factory_repo as repo
from app.services import scada_daily_meters as dm
from app.services import scada_meters_excel as xls

router = APIRouter(prefix="/api/smart-factory", tags=["smart-factory"])

DEFAULT_DAYS = 30
MAX_DAYS = 92
LIVE_TTL_S = 5.0
NO_TAGS = "Nhà máy chưa khai tag nào — admin vào Cấu hình kết nối SCADA để khai."


@router.get("/factories")
def factories() -> dict:
    """Nhà máy đang bật — KHÔNG lộ thông tin kết nối."""
    return {"factories": [{"id": f["id"], "name": f["name"], "metrics": dm.factory_metrics(f),
                           "layout_key": f.get("layout_key")}  # có → web mở được Sơ đồ vận hành
                          for f in repo.list_factories(enabled_only=True)]}


def _parse(value: str | None, label: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def resolve_period(date_from: str | None, date_to: str | None, today: date) -> tuple[date, date]:
    """Kỳ xem: mặc định 30 ngày gần nhất tính cả hôm nay; `date_to` quá hôm nay → kẹp về hôm nay."""
    d0, d1 = _parse(date_from, "Từ ngày"), _parse(date_to, "Đến ngày")
    if d0 and d0 > today:
        raise HTTPException(400, "Từ ngày không được sau hôm nay.")
    d1 = min(d1 or today, today)
    d0 = d0 or d1 - timedelta(days=DEFAULT_DAYS - 1)
    if d0 > d1:
        raise HTTPException(400, "Khoảng ngày không hợp lệ: từ ngày sau đến ngày.")
    if (d1 - d0).days + 1 > MAX_DAYS:
        raise HTTPException(400, f"Kỳ xem tối đa {MAX_DAYS} ngày.")
    return d0, d1


def query_bounds(d0: date, d1: date, today: date) -> tuple[datetime, datetime | None]:
    """Khung truy vấn Historian. Kỳ gồm hôm nay → vế trên None = GetDate() của máy SCADA (tránh lệch
    đồng hồ giữa hai máy). Kỳ đã qua → D+1 00:00 + 1 giờ: có Historian không trả dòng đúng mốc
    `<= end`, nới 1 giờ cho chắc có mốc đóng ngày cuối; mẫu sau D+1 00:00 bị bỏ khi tính ngày."""
    start = datetime.combine(d0, time())
    if d1 >= today:
        return start, None
    return start, datetime.combine(d1 + timedelta(days=1), time()) + timedelta(hours=1)


def _factory(factory_id: int) -> dict:
    factory = enabled_factory(factory_id)
    if not dm.factory_metrics(factory):
        raise HTTPException(400, NO_TAGS)
    return factory


def _report(factory_id: int, date_from: str | None, date_to: str | None, username: str) -> dict:
    factory = _factory(factory_id)
    now = dm.vn_now()
    d0, d1 = resolve_period(date_from, date_to, now.date())
    start, end = query_bounds(d0, d1, now.date())
    hourly, latest = guarded_read(factory, username, start, end, scada_client.read_meters)
    return dm.build_report(factory, hourly, latest, d0, d1, now)


@router.get("/meters/live")
def meters_live(factory_id: int = Query(...), username: str = Depends(get_current_user)) -> dict:
    """Số LŨY KẾ thời gian thực (điện · nước · số bành) tới lúc đọc — web hỏi lại mỗi ~10 giây;
    cache `LIVE_TTL_S` giây dùng chung mọi người xem nên SCADA chỉ bị hỏi tối đa 1 lần/`LIVE_TTL_S`."""
    factory = _factory(factory_id)
    rows = guarded_read(factory, username, None, None,
                        lambda f, _s, _e: scada_client.read_latest(f), ttl=LIVE_TTL_S, live=True)
    metrics = dm.factory_metrics(factory)
    latest = dm.latest_of(dm.to_samples(rows, factory, metrics), metrics)
    values = {m: {"value": dm.round_metric(m, latest[m][1]) if m in latest else None,
                  "at": dm.iso(latest[m][0]) if m in latest else None} for m in metrics}
    return {"factory": {"id": factory["id"], "name": factory["name"]},
            "metrics": [{"key": m, "label": dm.METRICS[m][0], "unit": dm.METRICS[m][1]}
                        for m in metrics],
            "values": values}


@router.get("/meters/daily")
def meters_daily(factory_id: int = Query(...), date_from: str | None = Query(None),
                 date_to: str | None = Query(None),
                 username: str = Depends(get_current_user)) -> dict:
    return _report(factory_id, date_from, date_to, username)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-") or "nha-may"


@router.get("/meters/daily.xlsx")
def meters_daily_xlsx(factory_id: int = Query(...), date_from: str | None = Query(None),
                      date_to: str | None = Query(None),
                      username: str = Depends(get_current_user)) -> Response:
    rep = _report(factory_id, date_from, date_to, username)
    name = (f"chi-so-dien-nuoc-banh_{_slug(rep['factory']['name'])}_"
            f"{rep['date_from']}_{rep['date_to']}.xlsx")
    return Response(
        content=xls.build_xlsx(rep),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'})
