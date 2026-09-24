"""Router SNAPSHOT số liệu tuần — bản lưu cố định thu mua · tiêu thụ · tồn kho của từng đơn vị.

Quyền (gắn ở `main.py`): XEM = quyền `unit_daily` (admin · chuyên viên được cấp · lãnh đạo Tập
đoàn mức xem) — cùng hàng rào với màn Báo cáo tổng hợp; tài khoản đơn vị (member/leader) không có
quyền này nên bị chặn 403 (đây là số toàn hệ thống). "Chụp ngay" = CHỈ admin.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.security import require_admin
from app.services import unit_week_snapshot as svc, unit_week_snapshot_excel as excel

router = APIRouter(prefix="/api/unit-week-snapshots", tags=["unit-week-snapshot"])


def _week_key(week_start: str) -> str:
    """Chuỗi ngày → thứ Hai hợp lệ (400 nếu sai định dạng hoặc không phải thứ Hai)."""
    try:
        d = date.fromisoformat(week_start)
    except ValueError as exc:
        raise HTTPException(400, "Ngày không hợp lệ (YYYY-MM-DD).") from exc
    if d.weekday() != 0:
        raise HTTPException(400, "Khoá tuần phải là ngày thứ Hai.")
    return d.isoformat()


def _get(week_start: str) -> dict:
    snap = svc.detail(_week_key(week_start))
    if snap is None:
        raise HTTPException(404, "Tuần này chưa có bản lưu số liệu.")
    return snap


@router.get("")
def list_snapshots() -> dict:
    """Các tuần đã chụp (mới nhất trước) + tuần đang đủ điều kiện chụp và tuần kế tiếp."""
    return {"items": svc.list_items(), "status": svc.status()}


@router.get("/{week_start}")
def get_snapshot(week_start: str) -> dict:
    """Bản lưu đầy đủ 1 tuần: biểu Thu mua + biểu Tiêu thụ – Tồn kho từng đơn vị + dòng Tổng cộng."""
    return _get(week_start)


@router.get("/{week_start}/excel")
def snapshot_excel(week_start: str) -> Response:
    """Tải Excel của bản lưu (2 sheet, cùng khuôn file Báo cáo tổng hợp) — dựng từ số ĐÃ LƯU."""
    snap = _get(week_start)
    return Response(
        content=excel.build(snap),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{excel.file_name(snap)}"'},
    )


@router.post("/take")
def take_now(username: str = Depends(require_admin)) -> dict:
    """Admin chụp NGAY tuần gần nhất đã hết hạn nhập — chỉ khi tuần đó CHƯA có bản lưu (không đè)."""
    res = svc.take_due(by=username)
    if not res["taken"]:
        taken_at = excel.stamp((res.get("snapshot") or {}).get("taken_at"))
        raise HTTPException(409, f"{res['week']['label']} đã có bản lưu lúc {taken_at} — "
                                 "bản lưu cố định, không chụp đè.")
    return res
