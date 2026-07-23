"""Bảng giá thành phần (/api/prices/board) — khoá lỗi 500 chuyên viên báo ngày 23/07/2026.

Giá USD/tấn giữ 1 SỐ LẺ (MRB yết cents/kg 2 số lẻ: 223,85 → 2238,5 USD/tấn — xem
`test_price_convert`). Schema `ExchangeComponent.usd_tonne` từng khai `int` nên pydantic ném
ResponseValidationError → endpoint trả 500. Hệ quả dây chuyền: bảng "So sánh Giá sàn Tập đoàn vs
Thị trường" và nhóm cùng tên trong nhận định AI (Bản tin biến động) đều báo "Chưa đủ dữ liệu".

Không cần DB: thay `price_repo.latest` bằng dữ liệu mẫu.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.price import PriceBoard
from app.services import price_board, price_repo


def _row(source: str, grade: str, price: float, unit: str,
         as_of: str = "2026-07-22") -> dict[str, Any]:
    return {
        "source": source, "grade": grade, "price": price, "currency": "USD",
        "unit": unit, "price_type": "settlement", "as_of": as_of,
        "contract": None, "ingested_at": "2026-07-22 10:00:00+00:00",
    }


_FX = _row("fx", "USD/JPY", 162.5055, "per USD")
_LATEST = [
    _row("lgm", "SMR20", 223.85, "US cents/kg"),      # → 2238,5 USD/T (ca lỗi được báo)
    _row("tocom", "RSS3", 407.4, "JPY/kg"),           # cần USD/JPY
    _FX,
]


def _mount(monkeypatch: pytest.MonkeyPatch, latest: list, fx: list) -> PriceBoard:
    monkeypatch.setattr(price_repo, "latest", lambda: list(latest))
    monkeypatch.setattr(price_repo, "prices_since", lambda *a, **k: list(fx))
    return PriceBoard(**price_board.build_board())   # y như response_model của endpoint


@pytest.fixture
def _board(monkeypatch: pytest.MonkeyPatch) -> PriceBoard:
    return _mount(monkeypatch, _LATEST, [_FX])


def test_board_khong_vo_khi_gia_usd_co_so_le(_board: PriceBoard) -> None:
    smr20 = next(e for e in _board.exchanges if e.grade == "SMR20")
    assert smr20.usd_tonne == 2238.5                 # KHÔNG được làm tròn/ném lỗi
    assert smr20.exchange == "MRE"


def test_board_van_kem_ty_gia_va_gia_quy_doi_qua_fx(_board: PriceBoard) -> None:
    rss3 = next(e for e in _board.exchanges if e.grade == "RSS3")
    assert rss3.fx_pair == "USD/JPY" and rss3.fx_rate == 162.5055
    assert rss3.usd_tonne == pytest.approx(407.4 * 1000 / 162.5055, abs=0.05)
    assert [f.pair for f in _board.fx] == ["USD/JPY"]


def test_board_khong_lay_ty_gia_ngay_khac_de_quy_doi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giá phiên 22/07 mà chỉ có tỷ giá 21/07 → để TRỐNG, không quy đổi bằng tỷ giá ngày khác.

    Sàn nghỉ lễ lệch nhau nên "giá mới nhất" và "tỷ giá mới nhất" hay rơi vào 2 ngày; ghép bừa
    2 ngày là vi phạm nguyên tắc không đắp dữ liệu ngày khác của dự án.
    """
    board = _mount(
        monkeypatch,
        [_row("tocom", "RSS3", 407.4, "JPY/kg")],
        [_row("fx", "USD/JPY", 162.5055, "per USD", as_of="2026-07-21")],
    )
    rss3 = next(e for e in board.exchanges if e.grade == "RSS3")
    assert rss3.usd_tonne is None and rss3.fx_rate is None
    assert rss3.native_price == 407.4          # giá gốc vẫn hiện đủ
