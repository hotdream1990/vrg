"""Tỷ giá USD — Close hằng ngày: CNY/JPY/THB (exchangerates, dự phòng x-rates) · VND (VCB) · MYR (BNM).

CNY/JPY/THB — NGUỒN CHÍNH exchangerates.org.uk (đúng nguồn Ban TTKD dùng), xem `fx_exchangerates`.
  Đồng nào nguồn chính không ra phiên nào → lấy từ x-rates.com (`fx_xrates`, lệch vài bps) và GHI
  CHÚ rõ trong kết quả quét (lượt quét thành "cảnh báo") để chuyên viên biết số không cùng nguồn Excel.
  Mỗi lần quét lấp lại 7 ngày gần nhất → tự lành khi lỡ vài lần quét. Chỉ Thứ 2–6.
VND: TỪ VIETCOMBANK (API công khai có date param) — "USD/VND (Mua)" (chuyển khoản) và
  "USD/VND (Bán)", đồng bộ với phiếu Báo giá mủ.
MYR: TỪ BNM (Ngân hàng TW Malaysia) API — buying_rate phiên 12:00 (đúng nguồn chuyên viên,
  rateType=BR, quote=rm); dùng quy đổi Latex LGM (Sen ÷ USD/MYR × 10). API theo tháng.
LÀM TRÒN: crawler giữ 4 số lẻ (CNY 4 · THB 4 · MYR 4); chuẩn hoá riêng khi LƯU
(USD/JPY 2 số lẻ theo file gốc Ban TTKD) nằm ở 1 chỗ duy nhất — `app.services.price_repo`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from ..base.fetcher import fetch_json
from ..base.models import CrawlResult, PriceRecord, Source, Status
from . import fx_exchangerates, fx_xrates

_CODES = ("CNY", "JPY", "THB")  # CNY/JPY quy futures→USD · THB quy physical Thái
_LOOKBACK_DAYS = 7  # mỗi lần quét lấp lại 7 ngày gần nhất

_VCB_URL = "https://www.vietcombank.com.vn/api/exchangerates?date={d}"  # VND: nguồn Vietcombank
# BNM (Malaysia) — buying_rate phiên 12:00, quote=rm (đúng nguồn chuyên viên). {path}='' hoặc '/year/Y/month/M'.
_BNM_URL = "https://api.bnm.gov.my/public/exchange-rate/USD{path}?session=1200&quote=rm"
_BNM_HEADERS = {"Accept": "application/vnd.BNM.API.v1+json"}
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _rec(code: str, as_of: date, rate: float) -> PriceRecord:
    return PriceRecord(source=Source.FX, grade=f"USD/{code}", price=rate, currency=code,
                       unit=f"{code} per USD", price_type="fx", as_of=as_of)


def _asia_closes(since: date, today: date) -> tuple[list[PriceRecord], list[str]]:
    """Close CNY/JPY/THB since..hôm qua: exchangerates trước, đồng nào trống → x-rates. (records, ghi chú).

    Dự phòng xét THEO ĐỒNG: exchangerates không ra phiên nào của đồng đó mới gọi x-rates. Đồng có số
    nhưng hụt vài ngày giữa khoảng thì KHÔNG bù bằng x-rates (tránh trộn 2 nguồn trong 1 chuỗi) — lượt
    quét sau tự lấp, còn thiếu kéo dài thì `fx_freshness` cảnh báo.
    """
    records, errors = fx_exchangerates.closes(since, today, _CODES, _rec)
    missing = tuple(c for c in _CODES if not any(r.grade == f"USD/{c}" for r in records))
    if not missing:
        return records, []
    backup = fx_xrates.closes(since, today, today, missing, _rec)
    records.extend(backup)
    rescued = [c for c in missing if any(r.grade == f"USD/{c}" for r in backup)]
    lost = [c for c in missing if c not in rescued]
    notes = []
    if rescued:
        why = ", ".join(f"{c}: {errors.get(c, '?')}" for c in rescued)
        notes.append(f"exchangerates lỗi ({why}) → dùng x-rates dự phòng")
    if lost:
        notes.append("tỷ giá thiếu: " + ",".join(lost))
    return records, notes


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
    """Quét tỷ giá: CNY/JPY/THB (lấp 7 ngày) + VND (VCB) + MYR (BNM). Cô lập lỗi từng nguồn."""
    today = datetime.now(timezone.utc).date()
    records, notes = _asia_closes(today - timedelta(days=_LOOKBACK_DAYS), today)
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
    """Backfill `days` ngày gần nhất: CNY/JPY/THB · VND (VCB từng ngày) · MYR (BNM theo tháng).

    exchangerates chỉ giữ ~10 phiên nên CNY/JPY/THB chỉ lấp được trong khoảng đó. ⚠ Nếu nguồn chính
    lỗi, dự phòng x-rates lùi bao xa cũng được → có thể GHI ĐÈ số exchangerates đã lưu (lệch vài bps).
    """
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=days)
    records, _ = _asia_closes(since, today)

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
