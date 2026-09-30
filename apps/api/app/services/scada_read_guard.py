"""Chống treo API + dồn tải lên SCADA khi đọc chỉ số theo ngày.

Vì sao cần: endpoint `/meters/daily` là `def` đồng bộ chạy trong threadpool (~40 luồng) DÙNG CHUNG với
mọi endpoint khác (kể cả đăng nhập). Mỗi lượt đọc SCADA có thể giữ luồng hàng chục giây khi VPN/SCADA
chậm; bấm lại liên tục hoặc nhiều người cùng xem thì cả app treo, đồng thời đè truy vấn Historian
lên hệ thống OT đang chạy thật của nhà máy. Hai lớp chặn:
  1. Khoá theo TỪNG nhà máy: mỗi nhà máy chỉ một lượt đọc SCADA tại một thời điểm; lượt sau chờ tối
     đa `LOCK_WAIT_S` giây rồi báo bận (router → 429) thay vì xếp hàng vô hạn.
  2. Cache kết quả đọc thô 60 giây, khoá = (nhà máy, updated_at, start, end) — admin sửa cấu hình là
     `updated_at` đổi → cache cũ tự hết hiệu lực. Xuất Excel ngay sau khi xem dùng lại đúng số đó.
Lỗi đọc KHÔNG cache (bấm Thử lại là đọc lại thật).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable

CACHE_TTL_S = 60.0
LOCK_WAIT_S = 15.0
BUSY_MESSAGE = "Đang đọc số liệu SCADA của nhà máy này — thử lại sau ít giây."

Reader = Callable[[dict, datetime, datetime | None], Any]

_clock = time.monotonic  # tách ra để test chỉnh được thời gian
_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()
_cache: dict[tuple, tuple[float, Any]] = {}
_cache_guard = threading.Lock()


class ScadaBusyError(Exception):
    """Nhà máy đang có lượt đọc SCADA khác chạy quá `LOCK_WAIT_S` giây → router trả 429."""


def factory_lock(factory_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(factory_id, threading.Lock())


def _cache_get(key: tuple) -> Any | None:
    with _cache_guard:
        hit = _cache.get(key)
        return hit[1] if hit and _clock() < hit[0] else None


def _cache_put(key: tuple, value: Any, ttl: float) -> None:
    now = _clock()
    with _cache_guard:
        # Dọn mục hết hạn mỗi lần ghi → cache không phình theo thời gian.
        for k in [k for k, (until, _) in _cache.items() if now >= until]:
            del _cache[k]
        _cache[key] = (now + ttl, value)


def clear_cache() -> None:
    with _cache_guard:
        _cache.clear()


def read(factory: dict, start: datetime | None, end: datetime | None, reader: Reader,
         ttl: float = CACHE_TTL_S) -> Any:
    """`reader(factory, start, end)` qua cache `ttl` giây + khoá theo nhà máy. Bận quá lâu →
    `ScadaBusyError`. Số lũy kế thời gian thực dùng `ttl` ngắn: nhiều người cùng mở màn vẫn chỉ
    một truy vấn SCADA mỗi `ttl` giây."""
    key = (factory["id"], factory.get("updated_at"), start, end)
    hit = _cache_get(key)
    if hit is not None:
        return hit
    lock = factory_lock(factory["id"])
    if not lock.acquire(timeout=LOCK_WAIT_S):
        raise ScadaBusyError(BUSY_MESSAGE)
    try:
        # Trong lúc chờ khoá, lượt trước có thể vừa đọc xong đúng kỳ này → dùng luôn, khỏi đọc lại.
        hit = _cache_get(key)
        if hit is None:
            hit = reader(factory, start, end)
            _cache_put(key, hit, ttl)
        return hit
    finally:
        lock.release()
