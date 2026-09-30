"""Dựng câu truy vấn AVEVA/Wonderware Historian qua linked server (OPENQUERY) + đọc kết quả trả về
— thuần hàm, không I/O (kết nối nằm ở `scada_client`).

OPENQUERY KHÔNG nhận tham số/biến → buộc phải ghép chuỗi. Chống injection bằng 3 lớp:
  1. Định danh (tag, linked server) phải khớp regex nghiêm TRƯỚC khi ghép (không có `'`, `]`,
     khoảng trắng, `;`…) — sai là ném `ValueError`, không bao giờ "làm sạch rồi dùng tiếp".
  2. Tag luôn nằm trong ngoặc vuông `[Tag]`; chuỗi truy vấn trong nằm trong nháy đơn, nháy đơn
     bên trong nhân đôi (dạng tương đương mẫu của khách mà KHÔNG cần `SET QUOTED_IDENTIFIER OFF`).
  3. Ngày giờ do code tự format từ `datetime` — không nhận chuỗi từ người dùng.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from decimal import Decimal
from typing import Any

#: Tên tag Historian (vd `PM_EnergyReal0`, `Line1.Water$Total`).
TAG_RE = re.compile(r"^[A-Za-z0-9_.$#-]{1,128}$")
#: Linked server / database — chặt hơn tag vì đứng NGOÀI ngoặc vuông.
IDENT_RE = re.compile(r"^[A-Za-z0-9_]{1,128}$")

HOURLY_MS = 3_600_000   # mẫu theo giờ cho chỉ số ngày
MINUTE_MS = 60_000      # mẫu theo phút cho số mới nhất
LATEST_MINUTES = 10     # cửa sổ lấy số mới nhất

_TS_FMT = "%Y-%m-%d %H:%M:%S"

#: Một mẫu thô: (thời điểm, {tag đúng như đã khai: giá trị | None}).
RawRow = tuple[datetime, dict[str, float | None]]


def valid_tag(tag: str | None) -> bool:
    return isinstance(tag, str) and bool(TAG_RE.fullmatch(tag))


def valid_ident(name: str | None) -> bool:
    return isinstance(name, str) and bool(IDENT_RE.fullmatch(name))


def factory_tags(factory: dict) -> list[str]:
    """Mọi tag đã khai của nhà máy theo thứ tự điện → nước → bành, bỏ trống + bỏ trùng (không
    phân biệt hoa thường — Historian coi `abc` và `ABC` là một cột, trùng cột làm vỡ kết quả)."""
    raw = [*(factory.get("energy_tags") or []), factory.get("water_tag"), factory.get("bales_tag")]
    seen: set[str] = set()
    out: list[str] = []
    for tag in raw:
        if tag and tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out


def _inner(tags: list[str], resolution_ms: int, time_clause: str) -> str:
    cols = ", ".join(f"[{t}]" for t in tags)
    return (
        f"SELECT DateTime, {cols} FROM WideHistory"
        f" WHERE wwRetrievalMode = ''Cyclic'' AND wwResolution = {int(resolution_ms)}"
        " AND wwQualityRule = ''Extended'' AND wwVersion = ''Latest''"
        f" AND {time_clause}"
    )


def _wrap(linked_server: str, tags: list[str], resolution_ms: int, time_clause: str) -> str:
    if not valid_ident(linked_server):
        raise ValueError(f"Tên linked server không hợp lệ: {linked_server!r}")
    if not tags:
        raise ValueError("Chưa khai tag nào để truy vấn")
    bad = [t for t in tags if not valid_tag(t)]
    if bad:
        raise ValueError(f"Tên tag không hợp lệ: {', '.join(map(repr, bad))}")
    return f"SELECT * FROM OPENQUERY({linked_server}, '{_inner(tags, resolution_ms, time_clause)}')"


def range_query(linked_server: str, tags: list[str], start: datetime,
                end: datetime | None) -> str:
    """Mẫu Cyclic THEO GIỜ trong [start, end]. `end=None` → tới `GetDate()` của máy SCADA
    (kỳ gồm hôm nay — dùng đồng hồ phía Historian để khỏi lệch giờ giữa hai máy)."""
    if not isinstance(start, datetime) or (end is not None and not isinstance(end, datetime)):
        raise ValueError("Mốc thời gian phải là datetime")
    upper = "GetDate()" if end is None else f"''{end.strftime(_TS_FMT)}''"
    clause = f"DateTime >= ''{start.strftime(_TS_FMT)}'' AND DateTime <= {upper}"
    return _wrap(linked_server, tags, HOURLY_MS, clause)


def latest_query(linked_server: str, tags: list[str]) -> str:
    """Mẫu theo PHÚT của `LATEST_MINUTES` phút gần nhất — lấy dòng cuối có số làm số mới nhất."""
    clause = f"DateTime >= DateAdd(mi,-{LATEST_MINUTES},GetDate()) AND DateTime <= GetDate()"
    return _wrap(linked_server, tags, MINUTE_MS, clause)


def to_timestamp(value: Any) -> datetime | None:
    """`DateTime` của Historian → datetime tròn giây (FreeTDS cũ trả datetime2 thành chuỗi)."""
    if isinstance(value, datetime):
        return value.replace(microsecond=0, tzinfo=None)
    if isinstance(value, str) and len(value) >= 19:
        try:
            return datetime.fromisoformat(value[:19].replace("T", " "))
        except ValueError:
            return None
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        num = float(value)
        return num if math.isfinite(num) else None
    return None


def map_rows(rows: list[dict[str, Any]], tags: list[str]) -> list[RawRow]:
    """Ghép cột trả về với tag đã khai KHÔNG phân biệt hoa thường; sắp theo thời điểm tăng dần."""
    out: list[RawRow] = []
    for row in rows:
        low = {str(k).lower(): v for k, v in row.items()}
        ts = to_timestamp(low.get("datetime"))
        if ts is not None:
            out.append((ts, {t: _number(low.get(t.lower())) for t in tags}))
    out.sort(key=lambda r: r[0])
    return out
