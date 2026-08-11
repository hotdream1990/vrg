"""SGX / SICOM — TSR20 (mã TF) & RSS3 (mã RT): settlement của kỳ hạn giao THÁNG SAU.

Nguồn: **báo cáo Daily Futures chính thức của SGX** — mỗi PHIÊN đúng 1 file:
  `https://links.sgx.com/1.0.0/derivatives-daily/{id}/FUTURE.zip` → `MMDDFUT.csv`
  `DATE,COM,COM_MM,COM_YY,OPEN,HIGH,LOW,CLOSE,SETTLE,VOLUME,OINT,SERIES`
`id` tăng 1 sau MỖI phiên (ngày sàn nghỉ không có id) → dò id từ mốc neo rồi **đối chiếu cột
DATE**: chỉ nhận đúng phiên cần lấy, không có thì thôi (giống cách lấy báo cáo ngày của OSE).

Vì sao BỎ API live-quote `contract-code` (dùng tới 0.4.12): field `base-date` của API nhảy sang
phiên mới TRƯỚC khi sàn ra settlement mới — và nhảy cả vào ngày sàn không ra settlement — nên
settlement của phiên cũ bị đóng dấu sang ngày sau. Thực tế 10/08/2026: SGX không ra settlement
cho cao su (SETTLE=0 trong file chính thức) nhưng API vẫn trả 273.9 của phiên 07/08 → hệ thống
ghi 273.9 cho cả 10/08 lẫn 11/08. File theo phiên không thể sai ngày như vậy.

**SETTLE = 0** trong file chính thức = phiên đó KHÔNG CÓ GIAO DỊCH / không ra settlement →
giữ nguyên 0 (quy ước toàn hệ thống: giá 0 = *No Trading*), KHÔNG lấy giá phiên cũ đắp vào.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime, timedelta, timezone

from ..base.fetcher import fetch_bytes
from ..base.models import CrawlResult, PriceRecord, Source, Status

_SGT = timezone(timedelta(hours=8))  # SGX = giờ Singapore (UTC+8)

URL = "https://links.sgx.com/1.0.0/derivatives-daily/{id}/FUTURE.zip"
SYMBOLS = {"TF": "TSR20", "RT": "RSS3"}  # mã SGX → grade bản tin

# Mốc neo đã đối chiếu tay: id 7572 = phiên 07/08/2026 (kiểm bằng cột DATE trong file).
_ANCHOR_ID, _ANCHOR_DAY = 7572, date(2026, 8, 7)
_MAX_PROBE = 12  # số lần dò id tối đa (thường 1–3 lần là trúng)


def _weekdays(a: date, b: date) -> int:
    """Số ngày trong tuần (T2–T6) giữa a và b, có DẤU — ước lượng số phiên để đoán id.

    Luôn ≥ số phiên thật (ngày nghỉ lễ không có id) nên id ước lượng luôn ≥ id thật → dò LÙI.
    """
    if b < a:
        return -_weekdays(b, a)
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def _session(report_id: int) -> tuple[date, list[dict[str, str]]] | None:
    """1 id → (ngày phiên, các dòng CSV). None nếu id chưa có (SGX trả trang HTML, không phải ZIP)."""
    try:
        blob = fetch_bytes(URL.format(id=report_id))
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            name = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
            text = zf.read(name).decode("utf-8", "ignore") if name else ""
    except Exception:  # noqa: BLE001 - id chưa có / lỗi mạng → coi như không có phiên
        return None
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return None
    try:
        return datetime.strptime(str(rows[0]["DATE"]).strip(), "%Y%m%d").date(), rows
    except (KeyError, ValueError):
        return None


def _report_for(day: date) -> list[dict[str, str]] | None:
    """Báo cáo ĐÚNG phiên `day`. None = SGX không có phiên đó (nghỉ) hoặc chưa đăng."""
    probe, step, seen = _ANCHOR_ID + _weekdays(_ANCHOR_DAY, day), 1, set()
    for _ in range(_MAX_PROBE):
        if probe < 1 or probe in seen:
            return None
        seen.add(probe)
        got = _session(probe)
        if got is None:  # chưa đăng → lùi nhanh dần (1, 2, 4, 8…) cho khỏi phụ thuộc số ngày nghỉ
            probe -= step
            step *= 2
            continue
        got_day, rows = got
        if got_day == day:
            return rows
        probe, step = probe + _weekdays(got_day, day), 1
    return None


def _latest_session() -> tuple[int, date, list[dict[str, str]]] | None:
    """Phiên MỚI NHẤT SGX đã đăng → (id, ngày, dòng CSV)."""
    probe, step = _ANCHOR_ID + _weekdays(_ANCHOR_DAY, datetime.now(_SGT).date()), 1
    for _ in range(_MAX_PROBE):
        if probe < 1:
            return None
        got = _session(probe)
        if got is None:
            probe -= step
            step *= 2
            continue
        for _ in range(_MAX_PROBE):  # leo lên nếu ước lượng còn thấp hơn phiên mới nhất
            nxt = _session(probe + 1)
            if nxt is None:
                break
            probe, got = probe + 1, nxt
        return probe, got[0], got[1]
    return None


def _target_delivery_month(session_day: date) -> tuple[int, int]:
    """Kỳ hạn cần lấy = THÁNG SAU tháng của PHIÊN đang lấy (đúng chỉ số chuyên viên) → (năm, tháng)."""
    if session_day.month == 12:
        return session_day.year + 1, 1
    return session_day.year, session_day.month + 1


def _num(v: object) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _records(day: date, rows: list[dict[str, str]]) -> list[PriceRecord]:
    """Lọc RT/TF kỳ hạn tháng sau → PriceRecord. SETTLE rỗng → bỏ; SETTLE 0 → giữ (No Trading)."""
    year, month = _target_delivery_month(day)
    out: list[PriceRecord] = []
    for r in rows:
        grade = SYMBOLS.get(str(r.get("COM", "")).strip())
        if not grade or _num(r.get("COM_MM")) != month or _num(r.get("COM_YY")) != year:
            continue
        settle = _num(r.get("SETTLE"))
        if settle is None:
            continue
        out.append(
            PriceRecord(
                source=Source.SGX,
                grade=grade,
                price=settle,
                currency="USc",  # US cents (không phải USD) — giá yết bằng cent/kg
                unit="US cents/kg",
                price_type="settlement",
                as_of=day,
                contract=f"{year:04d}-{month:02d}",
                extra={"volume": _num(r.get("VOLUME")), "open_interest": _num(r.get("OINT")),
                       "no_trading": settle == 0},
            )
        )
    return out


def crawl(as_of: date | None = None) -> CrawlResult:
    """Settlement 1 phiên: `as_of` cụ thể, hoặc phiên mới nhất SGX đã đăng."""
    try:
        if as_of:
            rows = _report_for(as_of)
            if rows is None:
                return CrawlResult(
                    source=Source.SGX, status=Status.EMPTY,
                    note=f"SGX chưa có báo cáo phiên {as_of:%d/%m/%Y} (nghỉ hoặc chưa đăng).")
            day = as_of
        else:
            got = _latest_session()
            if got is None:
                return CrawlResult(source=Source.SGX, status=Status.EMPTY,
                                   note="Không tải được báo cáo Daily Futures của SGX.")
            _, day, rows = got
        records = _records(day, rows)
        if not records:
            return CrawlResult(source=Source.SGX, status=Status.EMPTY,
                               note=f"Phiên {day:%d/%m/%Y}: không có kỳ hạn RT/TF giao tháng sau.")
        note = (f"Phiên {day:%d/%m/%Y}: SGX không ra settlement cho cao su (No Trading)."
                if all(r.price == 0 for r in records) else None)
        return CrawlResult(source=Source.SGX, status=Status.OK, records=records, note=note)
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.SGX, status=Status.ERROR, note=str(exc))


def history(days: int = 45) -> list[PriceRecord]:
    """Backfill: settlement RSS3+TSR20 của `days` phiên gần nhất (mỗi phiên 1 file)."""
    latest = _latest_session()
    if not latest:
        return []
    last_id = latest[0]
    out = _records(latest[1], latest[2])
    for i in range(last_id - 1, max(last_id - days, 0), -1):
        if (got := _session(i)) is not None:
            out.extend(_records(got[0], got[1]))
    return out
