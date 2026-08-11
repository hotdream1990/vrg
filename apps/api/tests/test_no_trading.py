"""Quy ước 'giá 0 = No Trading' — phiên sàn nghỉ / không ra settlement.

Số 0 vào kho giá từ file chính thức của sàn (SGX SETTLE=0, OSE không kỳ hạn nào giao dịch)
hoặc do chuyên viên tự đưa về 0 ở Quản lý số liệu. Báo cáo phải ghi 'No Trading', KHÔNG in
số 0 (dễ đọc thành giá 0 USD) và KHÔNG tính +/- % trên đó.
"""

from __future__ import annotations

from datetime import date

from app.services.bulletin_service import _build_market_text
from app.schemas.bulletin import PhysicalPriceItem, WorldPriceItem
from bulletin.convert import is_no_trading, to_usd_tonne_detail
from bulletin.html_template import _fmt, _world_table
from bulletin.models import BulletinData, WorldPriceRow


def test_is_no_trading() -> None:
    assert is_no_trading(0) and is_no_trading(0.0)
    assert not is_no_trading(None) and not is_no_trading(273.9)


def test_quy_doi_gia_0_khong_can_ty_gia() -> None:
    """0 quy đổi kiểu gì cũng là 0 → không để thiếu tỷ giá biến No Trading thành 'chưa có số'."""
    assert to_usd_tonne_detail(0, "JPY/kg", {}) == (0.0, None, None)
    assert to_usd_tonne_detail(0, "US cents/kg", {}) == (0.0, None, None)


def test_o_gia_in_no_trading() -> None:
    assert _fmt(0) == "No Trading"
    assert _fmt(None) == "N/A"
    assert _fmt(2656) == "2,656"


def test_bang_muc_i_in_no_trading() -> None:
    data = BulletinData(
        report_date=date(2026, 8, 10), prev_date=date(2026, 8, 7),
        world_prices=[WorldPriceRow(exchange="SGX", grade="RSS3", unit="USD/T",
                                    price_prev=2739, price_curr=0)],
    )
    html = _world_table(data)
    assert "No Trading" in html and ">0<" not in html


def test_muc_iv_noi_thang_la_khong_giao_dich() -> None:
    """Mục IV không được viết 'giao dịch ở mức 0 usd/tấn'."""
    world = [
        WorldPriceItem(exchange="OSE", grade="RSS3", price_prev=2666, price_curr=0),
        WorldPriceItem(exchange="SGX", grade="RSS3", price_prev=2739, price_curr=0),
        WorldPriceItem(exchange="SGX", grade="TSR20", price_prev=2192, price_curr=2200,
                       change_abs=8, change_pct=0.4),
    ]
    phys = [PhysicalPriceItem(grade="RSS3", price_prev=2824, price_curr=0)]
    ex_lines, physical = _build_market_text(world, phys)
    ose, sgx = ex_lines[0], ex_lines[2]
    assert "không giao dịch (No Trading)" in ose and "0 usd/tấn" not in ose
    assert "RSS3 không giao dịch (No Trading)" in sgx      # sàn nhiều mặt hàng → có tiền tố
    assert "TSR20 giao dịch ở mức 2.200 usd/tấn" in sgx    # mặt hàng còn lại vẫn báo giá
    assert physical == "RSS3 không giao dịch (No Trading);"
