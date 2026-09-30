"""Nhà máy thông minh — cấu hình kết nối SCADA (CHỈ admin, gác `require_admin` ở main.py).

Không bao giờ trả mật khẩu; PUT bỏ trống mật khẩu = giữ nguyên (trừ khi đổi máy chủ/cổng/tài khoản —
xem `scada_factory_repo.update_factory`). Thử kết nối luôn trả 200 (`ok=false` + lý do) để UI hiện
kết quả tại chỗ.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services import scada_client, scada_connection_check, scada_factory_repo as repo
from app.services import scada_daily_meters as dm
from app.services import scada_day_samples
from app.services import scada_read_guard as guard

router = APIRouter(prefix="/api/smart-factory/admin", tags=["smart-factory-admin"])


class FactoryIn(BaseModel):
    name: str = ""
    host: str = ""
    port: int | None = 1433
    username: str = ""
    password: str | None = None
    database: str | None = "Runtime"
    linked_server: str | None = "INSQL"
    energy_tags: list[str] = Field(default_factory=list)
    water_tag: str | None = None
    bales_tag: str | None = None
    enabled: bool = True


def _save(fn, *args) -> dict | None:  # noqa: ANN001 - create/update của repo
    try:
        return fn(*args)
    except repo.DuplicateNameError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _get(factory_id: int) -> dict:
    factory = repo.get_factory(factory_id)
    if not factory:
        raise HTTPException(404, "Không tìm thấy nhà máy.")
    return factory


@router.get("/factories")
def list_factories() -> dict:
    return {"factories": [repo.public_view(f) for f in repo.list_factories()]}


@router.post("/factories")
def create_factory(body: FactoryIn) -> dict:
    return {"factory": repo.public_view(_save(repo.create_factory, body.model_dump()))}


@router.put("/factories/{factory_id}")
def update_factory(factory_id: int, body: FactoryIn) -> dict:
    factory = _save(repo.update_factory, factory_id, body.model_dump())
    if factory is None:
        raise HTTPException(404, "Không tìm thấy nhà máy.")
    return {"factory": repo.public_view(factory)}


@router.delete("/factories/{factory_id}")
def delete_factory(factory_id: int) -> dict:
    if not repo.delete_factory(factory_id):
        raise HTTPException(404, "Không tìm thấy nhà máy.")
    return {"ok": True}


@router.post("/factories/{factory_id}/test")
def test_factory(factory_id: int) -> dict:
    """Thử kết nối bằng cấu hình ĐÃ LƯU (kể cả nhà máy đang tắt) + đọc số mới nhất + cảnh báo."""
    return scada_connection_check.check_connection(_get(factory_id))


@router.get("/factories/{factory_id}/samples")
def factory_samples(factory_id: int, day: str = Query(..., alias="date")) -> dict:
    """Mẫu theo giờ của một ngày (CHỈ ĐỌC) — giải thích cờ của ô chỉ số trên màn chỉ số."""
    factory = _get(factory_id)
    try:
        d = date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    now = dm.vn_now()
    if d > now.date():
        raise HTTPException(400, "Ngày không được sau hôm nay.")
    if not dm.factory_metrics(factory):
        raise HTTPException(400, "Nhà máy chưa khai tag nào.")
    try:
        return scada_day_samples.day_samples(factory, d, now)
    except guard.ScadaBusyError as exc:
        raise HTTPException(429, str(exc)) from exc
    except scada_client.ScadaError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/factories/{factory_id}/tags")
def factory_tag_search(factory_id: int, q: str = Query("", max_length=64)) -> dict:
    """Tìm tag trong bảng `Tag` của Historian theo tên/mô tả (CHỈ ĐỌC) — giúp khai cấu hình."""
    factory = _get(factory_id)
    if len(q.strip()) < 2:
        raise HTTPException(400, "Nhập ít nhất 2 ký tự để tìm tag.")
    try:
        return {"tags": scada_client.search_tags(factory, q)}
    except scada_client.ScadaError as exc:
        raise HTTPException(502, str(exc)) from exc
