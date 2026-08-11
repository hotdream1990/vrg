"""TOCOM/OSE — cao su RSS3 & TSR20: SETTLEMENT của kỳ hạn có TRADING VALUE lớn nhất.

Cao su nằm ở sàn OSE (sau tái cơ cấu JPX 2020, không còn ở TOCOM). Nguồn: JPX OSE Daily Report ZIP
  https://www.jpx.co.jp/automation/markets/statistics-derivatives/daily/files/{YYYYMM}/
  Daily_Report_OSE_{YYYYMMDD}.zip → giải nén → cdf_dyr_{ngày}.pdf (Commodity Derivatives Futures)
  → trang RSS3 / TSR20 của THỊ TRƯỜNG ĐẤU GIÁ (競争売買/AuctionMarket), bỏ trang J-NET.
  Lưu ý: chữ 'ゴム' xuất hiện ở CHÚ THÍCH của mọi trang → lọc thật sự là auction + RSS/TSR.
Chọn kỳ hạn theo MAX TRADING VALUE (đúng spec lay-gia-cac-san.md). Đơn vị JPY/kg.
ZIP archive ~4 tháng; tự lùi ngày để lấy báo cáo mới nhất có sẵn (hôm nay có thể chưa đăng).
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import date, timedelta

from ..base.fetcher import fetch_bytes
from ..base.models import CrawlResult, PriceRecord, Source, Status

_ZIP = (
    "https://www.jpx.co.jp/automation/markets/statistics-derivatives/daily/files/"
    "{ym}/Daily_Report_OSE_{ymd}.zip"
)


def _zip_url(d: date) -> str:
    return _ZIP.format(ym=d.strftime("%Y%m"), ymd=d.strftime("%Y%m%d"))


def _recent_days(today: date, n: int = 7) -> list[date]:
    """today lùi dần, bỏ T7/CN — để thử báo cáo mới nhất có sẵn."""
    days, d = [], today
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return days


def _parse_row(line: str) -> dict | None:
    """1 dòng dữ liệu PDF → {contract, settle, trading_value}. Tách riêng để test offline.

    settle = số thập phân CUỐI dòng (sau OHLC + net change). trading_value = số có dấu phẩy
    lớn nhất ≥ 1 triệu (¥); dòng không giao dịch → 0.
    """
    line = line.strip()
    if not re.match(r"^\d{6}\s", line):
        return None
    toks = line.split()
    decimals = [t for t in toks if re.fullmatch(r"\d+\.\d+", t)]
    if not decimals:
        return None
    big = [
        int(t.replace(",", ""))
        for t in toks
        if re.fullmatch(r"\d{1,3}(,\d{3})+", t) and int(t.replace(",", "")) >= 1_000_000
    ]
    return {"contract": toks[0], "settle": float(decimals[-1]), "trading_value": max(big) if big else 0}


def _parse_rubber(pdf_bytes: bytes) -> dict[str, list[dict]]:
    import pdfplumber  # lazy: chỉ cần khi crawl thật

    out: dict[str, list[dict]] = {}
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "ゴム" not in t or ("AuctionMarket" not in t and "競争売買" not in t):
                continue
            grade = "RSS3" if "RSS" in t else ("TSR20" if "TSR" in t else None)
            if not grade or grade in out:
                continue
            rows = [r for r in (_parse_row(line) for line in t.split("\n")) if r]
            if rows:
                out[grade] = rows
    return out


def _pick(rows: list[dict]) -> dict | None:
    """Kỳ hạn có Trading Value lớn nhất.

    KHÔNG kỳ hạn nào giao dịch → None = phiên đó grade này KHÔNG GIAO DỊCH (No Trading).
    Trước 0.4.13 hàm này trả kỳ hạn đầu (front): settlement lý thuyết của kỳ hạn không giao
    dịch bị JPX giữ nguyên nhiều phiên liền → hệ thống lưu lại một con số đứng im như thể là
    giá thật (vd OSE TSR20 = 350 JPY/kg suốt 03–07/08/2026).
    """
    traded = [r for r in rows if r["trading_value"] > 0]
    return max(traded, key=lambda r: r["trading_value"]) if traded else None


def _pdf_for(day: date) -> bytes | None:
    """Tải ZIP của đúng 1 ngày → bytes PDF cdf_dyr (None nếu ngày đó không có report)."""
    try:
        zbytes = fetch_bytes(_zip_url(day))
    except Exception:  # noqa: BLE001 - ngày này không có
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
            name = next((n for n in zf.namelist() if re.search(r"cdf_dyr_\d+\.pdf$", n)), None)
            return zf.read(name) if name else None
    except zipfile.BadZipFile:
        return None


def _records_for(pdf_bytes: bytes, day: date, keep_curve: bool = True) -> list[PriceRecord]:
    records: list[PriceRecord] = []
    for grade, rows in _parse_rubber(pdf_bytes).items():
        if not rows:
            continue
        # Không kỳ hạn nào giao dịch → giá 0 = No Trading (quy ước chung), KHÔNG lấy settlement
        # lý thuyết của kỳ hạn front đắp vào.
        best = _pick(rows)
        extra = {"exchange": "OSE/TOCOM", "selection": "max_trading_value",
                 "trading_value": best["trading_value"] if best else 0,
                 "no_trading": best is None}
        if keep_curve:
            extra["curve"] = rows
        records.append(
            PriceRecord(
                source=Source.TOCOM,
                grade=grade,
                price=best["settle"] if best else 0.0,
                currency="JPY",
                unit="JPY/kg",
                price_type="settlement",
                as_of=day,
                contract=best["contract"] if best else "",
                extra=extra,
            )
        )
    return records


def crawl(as_of: date | None = None) -> CrawlResult:
    """Lấy settlement phiên OSE mới nhất có báo cáo (báo cáo hôm nay đăng vào buổi tối JST).

    `as_of` của bản ghi LUÔN là ngày của báo cáo — ngày OSE nghỉ thì không sinh bản ghi cho ngày
    đó. Lùi ngày là để chờ báo cáo được đăng, KHÔNG phải đắp giá cũ sang ngày mới; khi có lùi thì
    ghi rõ trong `note` để trang Quét đa sàn thấy phiên nào đang được lấy.
    """
    try:
        want = as_of or date.today()
        for d in _recent_days(want):
            pdf = _pdf_for(d)
            if pdf and (records := _records_for(pdf, d)):
                note = (None if d == want else
                        f"OSE chưa có báo cáo ngày {want:%d/%m/%Y} — lấy phiên {d:%d/%m/%Y}.")
                if all(r.price == 0 for r in records):
                    note = f"Phiên {d:%d/%m/%Y}: OSE không có giao dịch cao su (No Trading)."
                return CrawlResult(source=Source.TOCOM, status=Status.OK, records=records, note=note)
        return CrawlResult(source=Source.TOCOM, status=Status.EMPTY, note="Không tải được OSE Daily Report ZIP")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.TOCOM, status=Status.ERROR, note=str(exc))


def history(days: int = 45, end: date | None = None) -> list[PriceRecord]:
    """Backfill RSS3+TSR20: settlement (max trading value) cho ~`days` phiên gần nhất.

    Chậm hơn SHFE (mỗi ngày = 1 ZIP + parse PDF). ZIP chỉ lưu ~4 tháng.
    """
    out: list[PriceRecord] = []
    d = end or date.today()
    got, scanned, max_scan = 0, 0, days * 2 + 30
    while got < days and scanned < max_scan:
        scanned += 1
        if d.weekday() < 5:
            pdf = _pdf_for(d)
            if pdf and (recs := _records_for(pdf, d, keep_curve=False)):
                out.extend(recs)
                got += 1
        d -= timedelta(days=1)
    return out
