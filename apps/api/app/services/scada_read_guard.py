"""Chống treo API + dồn tải lên SCADA khi đọc chỉ số theo ngày.

Vì sao cần: endpoint `/meters/daily` là `def` đồng bộ chạy trong threadpool (~40 luồng) DÙNG CHUNG với
mọi endpoint khác (kể cả đăng nhập). Mỗi lượt đọc SCADA có thể giữ luồng hàng chục giây khi VPN/SCADA
chậm; bấm lại liên tục hoặc nhiều người cùng xem thì cả app treo, đồng thời đè truy vấn Historian
lên hệ thống OT đang chạy thật của nhà máy. Hai lớp chặn:
  1. Khoá theo TỪNG nhà máy: mỗi nhà máy chỉ một lượt đọc SCADA tại một thời điểm; lượt sau chờ tối
     đa `LOCK_WAIT_S` giây rồi báo bận (router → 429) thay vì xếp hàng vô hạn.
  2. Cache kết quả đọc thô 60 giây, khoá = (nhà máy, updated_at, start, end, scope) — admin sửa
     cấu hình là `updated_at` đổi → cache cũ tự hết hiệu lực. Xuất Excel ngay sau khi xem dùng lại
     đúng số đó.
Lỗi đọc KHÔNG cache (bấm Thử lại là đọc lại thật).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable

CACHE_TTL_S = 60.0
LOCK_WAIT_S = 15.0
#: Lượt đọc "sống" (poll 5–10 s, `live=True`): chờ khoá ngắn rồi trả SỐ VỪA ĐỌC thay vì giữ luồng 15 s
#: → 429 (review 01/10/2026: ~50 người xem lúc SCADA chậm là hết threadpool chung của cả app).
LIVE_LOCK_WAIT_S = 2.0
#: Lượt đọc sống vừa lỗi → nhớ lỗi chừng này giây, không mở lại kết nối SQL Server qua VPN mỗi nhịp poll.
LIVE_ERROR_TTL_S = 10.0
BUSY_MESSAGE = "Đang đọc số liệu SCADA của nhà máy này — thử lại sau ít giây."

Reader = Callable[[dict, datetime, datetime | None], Any]

_clock = time.monotonic  # tách ra để test chỉnh được thời gian
_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()
_cache: dict[tuple, tuple[float, Any]] = {}
_cache_guard = threading.Lock()
# Chỉ cho lượt đọc sống (khoá có scope cố định → số khoá hữu hạn, không phình theo thời gian).
_last_good: dict[tuple, Any] = {}
_last_error: dict[tuple, tuple[float, Exception]] = {}


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
        _last_good.clear()
        _last_error.clear()


def read(factory: dict, start: datetime | None, end: datetime | None, reader: Reader,
         ttl: float = CACHE_TTL_S, scope: str = "", live: bool = False) -> Any:
    """`reader(factory, start, end)` qua cache `ttl` giây + khoá theo nhà máy. Bận quá lâu →
    `ScadaBusyError`. Số lũy kế thời gian thực dùng `ttl` ngắn: nhiều người cùng mở màn vẫn chỉ
    một truy vấn SCADA mỗi `ttl` giây. `scope` tách các lượt đọc KHÁC TAG cùng kỳ (vd sơ đồ vận
    hành `plant`) — thiếu nó hai màn dùng nhầm cache của nhau. `live=True`: bận thì trả số vừa đọc
    (web đã có `at` để biết số cũ), lỗi thì nhớ `LIVE_ERROR_TTL_S` giây."""
    key = (factory["id"], factory.get("updated_at"), start, end, scope)
    hit = _cache_get(key)
    if hit is not None:
        return hit
    if live:
        with _cache_guard:
            err = _last_error.get(key)
        if err and _clock() < err[0]:
            raise err[1]
    lock = factory_lock(factory["id"])
    if not lock.acquire(timeout=LIVE_LOCK_WAIT_S if live else LOCK_WAIT_S):
        with _cache_guard:
            stale = _last_good.get(key) if live else None
        if stale is not None:
            return stale
        raise ScadaBusyError(BUSY_MESSAGE)
    try:
        # Trong lúc chờ khoá, lượt trước có thể vừa đọc xong đúng kỳ này → dùng luôn, khỏi đọc lại.
        hit = _cache_get(key)
        if hit is None:
            try:
                hit = reader(factory, start, end)
            except Exception as exc:
                if live:
                    with _cache_guard:
                        _last_error[key] = (_clock() + LIVE_ERROR_TTL_S, exc)
                raise
            _cache_put(key, hit, ttl)
            if live:
                with _cache_guard:
                    _last_good[key] = hit
                    _last_error.pop(key, None)
        return hit
    finally:
        lock.release()
