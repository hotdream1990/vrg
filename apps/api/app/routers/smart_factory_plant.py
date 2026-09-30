"""Nhà máy thông minh — Sơ đồ vận hành (mimic SCADA kiểu màn RELCO): bố cục + số MỚI NHẤT theo khu.

Quyền `smart_factory` (gắn ở main.py). Bố cục là file JSON trong code (`scada_plant_layout`), nhà máy
chọn bố cục bằng `scada_factory.layout_key`. Số sống đọc thẳng Historian bằng truy vấn "số mới nhất"
dùng chung với /meters/live (Cyclic 1 phút, dòng cuối = lúc GetDate()) nhưng cửa sổ chỉ
`PLANT_MINUTES` phút. MỘT truy vấn cho mọi khu của nhà máy (~205 tag), cache `PLANT_TTL_S` giây DÙNG
CHUNG: bao nhiêu người mở, mở khu nào thì SCADA vẫn chỉ bị hỏi tối đa 1 lần / 5 giây / nhà máy.
Bận → trả số vừa đọc (live), không có thì 429; SCADA lỗi → 502 (như /meters/*).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.routers.smart_factory_shared import enabled_factory, guarded_read
from app.services import scada_client
from app.services import scada_daily_meters as dm
from app.services import scada_plant_layout as plant

router = APIRouter(prefix="/api/smart-factory/plant", tags=["smart-factory"])

PLANT_TTL_S = 5.0
PLANT_MINUTES = 1
NO_LAYOUT = "Nhà máy này chưa có sơ đồ vận hành."
NO_AREA = "Sơ đồ vận hành không có khu này."


def _plant(factory_id: int) -> tuple[dict, dict]:
    """(nhà máy đang bật, bố cục) — nhà máy chưa gán / gán khoá không còn file → 404."""
    factory = enabled_factory(factory_id)
    layout = plant.get_layout(factory.get("layout_key") or "")
    if layout is None:
        raise HTTPException(404, NO_LAYOUT)
    return factory, layout


@router.get("/layout")
def plant_layout(factory_id: int = Query(...)) -> dict:
    """Bố cục CHỈ gồm khu đang hiện (khu `hidden` giữ trong file, không gửi web)."""
    factory, layout = _plant(factory_id)
    return {"factory": {"id": factory["id"], "name": factory["name"]},
            "layout": plant.public_layout(layout)}


@router.get("/live")
def plant_live(factory_id: int = Query(...), area: str = Query(..., max_length=64),
               username: str = Depends(get_current_user)) -> dict:
    """Số mới nhất CÓ GIÁ TRỊ của mọi tag trong khu + tag điện; tag không có số → value null."""
    factory, layout = _plant(factory_id)
    tags = plant.area_tags(layout, area)
    if tags is None:  # kiểm TRƯỚC khi đọc: khu lạ / khu ẩn không bao giờ chạm SCADA hay vào khoá cache
        raise HTTPException(404, NO_AREA)
    every = plant.all_tags(layout)  # MỘT truy vấn cho mọi khu đang hiện, cache dùng chung
    rows = guarded_read(
        factory, username, None, None,
        lambda f, _s, _e: scada_client.read_latest(f, every, minutes=PLANT_MINUTES),
        ttl=PLANT_TTL_S, scope="plant", live=True)
    latest = dm.latest_of(rows, tags)
    values = {t: {"value": round(latest[t][1], 2) if t in latest else None,
                  "at": dm.iso(latest[t][0]) if t in latest else None} for t in tags}
    # fetched_at: giờ VN của máy chủ app — web so với `at` mới nhất để biết số đã CŨ (mất tín hiệu),
    # không dùng đồng hồ trình duyệt (máy người xem có thể lệch giờ/múi).
    return {"area": area, "values": values, "fetched_at": dm.iso(dm.vn_now().replace(microsecond=0))}
