"""Quy đổi đơn vị giá từ crawler → USD/tấn (đơn vị bản tin).

Crawlers trả về đơn vị gốc của sàn:
  - SHFE: CNY/tonne
  - TOCOM/OSE: JPY/kg
  - LGM: US cents/kg  (Latex: Sen/kg — đã quy đổi sang US cents/kg trong crawler)
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
