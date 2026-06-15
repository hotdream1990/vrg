"""Test offline cho SelectionStrategy (chọn kỳ hạn theo max volume/trading_value)."""

from crawlers.base.models import ContractQuote
from crawlers.base.selection import SelectionStrategy


def test_pick_max_volume() -> None:
    quotes = [
        ContractQuote(settle=100, volume=5),
        ContractQuote(settle=110, volume=50),   # volume lớn nhất
        ContractQuote(settle=120, volume=20),
    ]
    best = SelectionStrategy.MAX_VOLUME.pick(quotes)
    assert best is not None
    assert best.settle == 110 and best.volume == 50


def test_pick_max_trading_value() -> None:
    quotes = [
        ContractQuote(settle=100, trading_value=9),
        ContractQuote(settle=130, trading_value=99),  # trading value lớn nhất
    ]
    best = SelectionStrategy.MAX_TRADING_VALUE.pick(quotes)
    assert best is not None and best.settle == 130


def test_pick_skips_missing_field() -> None:
    assert SelectionStrategy.MAX_VOLUME.pick([]) is None
    # thiếu volume → bỏ qua, không chọn
    assert SelectionStrategy.MAX_VOLUME.pick([ContractQuote(settle=1)]) is None
