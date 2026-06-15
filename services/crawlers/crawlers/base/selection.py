"""Chọn kỳ hạn theo kinh nghiệm chuyên viên: lấy kỳ hạn có volume/trading_value LỚN NHẤT.

Tham số hóa (không hardcode số tháng) — theo spec lay-gia-cac-san.md.
"""

from __future__ import annotations

from enum import Enum

from .models import ContractQuote


class SelectionStrategy(str, Enum):
    MAX_VOLUME = "max_volume"                # SHFE (Volume lớn nhất)
    MAX_TRADING_VALUE = "max_trading_value"  # TOCOM (Trading Value lớn nhất)

    def _field(self) -> str:
        return "volume" if self is SelectionStrategy.MAX_VOLUME else "trading_value"

    def pick(self, quotes: list[ContractQuote]) -> ContractQuote | None:
        """Trả ContractQuote có tiêu chí lớn nhất (bỏ qua dòng thiếu dữ liệu)."""
        field = self._field()
        valid = [q for q in quotes if getattr(q, field) is not None]
        if not valid:
            return None
        return max(valid, key=lambda q: getattr(q, field))
