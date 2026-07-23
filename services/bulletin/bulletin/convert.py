"""Quy đổi đơn vị giá từ crawler → USD/tấn (đơn vị bản tin).

Crawlers trả về đơn vị gốc của sàn:
  - SHFE: CNY/tonne
  - TOCOM/OSE: JPY/kg
  - LGM: US cents/kg  (Latex: Sen/kg — quy đổi USD/T bằng tỷ giá USD/MYR: Sen ÷ USD/MYR × 10)
  - ANRPC: US$/kg
  - FX: per USD (ví dụ 1 USD = 25,800 VND)
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def r1(x: float) -> float:
    """Làm tròn 1 SỐ LẺ, nửa LÊN.

    Giữ 1 số lẻ vì nguồn yết tới đó: MRB cho US cents/kg 2 số lẻ (223,85) → 2238,5 USD/tấn.
    Trước đây trả số nguyên nên mất đúng 0,5 — chuyên viên đối chiếu với MRB thấy lệch.
    Dùng ROUND_HALF_UP vì `round()` của Python làm tròn về số CHẴN: round(2238.5) = 2238 và
    round(2288.5) = 2288, tức luôn thiệt xuống ở các giá kết thúc bằng ,5.
    """
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def r2(x: float) -> float:
    """Làm tròn 2 SỐ LẺ, nửa LÊN — tỷ giá USD/JPY lưu theo đúng file gốc Ban TTKD (163,12)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def r0(x: float) -> int:
    """Làm tròn về SỐ NGUYÊN, nửa LÊN — cho nơi bắt buộc số nguyên (vd bản tin)."""
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cny_tonne_to_usd_tonne(price_cny: float, usd_cny: float) -> float:
    """CNY/tấn → USD/tấn (SHFE)."""
    return r1(price_cny / usd_cny)


def jpy_kg_to_usd_tonne(price_jpy_per_kg: float, usd_jpy: float) -> float:
    """JPY/kg → USD/tấn (TOCOM/OSE).  1 tấn = 1000 kg."""
    return r1(price_jpy_per_kg * 1000 / usd_jpy)


def uscents_kg_to_usd_tonne(price_cents: float) -> float:
    """US cents/kg → USD/tấn (LGM).  100 cents = 1 USD, 1 tấn = 1000 kg."""
    return r1(price_cents * 1000 / 100)


def usd_kg_to_usd_tonne(price_usd_per_kg: float) -> float:
    """US$/kg → USD/tấn (ANRPC physical)."""
    return r1(price_usd_per_kg * 1000)


# Đơn vị gốc của sàn → cặp tỷ giá cần để quy đổi sang USD (None nếu đã là USD).
_FX_PAIR_FOR_UNIT = {"CNY/tonne": "USD/CNY", "JPY/kg": "USD/JPY"}


def to_usd_tonne_detail(
    price: float, unit: str, fx_rates: dict[str, float]
) -> tuple[float | None, str | None, float | None]:
    """Quy đổi 1 giá gốc → (usd_tonne, fx_pair, fx_rate). 1 NGUỒN quy đổi dùng chung.

    usd_tonne giữ 1 số lẻ (xem `r1`) — nơi nào cần số nguyên thì tự làm tròn bằng `r0`.
    fx_pair/fx_rate = None khi đơn vị đã ở hệ USD (US$/kg, US cents/kg).
    Thiếu tỷ giá → usd_tonne None nhưng vẫn trả fx_pair để UI báo rõ.
    """
    if unit in ("USD/tonne", "USD/T"):
        return r1(price), None, None
    if unit == "US$/kg":
        return usd_kg_to_usd_tonne(price), None, None
    if unit == "US cents/kg":
        return uscents_kg_to_usd_tonne(price), None, None
    if unit == "Sen/kg":
        # LGM Latex yết Sen/kg (Malaysia). Sen ÷ (USD/MYR) × 10 = USD/tấn.
        rate = fx_rates.get("USD/MYR")
        return (r1(price * 10 / rate) if rate else None), "USD/MYR", rate
    if unit == "baht/kg":
        rate = fx_rates.get("USD/THB")
        return (r1(price * 1000 / rate) if rate else None), "USD/THB", rate
    if unit == "CNY/tonne":
        rate = fx_rates.get("USD/CNY")
        return (cny_tonne_to_usd_tonne(price, rate) if rate else None), "USD/CNY", rate
    if unit == "JPY/kg":
        rate = fx_rates.get("USD/JPY")
        return (jpy_kg_to_usd_tonne(price, rate) if rate else None), "USD/JPY", rate
    # Đơn vị lạ → giả định đã ~USD/tấn.
    return r1(price), None, None
