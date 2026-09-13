"""Tỷ giá USD — Close hằng ngày: CNY/JPY/THB (x-rates) · VND (Vietcombank) · MYR (BNM).

CNY/JPY/THB — x-rates.com, trang "Historical Rates" theo ngày (HTTP thường, không Cloudflare).
  Trước 03/09/2026 lấy từ exchangerates.org.uk (nguồn Ban TTKD dùng) nhưng trang đó đã đổi giao
  diện: trang conversion KHÔNG còn bảng "Exchange Rate History" có ngày; trang lịch sử + API biểu
  đồ nằm sau Cloudflare (thách thức/chặn hẳn) → bỏ, không lách chặn bot.
  GOTCHA ngày: trang x-rates ngày X là ẢNH CHỤP lúc ~00:00 UTC ngày X = giá đóng cửa ngày X-1
  (đo khớp giờ với Yahoo). Vì vậy Close ngày D = trang ngày D+1. Đối chiếu 43 phiên 06/07–02/09
  với số exchangerates đã lưu: lệch trung vị JPY 1,2 · CNY 0,8 · THB 2,4 bps.
  GOTCHA "hôm nay": trang của ngày chưa chốt trả tỷ giá LIVE (nhãn giờ = giờ hiện tại) → chỉ nhận
  ngày X < hôm nay (UTC) VÀ nhãn giờ đúng nhãn ảnh chụp đã chốt; sai → bỏ, không đoán.
  Chỉ phát hành Thứ 2–6 (sàn không giao dịch cuối tuần; không nhân bản giá thứ Sáu sang thứ Bảy).
VND: TỪ VIETCOMBANK (API công khai có date param) — "USD/VND (Mua)" (chuyển khoản) và
  "USD/VND (Bán)", đồng bộ với phiếu Báo giá mủ.
MYR: TỪ BNM (Ngân hàng TW Malaysia) API — buying_rate phiên 12:00 (đúng nguồn chuyên viên,
  rateType=BR, quote=rm); dùng quy đổi Latex LGM (Sen ÷ USD/MYR × 10). API theo tháng.
LÀM TRÒN: crawler giữ 4 số lẻ như nguồn cũ (CNY 4 · THB 4 · MYR 4); chuẩn hoá riêng khi LƯU
(USD/JPY 2 số lẻ theo file gốc Ban TTKD) nằm ở 1 chỗ duy nhất — `app.services.price_repo`.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from ..base.fetcher import fetch_json, fetch_text
from ..base.models import CrawlResult, PriceRecord, Source, Status

_XR_URL = "https://www.x-rates.com/historical/?from=USD&amount=1&date={d}"
_XR_CODES = ("CNY", "JPY", "THB")  # CNY/JPY quy futures→USD · THB quy physical Thái
_XR_LOOKBACK_DAYS = 7  # mỗi lần quét lấp lại 7 ngày gần nhất → tự lành khi lỡ vài lần quét
# Nhãn giờ của trang ngày ĐÃ CHỐT (mọi ngày quá khứ đều in đúng nhãn này); trang live in giờ hiện tại.
_XR_SNAPSHOT_STAMP = "16:00 UTC"
_XR_STAMP = re.compile(r'class="ratesTimestamp">([^<]+)<')
_XR_RATE = re.compile(r"from=USD&amp;to=([A-Z]{3})'>([\d.]+)<")

_VCB_URL = "https://www.vietcombank.com.vn/api/exchangerates?date={d}"  # VND: nguồn Vietcombank
# BNM (Malaysia) — buying_rate phiên 12:00, quote=rm (đúng nguồn chuyên viên). {path}='' hoặc '/year/Y/month/M'.
_BNM_URL = "https://api.bnm.gov.my/public/exchange-rate/USD{path}?session=1200&quote=rm"
_BNM_HEADERS = {"Accept": "application/vnd.BNM.API.v1+json"}
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _rec(code: str, as_of: date, rate: float) -> PriceRecord:
    return PriceRecord(source=Source.FX, grade=f"USD/{code}", price=rate, currency=code,
                       unit=f"{code} per USD", price_type="fx", as_of=as_of)


def _parse_xrates(html: str) -> dict[str, float]:
    """{mã: tỷ giá} từ 1 trang lịch sử x-rates ĐÃ CHỐT. Trang live/lạ/bị chặn → {}. Offline-testable."""
    stamp = _XR_STAMP.search(html)
    if not stamp or not stamp.group(1).strip().endswith(_XR_SNAPSHOT_STAMP):
        return {}
    rates: dict[str, float] = {}
    for code, value in _XR_RATE.findall(html):  # bảng xuất hiện 2 lần (top-10 + đầy đủ) → giữ lần đầu
        if code in _XR_CODES and code not in rates:
            rates[code] = round(float(value), 4)
    return rates


def _xrates_closes(first: date, last: date, today: date | None = None) -> list[PriceRecord]:
    """Close CNY/JPY/THB các ngày Thứ 2–6 trong [first, last]. Close ngày D = ảnh chụp ngày D+1.

    Chỉ nhận ảnh chụp của ngày < hôm nay (UTC). Lỗi mạng → dừng luôn (không kéo dài cả lượt quét).
    """
    today = today or datetime.now(timezone.utc).date()
    out: list[PriceRecord] = []
    d = first
    while d <= last:
        snap = d + timedelta(days=1)
        if snap >= today:
            break
        if d.weekday() < 5:
            try:
                html = fetch_text(_XR_URL.format(d=snap.isoformat()), retries=2)
            except Exception:  # noqa: BLE001 - nguồn sập → dừng, crawl() ghi chú thiếu cặp nào
                break
            out.extend(_rec(code, d, rate) for code, rate in _parse_xrates(html).items())
        d += timedelta(days=1)
    return out


def _vcb_usd(day: date | None = None) -> tuple[date, float | None, float | None] | None:
    """(ngày, mua CK, bán) USD từ VCB theo ngày (mặc định hôm nay). None nếu lỗi/không có USD."""
    d = (day or datetime.now(timezone.utc).date()).isoformat()
    try:
        data = fetch_json(_VCB_URL.format(d=d),
                          headers={"User-Agent": _UA, "Accept": "application/json"})
    except Exception:  # noqa: BLE001
        return None
    usd = next((x for x in data.get("Data", []) if x.get("currencyCode") == "USD"), None)
    if not usd:
        return None

    def _num(v: object) -> float | None:
        s = str(v).replace(",", "").strip()
        try:
            return float(s) if s and s != "-" else None
        except ValueError:
            return None

    src = str(data.get("Date") or d)[:10]
    try:
        as_of = date.fromisoformat(src)
    except ValueError:
        as_of = date.fromisoformat(d)
    return as_of, _num(usd.get("transfer")), _num(usd.get("sell"))


def _vnd_records(day: date | None = None) -> list[PriceRecord]:
    """USD/VND Mua (chuyển khoản) + Bán từ VCB → list PriceRecord (rỗng nếu lỗi)."""
    got = _vcb_usd(day)
    if not got:
        return []
    as_of, ck, ban = got
    out: list[PriceRecord] = []
    if ck is not None:
        out.append(PriceRecord(source=Source.FX, grade="USD/VND (Mua)", price=ck,
                               currency="VND", unit="VND per USD", price_type="fx", as_of=as_of))
    if ban is not None:
        out.append(PriceRecord(source=Source.FX, grade="USD/VND (Bán)", price=ban,
                               currency="VND", unit="VND per USD", price_type="fx", as_of=as_of))
    return out


def _bnm_myr(day: date | None = None) -> list[PriceRecord]:
    """USD/MYR từ BNM (buying_rate, phiên 12:00). day=None → mới nhất; có day → cả tháng đó.

    quote=rm → RM per 1 USD (≈4,07), cùng chiều với các cặp USD/xxx khác. rateType=BR = buying_rate.
    """
    path = f"/year/{day.year}/month/{day.month}" if day else ""
    try:
        data = fetch_json(_BNM_URL.format(path=path), headers=_BNM_HEADERS)
    except Exception:  # noqa: BLE001
        return []
    rate = (data or {}).get("data", {}).get("rate")
    items = rate if isinstance(rate, list) else ([rate] if rate else [])
    out: list[PriceRecord] = []
    for r in items:
        buying, d = r.get("buying_rate"), r.get("date")
        try:
            as_of = date.fromisoformat(str(d))
        except (TypeError, ValueError):
            continue
        if buying:
            out.append(_rec("MYR", as_of, round(float(buying), 4)))
    return out


def crawl() -> CrawlResult:
    """Quét tỷ giá: CNY/JPY/THB (x-rates, lấp 7 ngày) + VND (VCB) + MYR (BNM). Cô lập lỗi từng nguồn."""
    notes: list[str] = []
    today = datetime.now(timezone.utc).date()
    records = _xrates_closes(today - timedelta(days=_XR_LOOKBACK_DAYS), today, today)
    missing = [c for c in _XR_CODES if not any(r.grade == f"USD/{c}" for r in records)]
    if missing:
        notes.append("x-rates thiếu: " + ",".join(missing))
    vnd = _vnd_records()
    if vnd:
        records.extend(vnd)
    else:
        notes.append("VND (VCB) lỗi")
    myr = _bnm_myr()
    if myr:
        records.extend(myr)
    else:
        notes.append("MYR (BNM) lỗi")
    note = "; ".join(notes) or None
    if records:
        return CrawlResult(source=Source.FX, status=Status.OK, records=records, note=note)
    return CrawlResult(source=Source.FX, status=Status.BLOCKED, note=note or "Không lấy được tỷ giá")


def history(days: int) -> list[PriceRecord]:
    """Backfill `days` ngày gần nhất: CNY/JPY/THB (x-rates) · VND (VCB từng ngày) · MYR (BNM theo tháng).

    ⚠ Khoảng lùi chạm ≤ 02/09/2026 sẽ GHI ĐÈ số exchangerates cũ bằng số x-rates (lệch vài bps).
    """
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=days)
    records = _xrates_closes(since, today, today)

    # VND (Mua/Bán) từ VCB — API có date param nên backfill được từng ngày trong khoảng.
    day = today
    for _ in range(days + 1):
        records.extend(_vnd_records(day))
        day -= timedelta(days=1)

    # MYR từ BNM — API trả theo tháng; quét các tháng phủ khoảng [since, hôm nay].
    seen_months: set[tuple[int, int]] = set()
    day = today
    for _ in range(days + 1):
        key = (day.year, day.month)
        if key not in seen_months:
            seen_months.add(key)
            records.extend(m for m in _bnm_myr(day) if m.as_of >= since)
        day -= timedelta(days=1)
    return records
