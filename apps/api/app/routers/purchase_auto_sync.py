"""Router "Tự động lấy giá mủ nguyên liệu từ đơn vị" — cầu `vrg_unit` → `vrg`.

Người bật/tắt là CHUYÊN VIÊN của chính màn Giá mủ nguyên liệu (quyền `raw_material`), không phải
admin: cấu hình này quyết định số nào vào bản tin/báo cáo, thuộc nghiệp vụ của Ban TTKD.
Mức Xem chỉ đọc được trạng thái; mọi thao tác ghi đòi mức Sửa.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import require_cap, require_cap_edit
from app.schemas.price import PurchaseAutoSyncEdit
from app.services import purchase_price_sync

router = APIRouter(prefix="/api/prices/purchase-auto-sync", tags=["prices"])


@router.get("", dependencies=[Depends(require_cap("raw_material"))])
def get_auto_sync() -> dict:
    """Công tắc tổng + danh sách đơn vị (kèm đơn vị nào đang được đồng bộ)."""
    return purchase_price_sync.config()


@router.put("")
def put_auto_sync(body: PurchaseAutoSyncEdit,
                  username: str = Depends(require_cap_edit("raw_material"))) -> dict:
    """Lưu công tắc tổng + danh sách đơn vị được lấy số tự động."""
    return purchase_price_sync.save_config(body.enabled, body.companies, by=username)


@router.post("/backfill")
def run_backfill(days: int = Query(purchase_price_sync.DEFAULT_BACKFILL_DAYS, ge=0,
                                   le=purchase_price_sync.MAX_BACKFILL_DAYS),
                 username: str = Depends(require_cap_edit("raw_material"))) -> dict:
    """Lấy ngay số các đơn vị đã nộp trong N ngày gần nhất (bật cầu chỉ ăn từ lần nộp sau)."""
    return purchase_price_sync.backfill(days, by=username)
