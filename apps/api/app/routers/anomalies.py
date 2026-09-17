"""Router "Cảnh báo bất thường" — chỉ ADMIN (gắn `require_admin` ở main, cùng kiểu users/config).

Quét trực tiếp mỗi lần mở trang (không lưu bảng kết quả) — chủ dự án chốt 11/09/2026. Ngưỡng
phát hiện đọc từ cấu hình (nhóm `anomaly`), thiếu khoá nào thì lấy `default` của khoá đó
(`app/services/anomaly_types.THRESHOLDS`).

`anomaly_rules.scan()` (luật quét thật) được viết song song với router này nên import MUỘN
trong hàm — nếu module đó chưa tồn tại, trả 503 gọn thay vì sập cả ứng dụng lúc khởi động.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.edit_window import today
from app.core.security import require_admin
from app.services import anomaly_export, config_repo
from app.services.anomaly_types import THRESHOLDS

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _thresholds() -> dict[str, float]:
    """Ngưỡng đang áp dụng: đã lưu ở app_config thì lấy giá trị đó, chưa có thì lấy `default`."""
    out: dict[str, float] = {}
    for key, spec in THRESHOLDS.items():
        raw = config_repo.get_value(key)
        try:
            out[key] = float(raw) if raw not in (None, "") else float(spec["default"])
        except (TypeError, ValueError):
            out[key] = float(spec["default"])
    return out


def _default_range() -> tuple[str, str]:
    """Mặc định: từ 01/01 năm hiện tại tới HÔM QUA — hôm nay chưa hết ngày, kể vào là nhắc oan."""
    d = today()
    return date(d.year, 1, 1).isoformat(), (d - timedelta(days=1)).isoformat()


def scan_range(date_from: str | None, date_to: str | None) -> dict:
    """Quét đủ 8 luật trong khoảng (thiếu thì lấy mặc định) — dùng chung với màn của lãnh đạo
    đơn vị (`member_anomalies`). Import muộn `anomaly_rules` vì file đó từng viết song song."""
    try:
        from app.services import anomaly_rules
    except ImportError as exc:  # pragma: no cover - chỉ xảy ra khi anomaly_rules.py chưa tồn tại
        raise HTTPException(
            503, "Bộ luật quét bất thường chưa sẵn sàng (app/services/anomaly_rules.py)"
        ) from exc
    d_from, d_to = _default_range()
    return anomaly_rules.scan(date_from or d_from, date_to or d_to, _thresholds())


@router.get("", dependencies=[Depends(require_admin)])
def get_anomalies(date_from: str | None = Query(None), date_to: str | None = Query(None)) -> dict:
    """Quét + trả kết quả, kèm `thresholds` đang áp dụng để UI hiện lên form cấu hình."""
    result = scan_range(date_from, date_to)
    result["thresholds"] = _thresholds()
    return result


@router.get("/config", dependencies=[Depends(require_admin)])
def get_config() -> list[dict]:
    """Danh sách ngưỡng cho form admin: nhãn + gợi ý + giá trị đang áp dụng + mặc định gốc."""
    values = _thresholds()
    return [
        {"key": k, "label": v["label"], "hint": v["hint"], "value": values[k], "default": v["default"]}
        for k, v in THRESHOLDS.items()
    ]


@router.put("/config")
def put_config(body: dict, username: str = Depends(require_admin)) -> dict:
    """Lưu ngưỡng admin sửa. Chỉ nhận khoá có trong THRESHOLDS; giá trị phải là số > 0."""
    values = body.get("values") or {}
    updates: dict[str, str] = {}
    for key, raw in values.items():
        if key not in THRESHOLDS:
            continue  # khoá lạ → bỏ qua êm, không phải lỗi của admin
        label = THRESHOLDS[key]["label"]
        try:
            num = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(400, f'Giá trị của "{label}" phải là số') from None
        if num <= 0:
            raise HTTPException(400, f'Giá trị của "{label}" phải lớn hơn 0')
        updates[key] = str(num)
    for key, value in updates.items():
        config_repo.set_value(key, value, by=username)
    return {"updated": len(updates)}


@router.get("/export.xlsx", dependencies=[Depends(require_admin)])
def export_xlsx(date_from: str | None = Query(None), date_to: str | None = Query(None)) -> Response:
    """Xuất Excel: một sheet mỗi nhóm cảnh báo + sheet "Tổng quan"."""
    result = scan_range(date_from, date_to)
    data = anomaly_export.build_xlsx(result)
    name = f"canh-bao-bat-thuong-{result['date_from']}-den-{result['date_to']}.xlsx"
    return Response(
        content=data, media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
