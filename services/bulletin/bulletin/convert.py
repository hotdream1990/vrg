"""Quy đổi đơn vị giá từ crawler → USD/tấn (đơn vị bản tin).

Crawlers trả về đơn vị gốc của sàn:
  - SHFE: CNY/tonne
  - TOCOM/OSE: JPY/kg
  - LGM: US cents/kg  (Latex: Sen/kg — quy đổi USD/T bằng tỷ giá USD/MYR: Sen ÷ USD/MYR × 10)
  - ANRPC: US$/kg
  - FX: per USD (ví dụ 1 USD = 25,800 VND)
"""

from __future__ import annotations


def cny_tonne_to_usd_tonne(price_cny: float, usd_cny: float) -> int:
    """CNY/tấn → USD/tấn (SHFE)."""
    return round(price_cny / usd_cny)


def jpy_kg_to_usd_tonne(price_jpy_per_kg: float, usd_jpy: float) -> int:
    """JPY/kg → USD/tấn (TOCOM/OSE).  1 tấn = 1000 kg."""
    return round(price_jpy_per_kg * 1000 / usd_jpy)


def uscents_kg_to_usd_tonne(price_cents: float) -> int:
    """US cents/kg → USD/tấn (LGM).  100 cents = 1 USD, 1 tấn = 1000 kg."""
    return round(price_cents * 1000 / 100)


def usd_kg_to_usd_tonne(price_usd_per_kg: float) -> int:
    """US$/kg → USD/tấn (ANRPC physical)."""
    return round(price_usd_per_kg * 1000)


# Đơn vị gốc của sàn → cặp tỷ giá cần để quy đổi sang USD (None nếu đã là USD).
_FX_PAIR_FOR_UNIT = {"CNY/tonne": "USD/CNY", "JPY/kg": "USD/JPY"}


def to_usd_tonne_detail(
    price: float, unit: str, fx_rates: dict[str, float]
) -> tuple[int | None, str | None, float | None]:
    """Quy đổi 1 giá gốc → (usd_tonne, fx_pair, fx_rate). 1 NGUỒN quy đổi dùng chung.

    fx_pair/fx_rate = None khi đơn vị đã ở hệ USD (US$/kg, US cents/kg).
    Thiếu tỷ giá → usd_tonne None nhưng vẫn trả fx_pair để UI báo rõ.
    """
    if unit in ("USD/tonne", "USD/T"):
        return round(price), None, None
    if unit == "US$/kg":
        return usd_kg_to_usd_tonne(price), None, None
    if unit == "US cents/kg":
        return uscents_kg_to_usd_tonne(price), None, None
    if unit == "Sen/kg":
        # LGM Latex yết Sen/kg (Malaysia). Sen ÷ (USD/MYR) × 10 = USD/tấn.
        rate = fx_rates.get("USD/MYR")
        return (round(price * 10 / rate) if rate else None), "USD/MYR", rate
    if unit == "baht/kg":
        rate = fx_rates.get("USD/THB")
        return (round(price * 1000 / rate) if rate else None), "USD/THB", rate
    if unit == "CNY/tonne":
        rate = fx_rates.get("USD/CNY")
        return (cny_tonne_to_usd_tonne(price, rate) if rate else None), "USD/CNY", rate
    if unit == "JPY/kg":
        rate = fx_rates.get("USD/JPY")
        return (jpy_kg_to_usd_tonne(price, rate) if rate else None), "USD/JPY", rate
    # Đơn vị lạ → giả định đã ~USD/tấn.
    return round(price), None, None
