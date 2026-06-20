"""Map crawler PriceRecord[] → BulletinData (world + physical prices).

Chạy crawler, quy đổi đơn vị, nhóm theo sàn/grade, tạo BulletinData
sẵn sàng cho generator.

Cần 2 ngày data (T-1 và T-2) để tính chênh lệch. Nếu chỉ có T-1,
cột prev sẽ để None.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

# Thêm đường dẫn crawlers vào sys.path để import
_CRAWLERS_DIR = Path(__file__).resolve().parent.parent.parent / "crawlers"
if str(_CRAWLERS_DIR) not in sys.path:
    sys.path.insert(0, str(_CRAWLERS_DIR))

from crawlers.base.models import PriceRecord, Source  # noqa: E402
from crawlers.run_crawl import run as run_crawl  # noqa: E402

from .convert import (  # noqa: E402
    cny_tonne_to_usd_tonne,
    jpy_kg_to_usd_tonne,
    usd_kg_to_usd_tonne,
    uscents_kg_to_usd_tonne,
)
from .models import BulletinData, PhysicalPriceRow, WorldPriceRow  # noqa: E402


def _to_usd_tonne(rec: PriceRecord, fx_rates: dict[str, float]) -> int | None:
    """Quy đổi PriceRecord sang USD/tấn. Trả None nếu thiếu FX."""
    if rec.unit == "US$/kg":
        return usd_kg_to_usd_tonne(rec.price)
    if rec.unit == "US cents/kg":
        return uscents_kg_to_usd_tonne(rec.price)
    if rec.unit == "CNY/tonne":
        rate = fx_rates.get("USD/CNY")
        return cny_tonne_to_usd_tonne(rec.price, rate) if rate else None
    if rec.unit == "JPY/kg":
        rate = fx_rates.get("USD/JPY")
        return jpy_kg_to_usd_tonne(rec.price, rate) if rate else None
    if rec.unit == "USD/tonne":
        return round(rec.price)
    return None


def _extract_fx(records: list[PriceRecord]) -> dict[str, float]:
    """Trích tỷ giá từ FX records: 'USD/CNY' → 7.2345."""
    fx = {}
    for r in records:
        if r.source == Source.FX:
            fx[r.grade] = r.price
    return fx


# Mapping: (source, grade từ crawler) → (exchange tên bản tin, grade bản tin)
_WORLD_GRADE_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("tocom", "RSS3"): ("OSE", "RSS3"),
    ("tocom", "TSR20"): ("OSE", "TSR20"),      # OSE = sàn Nhật (bản tin gọi OSE)
    ("shfe", "RU"): ("SHANGHAI", "RSS3"),       # SHFE Natural Rubber (mã RU) → bản tin ghi RSS3
    ("sgx", "RSS3"): ("SGX", "RSS3"),
    ("sgx", "TSR20"): ("SGX", "TSR20"),
    ("lgm", "SMRCV"): ("MRE", "SMRCV"),
    ("lgm", "SMR20"): ("MRE", "SMR20"),
    ("lgm", "LATEX"): ("MRE", "LATEX"),
}

# Mapping: grade ANRPC → grade bản tin physical
_PHYSICAL_GRADE_MAP: dict[str, str] = {
    "RSS3": "RSS3",
    "STR20": "STR20",
    "SMR20": "SMR20",
    "SIR20": "SIR20",
}


def build_from_crawl(report_date: date | None = None) -> BulletinData:
    """Chạy crawler, quy đổi, trả BulletinData (phần auto).

    Phần giá sàn VRG, mủ nguyên liệu, phân tích thị trường
    cần bổ sung thủ công sau khi gọi hàm này.
    """
    if report_date is None:
        report_date = date.today() - timedelta(days=1)
    prev_date = report_date - timedelta(days=1)

    results = run_crawl()
    all_records = [rec for r in results for rec in r.records]
    fx_rates = _extract_fx(all_records)

    # --- World prices ---
    world_prices = []
    for rec in all_records:
        key = (rec.source.value, rec.grade)
        mapping = _WORLD_GRADE_MAP.get(key)
        if not mapping:
            continue
        exchange, grade = mapping
        usd_t = _to_usd_tonne(rec, fx_rates)
        if usd_t is not None:
            world_prices.append(WorldPriceRow(
                exchange=exchange,
                grade=grade,
                unit="USD/T",
                price_prev=None,    # T-2 cần từ DB history
                price_curr=usd_t,
            ))

    # --- Physical prices (ANRPC) ---
    physical_prices = []
    for rec in all_records:
        if rec.source != Source.ANRPC:
            continue
        grade = _PHYSICAL_GRADE_MAP.get(rec.grade)
        if not grade:
            continue
        usd_t = _to_usd_tonne(rec, fx_rates)
        if usd_t is not None:
            physical_prices.append(PhysicalPriceRow(
                grade=grade,
                price_prev=None,    # T-2 cần từ DB
                price_curr=usd_t,
            ))

    # --- Exchange summary text (auto-generate từ data) ---
    exchange_summary = _build_exchange_summary(world_prices)

    return BulletinData(
        report_date=report_date,
        prev_date=prev_date,
        world_prices=world_prices,
        physical_prices=physical_prices,
        market_exchange_summary=exchange_summary,
    )


def _build_exchange_summary(world_prices: list[WorldPriceRow]) -> list[str]:
    """Tạo text tóm tắt giá từng sàn (Section IV.1)."""
    lines = []
    by_exchange: dict[str, list[WorldPriceRow]] = {}
    for wp in world_prices:
        by_exchange.setdefault(wp.exchange, []).append(wp)

    exchange_names = {
        "OSE": "Sàn TOCOM (Nhật Bản)",
        "SHANGHAI": "Sàn SHFE (Thượng Hải - Trung Quốc)",
        "SGX": "Sàn SGX (Singapore)",
        "MRE": "Sàn MRB (Malaysia)",
    }

    for exc_code, full_name in exchange_names.items():
        rows = by_exchange.get(exc_code, [])
        if not rows:
            continue
        parts = []
        for r in rows:
            price_str = f"{r.price_curr:,}" if r.price_curr else "N/A"
            chg = ""
            if r.change_abs is not None:
                direction = "tăng" if r.change_abs > 0 else "giảm"
                chg = f" {direction} {abs(r.change_abs):02d} usd/tấn ({abs(r.change_pct):.1f}%)"
            parts.append(f"{r.grade} giao dịch ở mức {price_str} usd/tấn{chg}")
        line = f"{full_name}: {'; '.join(parts)};"
        lines.append(line)

    return lines
