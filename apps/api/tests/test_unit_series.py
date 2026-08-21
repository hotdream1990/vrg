"""Test chuỗi THEO NGÀY dựng từ số liệu đơn vị thành viên (Command Center · Bản tin biến động).

Ràng buộc phải khoá lại:
1. Thu mua: sản lượng và đơn giá cùng gốc "đơn vị tự khai"; đơn vị có giá mà chưa khai sản lượng
   vẫn nằm trong dải giá của ngày (và ngược lại).
2. Đơn vị nước ngoài khai giá nội tệ → quy ra VND bằng tỷ giá của chính bản ghi ngày đó.
3. Tồn kho: mỗi ngày là ẢNH CHỤP độc lập — số cũ dùng lại tối đa `MAX_AGE_DAYS` ngày rồi rơi ra,
   KHÔNG cộng dồn giữa các ngày.
4. Phần "đã ký hợp đồng" bị CẮT TRẦN theo tồn kho của TỪNG đơn vị (giống `inventory_auto`).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_HQ, PURCHASE_SOURCE_UNIT
from app.services import price_repo, unit_daily_repo, unit_series
from app.services import unit_series_purchase as pur
from app.services import unit_series_consumption as con
from app.services import unit_series_stock as st

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

UNIT = "_zz_series_unit"
LAO = "_zz_series_lao"          # đơn vị nước ngoài: khai giá nội tệ + tỷ giá
DAY = (date.today() - timedelta(days=1)).isoformat()
PREV = (date.today() - timedelta(days=2)).isoformat()


def _price(company: str, price: float, price_type: str = "purchase",
           source: str = PURCHASE_SOURCE_UNIT, as_of: str = DAY) -> None:
    price_repo.upsert_record({"as_of": as_of, "source": source, "grade": company, "contract": "",
                              "price_type": price_type, "price": price, "currency": "VND",
                              "unit": "đồng/độ"})


@pytest.fixture()
def clean():
    _wipe()
    yield
    _wipe()


def _wipe() -> None:
    with session_scope() as db:
        for g in (UNIT, LAO):
            db.execute(text("DELETE FROM fact_price WHERE grade = :g"), {"g": g})
            db.execute(text("DELETE FROM unit_daily_report WHERE company = :g"), {"g": g})


def _row(series: dict, as_of: str) -> dict:
    return next(r for r in series["rows"] if r["as_of"] == as_of)


# ── Thu mua ────────────────────────────────────────────────────────────────────
def test_purchase_series_joins_price_and_volume(clean) -> None:
    """Sản lượng cộng từ biểu Thu mua, dải giá lấy lớp đơn vị tự khai — hai nguồn ghép theo ngày."""
    _price(UNIT, 520)
    _price(UNIT, 480, price_type="purchase_cup")
    unit_daily_repo.upsert("purchase", DAY, UNIT, {"latex_wet": 12.5, "coagulum": 3.0}, "test")

    row = _row(pur.purchase_series(PREV, DAY), DAY)
    assert row["latex"]["qty"] >= 12.5 and row["latex"]["min"] <= 520 <= row["latex"]["max"]
    assert row["cup"]["qty"] >= 3.0 and row["cup"]["min"] <= 480 <= row["cup"]["max"]


def test_price_without_volume_still_counted(clean) -> None:
    """Đơn vị công bố giá nhưng chưa khai sản lượng: vẫn nằm trong dải giá của ngày."""
    _price(UNIT, 999999)                      # giá "chỉ dấu" cao để nhận ra trong dải
    row = _row(pur.purchase_series(DAY, DAY), DAY)
    assert row["latex"]["max"] == 999999 and row["latex"]["units"] >= 1


def test_hq_price_layer_is_ignored(clean) -> None:
    """Chuỗi này chỉ đọc lớp ĐƠN VỊ tự khai — số chuyên viên chốt không được trộn vào.

    Không dùng `_row`: giá lớp chuyên viên KHÔNG tạo ra số liệu nào cho ngày đó, mà ngày rỗng thì
    đã bị loại khỏi chuỗi — trên DB sạch `rows` rỗng hẳn.
    """
    _price(UNIT, 888888, source=PURCHASE_SOURCE_HQ)
    rows = pur.purchase_series(DAY, DAY)["rows"]
    assert all((r["latex"]["max"] or 0) != 888888 for r in rows)


def test_foreign_unit_local_price_converted(clean) -> None:
    """Giá nội tệ (LAK/độ) × tỷ giá của bản ghi = giá VND — không lấy nguyên số nội tệ."""
    unit_daily_repo.upsert("purchase", DAY, LAO,
                           {"latex_wet": 5.0, "price_latex_local": 100.0, "fx_purchase": 1.5}, "test")
    row = _row(pur.purchase_series(DAY, DAY), DAY)
    assert row["latex"]["max"] >= 150.0       # 100 × 1,5 = 150 đồng/độ


# ── Tồn kho ────────────────────────────────────────────────────────────────────
def _stock(as_of: str, company: str = UNIT, warehoused: float = 100.0) -> None:
    unit_daily_repo.upsert("consumption", as_of, company, {
        "stock_warehoused": [{"grade": "SVR 10", "qty": warehoused}],
        "stock_not_warehoused": [{"grade": "SVR 10", "qty": 40.0}],
    }, "test")


def _totals(date_from: str, date_to: str) -> dict[str, float]:
    """{ngày: tổng tồn} — đo bằng CHÊNH LỆCH trước/sau khi seed vì DB test dùng chung có số nền."""
    return {r["as_of"]: (r["total"] or 0.0) for r in st.stock_series(date_from, date_to, "grade")["rows"]}


def test_stock_snapshot_carries_forward_then_expires(clean) -> None:
    """Số của một ngày được dùng lại tối đa MAX_AGE_DAYS ngày rồi rơi khỏi ảnh chụp."""
    base = date.fromisoformat(DAY) - timedelta(days=st.MAX_AGE_DAYS + 2)
    within = (base + timedelta(days=st.MAX_AGE_DAYS)).isoformat()
    after = (base + timedelta(days=st.MAX_AGE_DAYS + 1)).isoformat()
    before = _totals(base.isoformat(), DAY)

    _stock(base.isoformat())
    now = _totals(base.isoformat(), DAY)
    assert round(now[within] - before[within], 3) == 100.0    # còn trong hạn → vẫn tính
    assert round(now[after] - before[after], 3) == 0.0        # quá hạn → rơi khỏi ảnh chụp


def test_stock_never_accumulates_across_days(clean) -> None:
    """Hai ngày liên tiếp cùng khai 100 tấn thì ngày sau vẫn là 100 (số thời điểm, không cộng dồn)."""
    before = _totals(PREV, DAY)
    _stock(PREV, warehoused=100.0)
    _stock(DAY, warehoused=100.0)
    now = _totals(PREV, DAY)
    assert round(now[PREV] - before[PREV], 3) == 100.0
    assert round(now[DAY] - before[DAY], 3) == 100.0          # KHÔNG phải 200


def test_structure_splits_signed_and_free(clean) -> None:
    """Cơ cấu: đã ký + tự do = tổng tồn; chưa có hợp đồng thì toàn bộ là tồn tự do."""
    _stock(DAY)
    row = _row(st.stock_series(DAY, DAY, "structure"), DAY)
    assert round(row["values"]["signed"] + row["values"]["free"], 3) == row["total"]


def test_grade_and_region_cover_the_same_total(clean) -> None:
    """Ba cách nhóm cùng một ngày phải cộng ra cùng một tổng tồn kho."""
    _stock(DAY)
    totals = {g: sum(_row(st.stock_series(DAY, DAY, g), DAY)["values"].values())
              for g in st.GROUPS}
    assert round(totals["grade"], 3) == round(totals["region"], 3) == round(totals["structure"], 3)


# ── Cửa sổ ngày ────────────────────────────────────────────────────────────────
def test_window_clamps_to_floor_and_max_span() -> None:
    """Không cho lùi trước mốc bắt đầu chuỗi, cũng không cho kéo quá trần ngày."""
    a, _ = unit_series.window("2020-01-01", DAY, start_floor=st.STOCK_START)
    assert a == st.STOCK_START
    a2, b2 = unit_series.window("2020-01-01", DAY)
    assert (date.fromisoformat(b2) - date.fromisoformat(a2)).days == unit_series.MAX_WINDOW_DAYS - 1


# ── Rổ giá & bỏ số rỗng/bằng 0 ─────────────────────────────────────────────────
def test_zero_volume_is_not_a_volume(clean) -> None:
    """Sản lượng 0 (có tổ chức mua nhưng không mua được) không được vẽ thành cột 0."""
    far = (date.today() - timedelta(days=395)).isoformat()   # ngày xa hẳn dữ liệu thật trong DB
    _price(UNIT, 500, as_of=far)
    unit_daily_repo.upsert("purchase", far, UNIT, {"latex_wet": 0}, "test")
    row = _row(pur.purchase_series(far, far), far)
    assert (row["latex"]["qty"], row["latex"]["qty_units"]) == (None, 0)
    assert row["latex"]["units"] == 1        # ngày vẫn còn vì có đơn giá


def test_days_without_any_number_are_dropped(clean) -> None:
    """Ngày không có giá lẫn sản lượng của cả hai loại mủ thì không nằm trong chuỗi."""
    far = (date.today() - timedelta(days=400)).isoformat()   # xa hẳn dữ liệu thật trong DB
    assert pur.purchase_series(far, far)["rows"] == []


def test_steady_basket_drops_occasional_units(clean) -> None:
    """Đơn vị chỉ khai 1 ngày không được kéo đáy dải giá của riêng ngày đó."""
    days = [(date.fromisoformat(DAY) - timedelta(days=i)).isoformat() for i in range(6)]
    for d in days:                                  # đơn vị khai ĐỀU, giá cao
        _price(UNIT, 500, as_of=d)
    _price(LAO, 100, as_of=DAY)                     # đơn vị khai LÁC ĐÁC, giá thấp

    steady = _row(pur.purchase_series(days[-1], DAY), DAY)["latex"]
    every = _row(pur.purchase_series(days[-1], DAY, "all"), DAY)["latex"]
    assert every["min"] <= 100 < steady["min"]      # rổ "all" thấy đáy 100, rổ mặc định thì không


# ── Các cách chia mới (thu mua theo khu vực/đơn vị · tồn tự do · tiêu thụ) ─────
def test_purchase_volume_groups_by_region_and_company(clean) -> None:
    """Sản lượng chia theo khu vực/đơn vị: đơn vị chưa gán khu vực vẫn phải hiện ra, không rơi mất."""
    far = (date.today() - timedelta(days=396)).isoformat()
    unit_daily_repo.upsert("purchase", far, UNIT, {"latex_wet": 7.5}, "test")

    by_company = pur.purchase_volume_series(far, far, "latex", "company")
    assert _row(by_company, far)["values"][UNIT] == 7.5
    by_region = pur.purchase_volume_series(far, far, "latex", "region")
    assert _row(by_region, far)["values"][pur.NO_REGION] == 7.5


def test_purchase_volume_skips_zero(clean) -> None:
    """Ngày đơn vị khai 0 tấn không tạo ra cột 0 (cùng quy tắc với chuỗi giá)."""
    far = (date.today() - timedelta(days=397)).isoformat()
    unit_daily_repo.upsert("purchase", far, UNIT, {"latex_wet": 0}, "test")
    assert pur.purchase_volume_series(far, far, "latex", "company")["rows"] == []


def test_free_grade_is_stock_minus_signed_capped(clean) -> None:
    """Tồn tự do theo chủng loại = tồn − đã ký, cắt trần từng chủng loại (không bao giờ âm)."""
    _stock(DAY)                      # 100 tấn SVR 10 đã nhập kho, chưa có hợp đồng nào
    row = _row(st.stock_series(DAY, DAY, "free_grade"), DAY)
    grade = row["values"].get("SVR 10") or row["values"].get(unit_series.OTHER_KEY)
    assert grade is not None and all(v >= 0 for v in row["values"].values())
    # Tổng vẫn là TỒN KHO, không phải tổng phần tự do — tooltip/dòng tổng dùng chung con số này.
    assert row["total"] >= sum(row["values"].values())


def test_consumption_series_groups_and_revenue(clean) -> None:
    """Chuỗi tiêu thụ: mọi cách chia cho cùng một tổng sản lượng của ngày."""
    day_from = (date.today() - timedelta(days=30)).isoformat()
    totals = {}
    for g in con.GROUPS:
        rep = con.consumption_series(day_from, DAY, g)
        totals[g] = round(sum(r["total"] for r in rep["rows"]), 3)
        assert all(r["revenue_missing_lines"] >= 0 for r in rep["rows"])
    assert len(set(totals.values())) == 1, totals
