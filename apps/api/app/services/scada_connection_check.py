"""Nút «Kiểm tra kết nối» SCADA: kết nối + đọc số mới nhất + CẢNH BÁO cấu hình làm lệch chỉ số ngày.

Vì sao cảnh báo múi giờ/đồng hồ: Historian trả mốc theo giờ của CHÍNH máy SCADA (GetDate()), còn
chỉ số ngày chia theo 00:00 giờ Việt Nam. Máy SCADA đặt múi khác UTC+7 hoặc đồng hồ chạy lệch thì
mọi mốc ngày lệch theo mà không có cờ nào trên bảng — chỉ phát hiện được ở bước kiểm tra này.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services import scada_client
from app.services import scada_daily_meters as dm
from app.services import scada_historian_sql as hsql

logger = logging.getLogger("vrg.scada")

VN_OFFSET = "+07:00"
MAX_CLOCK_SKEW = timedelta(minutes=5)
_VALUE_KEYS = {"energy": "energy_kwh", "water": "water_m3", "bales": "bales"}
#: CONVERT(varchar(33), SYSDATETIMEOFFSET(), 126) → '2026-09-30T21:27:38.9179538+07:00'.
_SERVER_TIME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?\s*(Z|[+-]\d{2}:\d{2})")


def parse_server_time(raw: str) -> tuple[str, datetime] | None:
    """Giờ máy SQL Server → ('YYYY-MM-DDTHH:MM:SS±HH:MM', datetime có múi); sai dạng → None."""
    m = _SERVER_TIME_RE.fullmatch((raw or "").strip())
    if not m:
        return None
    text = m[1] + ("+00:00" if m[2] == "Z" else m[2])
    return text, datetime.fromisoformat(text)


def clock_warnings(server_time: str, now_utc: datetime) -> list[str]:
    """Cảnh báo múi giờ ≠ UTC+7 và đồng hồ lệch quá `MAX_CLOCK_SKEW` so với đồng hồ máy chủ app."""
    parsed = parse_server_time(server_time)
    if not parsed:
        return ["Không đọc được giờ của máy SCADA — chưa kiểm được múi giờ và đồng hồ."]
    text, at = parsed
    out: list[str] = []
    if text[-6:] != VN_OFFSET:
        out.append(f"Múi giờ máy SCADA là UTC{text[-6:]} — chỉ số ngày tính theo giờ Việt Nam "
                   "(UTC+7) sẽ lệch mốc.")
    skew = at - now_utc
    if abs(skew) > MAX_CLOCK_SKEW:
        minutes = round(abs(skew).total_seconds() / 60)
        out.append(f"Đồng hồ máy SCADA {'nhanh' if skew > timedelta(0) else 'chậm'} {minutes} phút "
                   "so với giờ Việt Nam của máy chủ ứng dụng — mốc 00:00 của chỉ số ngày sẽ lệch theo.")
    return out


def _latest_block(factory: dict, latest: list[hsql.RawRow]) -> tuple[dict[str, Any], list[str]]:
    """Số MỚI NHẤT có giá trị của TỪNG chỉ số (không chỉ dòng cuối — mỗi tag có thể trễ khác nhau)."""
    metrics = dm.factory_metrics(factory)
    found = dm.latest_of(dm.to_samples(latest, factory, metrics), metrics)
    tags = hsql.factory_tags(factory)
    raw = {t: next((v[t] for _, v in reversed(latest) if v.get(t) is not None), None) for t in tags}
    out = {"latest_at": dm.iso(max((ts for ts, _ in found.values()), default=None)), "raw": raw,
           "values": {_VALUE_KEYS[m]: dm.round_metric(m, found[m][1]) if m in found else None
                      for m in metrics}}
    if not found:
        return out, [f"{hsql.LATEST_MINUTES} phút gần nhất Historian không có số của các tag đã khai."]
    return out, [f"{dm.METRICS[m][0]} đã khai tag nhưng {hsql.LATEST_MINUTES} phút gần nhất không có "
                 "số — kiểm tra tag/thiết bị đo." for m in metrics if m not in found]


def check_connection(factory: dict, now_utc: datetime | None = None) -> dict[str, Any]:
    """LUÔN trả dict — lỗi thì `ok=False` + lý do đọc được; thành công kèm `warnings` (có thể rỗng)."""
    try:
        version, server_time, latest = scada_client.probe(factory)
    except scada_client.ScadaError as exc:
        return {"ok": False, "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001 - lỗi lạ của driver cũng phải thành câu trả lời
        logger.warning("[scada] Thử kết nối %s lỗi lạ: %s", factory.get("name"), type(exc).__name__)
        return {"ok": False, "detail": f"Lỗi không xác định khi kết nối ({type(exc).__name__})"}
    parsed = parse_server_time(server_time)
    warnings = clock_warnings(server_time, now_utc or datetime.now(timezone.utc))
    out: dict[str, Any] = {"ok": True, "detail": "Kết nối thành công", "server_version": version,
                           "server_time": parsed[0] if parsed else None}
    if not hsql.factory_tags(factory):
        out["detail"] = "Kết nối thành công — nhà máy chưa khai tag nào để đọc số"
    else:
        block, more = _latest_block(factory, latest)
        out.update(block)
        warnings += more
    out["warnings"] = warnings
    return out
