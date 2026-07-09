"""Test gom 'Giá mủ nguyên liệu' theo khu vực cho bản tin (pure `_regions_from_purchase`)."""

from __future__ import annotations

from app.services import bulletin_service as bs


def _regions(purchase, unit_region, order):
    return [(r.region, r.price_text) for r in bs._regions_from_purchase(purchase, unit_region, order)]


def test_range_when_multiple_units_in_region() -> None:
    purchase = {"Dầu Tiếng": 545, "Phước Hòa": 538, "Bình Long": 554}
    unit_region = {"Dầu Tiếng": "Bình Dương", "Phước Hòa": "Bình Dương", "Bình Long": "Bình Thuận"}
    order = ["Bình Dương", "Bình Thuận", "Tây Ninh"]
    # Bình Dương có 2 giá (538,545) → khoảng "538-545"; Bình Thuận 1 giá → "554"; Tây Ninh không có → bỏ.
    assert _regions(purchase, unit_region, order) == [("Bình Dương", "538-545"), ("Bình Thuận", "554")]


def test_unassigned_units_are_skipped() -> None:
    purchase = {"Bà Rịa": 550, "Dầu Tiếng": 545}
    unit_region = {"Dầu Tiếng": "Bình Dương"}  # Bà Rịa chưa gán khu vực
    # Bà Rịa (chưa gán) bị bỏ; chỉ còn Bình Dương.
    assert _regions(purchase, unit_region, ["Bình Dương"]) == [("Bình Dương", "545")]


def test_empty_region_not_in_report() -> None:
    # Khu vực trong order nhưng không có đơn vị nào có giá → không xuất hiện.
    assert _regions({}, {}, ["Bình Dương", "Tây Ninh"]) == []


def test_order_follows_region_order_not_price() -> None:
    purchase = {"A": 500, "B": 600}
    unit_region = {"A": "Tây Ninh", "B": "Bình Dương"}
    # Theo region_order (Bình Dương trước Tây Ninh), không theo giá.
    assert _regions(purchase, unit_region, ["Bình Dương", "Tây Ninh"]) == [("Bình Dương", "600"), ("Tây Ninh", "500")]
