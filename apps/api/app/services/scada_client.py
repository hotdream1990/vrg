"""Đọc số liệu SCADA từ SQL Server của nhà máy (pymssql — wheel có sẵn FreeTDS, không cần ODBC).

Mọi lỗi kết nối/truy vấn được quy về `ScadaError` với câu tiếng Việt đọc được + thông điệp gốc
(đã decode) để admin tự khoanh vùng (mạng? tài khoản? linked server? tag?). Thông điệp KHÔNG BAO GIỜ
chứa mật khẩu — thông điệp gốc có lặp lại mật khẩu thì bỏ hẳn phần "Chi tiết".
⛔ SQL Server của SCADA là hệ thống OT đang chạy thật: module này CHỈ chạy SELECT/OPENQUERY.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import pymssql

from app.services import scada_historian_sql as hsql
from app.services.scada_errors import ScadaError, friendly_error  # noqa: F401 - API công khai cũ

def _collect_messages(conn: Any) -> list[str]:
    """Hứng MỌI thông điệp server (tag sai → exception chỉ còn "Statement(s) could not be prepared",
    câu có ích "Invalid column name 'X'" chỉ nằm ở đây). API nội bộ pymssql → thiếu thì bỏ qua."""
    msgs: list[str] = []

    def handler(_state: int, _severity: int, _srv: Any, _proc: Any, _line: int, text: Any) -> None:
        msg = text.decode("utf-8", "replace") if isinstance(text, bytes) else str(text)
        if msg.strip():
            msgs.append(re.sub(r"\s+", " ", msg).strip())

    try:
        conn._conn.set_msghandler(handler)
    except AttributeError:
        pass
    return msgs


@contextmanager
def _connect(factory: dict) -> Iterator[tuple[Any, list[str]]]:
    try:
        conn = pymssql.connect(
            server=factory["host"], port=str(factory["port"]), user=factory["username"],
            password=factory["password"], database=factory["database_name"],
            # timeout 30s: dưới ngưỡng 100s của Cloudflare và không giữ luồng API quá lâu khi
            # SCADA/VPN chậm (xem scada_read_guard — khoá theo nhà máy + cache).
            login_timeout=10, timeout=30, appname="VRG-SmartFactory")
    except pymssql.Error as exc:
        raise ScadaError(friendly_error(exc, factory, connected=False)) from exc
    try:
        yield conn, _collect_messages(conn)
    finally:
        conn.close()


def _query(session: tuple[Any, list[str]], factory: dict, sql: str,
           params: tuple | None = None) -> list[dict[str, Any]]:
    conn, msgs = session
    msgs.clear()  # chỉ giữ thông điệp của CÂU NÀY
    try:
        cur = conn.cursor(as_dict=True)
        cur.execute(sql, params)
        return list(cur.fetchall())
    except pymssql.Error as exc:
        raise ScadaError(friendly_error(exc, factory, connected=True, server_msgs=msgs)) from exc


def _tags(factory: dict) -> list[str]:
    tags = hsql.factory_tags(factory)
    if not tags:
        raise ScadaError("Nhà máy chưa khai tag nào (điện · nước · số bành) — vào Cấu hình để khai.")
    return tags


def _read(factory: dict, *builders: tuple) -> list[list[hsql.RawRow]]:
    """Dựng từng câu (hàm dựng, *tham số sau linked server/tags) rồi chạy trên MỘT kết nối."""
    tags = _tags(factory)
    try:
        sqls = [fn(factory["linked_server"], tags, *args) for fn, *args in builders]
    except ValueError as exc:
        raise ScadaError(f"Cấu hình nhà máy không hợp lệ: {exc}") from exc
    with _connect(factory) as session:
        return [hsql.map_rows(_query(session, factory, sql), tags) for sql in sqls]


def read_meters(factory: dict, start: datetime,
                end: datetime | None) -> tuple[list[hsql.RawRow], list[hsql.RawRow]]:
    """(mẫu theo giờ trong kỳ, mẫu theo phút 10' gần nhất) — MỘT kết nối, hai truy vấn."""
    hourly, latest = _read(factory, (hsql.range_query, start, end), (hsql.latest_query,))
    return hourly, latest


def read_latest(factory: dict) -> list[hsql.RawRow]:
    """Chỉ mẫu theo phút 10' gần nhất — số lũy kế thời gian thực (dòng cuối = lúc GetDate())."""
    return _read(factory, (hsql.latest_query,))[0]


#: Một câu: phiên bản + giờ máy SQL Server kèm múi (kiểm múi giờ/đồng hồ — mốc ngày dựa vào nó).
PROBE_SQL = ("SELECT @@VERSION AS version, "
             "CONVERT(varchar(33), SYSDATETIMEOFFSET(), 126) AS server_time")


def probe(factory: dict) -> tuple[str, str, list[hsql.RawRow]]:
    """Thử kết nối: (phiên bản SQL Server, giờ máy SQL Server dạng ISO kèm múi, mẫu phút gần nhất
    — rỗng nếu chưa khai tag)."""
    tags = hsql.factory_tags(factory)
    try:
        latest_sql = hsql.latest_query(factory["linked_server"], tags) if tags else None
    except ValueError as exc:
        raise ScadaError(f"Cấu hình nhà máy không hợp lệ: {exc}") from exc
    with _connect(factory) as session:
        rows = _query(session, factory, PROBE_SQL)
        first = rows[0] if rows else {}
        latest = hsql.map_rows(_query(session, factory, latest_sql), tags) if latest_sql else []
    version = str(first.get("version") or "").splitlines()
    return (version[0].strip() if version else ""), str(first.get("server_time") or ""), latest


#: Bảng `Tag` của Historian (CSDL Runtime) — tra tên tag cho admin khai cấu hình. Tham số hoá (%s).
TAG_SEARCH_SQL = ("SELECT TOP 50 TagName, Description FROM Tag "
                  "WHERE TagName LIKE %s OR Description LIKE %s ORDER BY TagName")


def search_tags(factory: dict, keyword: str) -> list[dict[str, str]]:
    """Tìm tag theo tên/mô tả (CHỈ ĐỌC, tối đa 50 dòng)."""
    pattern = f"%{keyword.strip()[:64]}%"
    with _connect(factory) as session:
        rows = _query(session, factory, TAG_SEARCH_SQL, (pattern, pattern))
    return [{"tag": str(r.get("TagName") or ""), "description": str(r.get("Description") or "")}
            for r in rows]
