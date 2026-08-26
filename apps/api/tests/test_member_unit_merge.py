"""SÁP NHẬP đơn vị (member_unit.merged_into/merged_at) — cam kết cốt lõi của tính năng.

Điều phải khoá lại bằng test:
1. Số liệu TRƯỚC sáp nhập giữ nguyên tên đơn vị cũ (khác đổi tên — đổi tên ghi đè `company`).
2. Từ ngày hiệu lực, đơn vị cũ không nhận số liệu mới; ngày TRƯỚC đó vẫn sửa được.
3. Tài khoản đơn vị chuyển hẳn sang đơn vị mới.
4. Báo cáo mặc định GỘP số của đơn vị cũ vào đơn vị mới, `split_merged` thì tách ra —
   nhưng kỳ kết thúc TRƯỚC ngày sáp nhập thì hai đơn vị vẫn đứng riêng.
5. Bảng theo dõi nộp báo cáo không đòi đơn vị đã sáp nhập nộp cho những ngày sau đó.
6. Gỡ sáp nhập trả đơn vị về trạng thái hoạt động mà không phải khôi phục dữ liệu.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import (
    member_unit_merge as merge, member_unit_repo, unit_daily_repo, unit_report_purchase as pur,
    unit_report_status as sta,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

OLD, NEW, THIRD = "_zz_mg_cu", "_zz_mg_moi", "_zz_mg_ba"
UNITS = (OLD, NEW, THIRD)
ACCOUNT = "_zz_mg_user"

D_MERGE = (date.today() - timedelta(days=10)).isoformat()          # ngày hiệu lực sáp nhập
D_BEFORE = (date.today() - timedelta(days=20)).isoformat()         # số liệu trước sáp nhập
D_AFTER = (date.today() - timedelta(days=3)).isoformat()           # sau sáp nhập


def _cleanup() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = ANY(:u)"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM unit_customer WHERE company = ANY(:u)"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM unit_daily_report WHERE company = ANY(:u)"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = ANY(:u)"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM app_user WHERE username = :a"), {"a": ACCOUNT})
        db.execute(text("UPDATE member_unit SET merged_into = NULL, merged_at = NULL "
                        "WHERE merged_into = ANY(:u)"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM member_unit WHERE name = ANY(:u)"), {"u": list(UNITS)})


@pytest.fixture(autouse=True)
def _units():
    _cleanup()
    for n in UNITS:
        member_unit_repo.add_unit(n)
    yield
    _cleanup()


def _purchase(company: str, as_of: str, qty: float) -> None:
    unit_daily_repo.upsert("purchase", as_of, company, {"latex_wet": qty}, "test")


def _by_company(rep: dict) -> dict[str, float]:
    return {r["key"]: r["qty_latex"] for r in rep["rows"]}


# ── 1. Dữ liệu cũ giữ nguyên ───────────────────────────────────────────────────
def test_merge_keeps_old_rows_under_the_old_unit() -> None:
    """Sáp nhập KHÔNG đụng số liệu: bản ghi cũ vẫn mang tên đơn vị cũ (khác hẳn đổi tên)."""
    _purchase(OLD, D_BEFORE, 100)
    merge.merge(OLD, NEW, D_MERGE)

    with session_scope() as db:
        rows = db.execute(text("SELECT company FROM unit_daily_report WHERE as_of = CAST(:d AS date) "
                               "AND company = ANY(:u)"),
                          {"d": D_BEFORE, "u": list(UNITS)}).scalars().all()
    assert rows == [OLD], "số liệu trước sáp nhập phải giữ nguyên tên đơn vị cũ"

    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[OLD]["merged_into"] == NEW
    assert str(units[OLD]["merged_at"]) == D_MERGE
    assert units[OLD]["is_active"] is False           # biến khỏi mọi danh sách nhập liệu
    assert OLD not in member_unit_repo.active_names()


# ── 2. Gác ghi theo NGÀY SỐ LIỆU ───────────────────────────────────────────────
def test_writes_blocked_from_effective_date_but_old_days_still_editable() -> None:
    merge.merge(OLD, NEW, D_MERGE)

    with pytest.raises(ValueError) as exc:
        merge.assert_can_enter(OLD, D_AFTER)
    assert NEW in str(exc.value), "câu báo lỗi phải chỉ rõ nhập vào đơn vị nào"
    with pytest.raises(ValueError):                   # đúng ngày hiệu lực cũng đã thuộc đơn vị mới
        merge.assert_can_enter(OLD, D_MERGE)

    merge.assert_can_enter(OLD, D_BEFORE)             # ngày trước sáp nhập: vẫn sửa được
    merge.assert_can_enter(NEW, D_AFTER)


def test_merged_unit_cannot_take_a_dateless_write() -> None:
    """Thao tác không gắn ngày cụ thể coi như "từ nay" → chặn."""
    merge.merge(OLD, NEW, D_MERGE)
    with pytest.raises(ValueError):
        merge.assert_can_enter(OLD)


# ── 3. Tài khoản chuyển sang đơn vị mới ────────────────────────────────────────
def test_accounts_move_to_the_new_unit() -> None:
    from app.services import user_repo

    user_repo.create_user(ACCOUNT, "matkhau123", None, "member", member_units=[OLD, THIRD])
    result = merge.merge(OLD, NEW, D_MERGE)

    assert result["accounts_moved"] == [ACCOUNT]
    got = user_repo.get_user(ACCOUNT)
    assert got["member_units"] == [NEW, THIRD], "đơn vị cũ nhường chỗ cho đơn vị mới, giữ thứ tự"


def test_account_holding_both_units_does_not_get_a_duplicate() -> None:
    from app.services import user_repo

    user_repo.create_user(ACCOUNT, "matkhau123", None, "member", member_units=[OLD, NEW])
    merge.merge(OLD, NEW, D_MERGE)
    assert user_repo.get_user(ACCOUNT)["member_units"] == [NEW]


# ── 4. Báo cáo: gộp mặc định, tách khi được yêu cầu ────────────────────────────
def test_report_rolls_the_old_unit_into_the_new_one() -> None:
    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_AFTER, 30)
    merge.merge(OLD, NEW, D_MERGE)

    rep = pur.purchase_report(D_BEFORE, D_AFTER, companies=f"{OLD},{NEW}")
    rows = _by_company(rep)
    assert rows == {NEW: 130.0}, "mặc định gộp: một dòng mang tên đơn vị hiện hành"

    split = _by_company(pur.purchase_report(D_BEFORE, D_AFTER, companies=f"{OLD},{NEW}",
                                            split_merged=True))
    assert split == {OLD: 100.0, NEW: 30.0}


def test_picking_only_the_new_unit_still_pulls_the_old_unit_history() -> None:
    """Chọn đúng đơn vị hiện hành ở ô lọc là đã có cả giai đoạn trước sáp nhập."""
    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_AFTER, 30)
    merge.merge(OLD, NEW, D_MERGE)
    assert _by_company(pur.purchase_report(D_BEFORE, D_AFTER, companies=NEW)) == {NEW: 130.0}


def test_filtering_by_the_old_unit_while_rolled_up_still_returns_numbers() -> None:
    """Chọn nhầm đơn vị cũ trong lúc đang xem GỘP: quy về đơn vị hiện hành, KHÔNG trả bảng trống."""
    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_AFTER, 30)
    merge.merge(OLD, NEW, D_MERGE)
    assert _by_company(pur.purchase_report(D_BEFORE, D_AFTER, companies=OLD)) == {NEW: 130.0}


def test_period_ending_before_the_merge_keeps_the_units_apart() -> None:
    """Kỳ kết thúc TRƯỚC ngày sáp nhập: lúc ấy hai đơn vị còn độc lập nên vẫn hai dòng."""
    d0 = (date.fromisoformat(D_BEFORE) - timedelta(days=1)).isoformat()
    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_BEFORE, 30)
    merge.merge(OLD, NEW, D_MERGE)

    rep = pur.purchase_report(d0, D_BEFORE, companies=f"{OLD},{NEW}")
    assert _by_company(rep) == {OLD: 100.0, NEW: 30.0}


def test_year_plan_of_the_old_unit_counts_in_the_denominator() -> None:
    """Gộp sản lượng mà bỏ chỉ tiêu của đơn vị cũ là % kế hoạch tự đẹp lên."""
    year = int(D_AFTER[:4])
    unit_daily_repo.set_year_plan(year, OLD, 600, None, None, None, None, None, "test")
    unit_daily_repo.set_year_plan(year, NEW, 400, None, None, None, None, None, "test")
    _purchase(OLD, D_BEFORE, 100)
    merge.merge(OLD, NEW, D_MERGE)

    rep = pur.purchase_report(D_BEFORE, D_AFTER, companies=NEW)
    assert [r["plan_tonnes"] for r in rep["rows"]] == [1000.0]


def test_period_report_rolls_up_and_splits() -> None:
    """Báo cáo tổng hợp: gộp cho ra MỘT dòng đơn vị hiện hành, tách cho ra hai dòng."""
    from app.services import unit_period_report

    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_AFTER, 30)
    merge.merge(OLD, NEW, D_MERGE)

    rolled = {r["company"]: r["latex_wet"] for r in
              unit_period_report.period_report("purchase", D_BEFORE, D_AFTER, [NEW])["rows"]}
    assert rolled == {NEW: 130.0}

    split = {r["company"]: r["latex_wet"] for r in
             unit_period_report.period_report("purchase", D_BEFORE, D_AFTER, [OLD, NEW],
                                              split_merged=True)["rows"]}
    assert split == {OLD: 100.0, NEW: 30.0}


def test_stock_and_consumption_reports_run_with_a_merged_unit() -> None:
    """Chạy trơn hai bảng còn lại khi hệ thống có đơn vị đã sáp nhập (cả gộp lẫn tách)."""
    from app.services import unit_report_consumption as con, unit_report_stock as st

    merge.merge(OLD, NEW, D_MERGE)
    today = date.today().isoformat()
    for split in (False, True):
        assert "rows" in st.stock_report(today, 7, companies=NEW, group_by="day",
                                         split_merged=split)
        assert "rows" in st.stock_report(today, 0, group_by="company", split_merged=split)
        assert "rows" in con.consumption_report(D_BEFORE, today, companies=NEW,
                                                split_merged=split)


# ── 5. Theo dõi nộp báo cáo ────────────────────────────────────────────────────
def test_status_stops_asking_the_merged_unit_after_the_effective_date() -> None:
    year = int(D_AFTER[:4])
    unit_daily_repo.set_year_plan(year, OLD, 100, None, None, None, None, None, "test")
    _purchase(OLD, D_BEFORE, 10)
    merge.merge(OLD, NEW, D_MERGE)

    rep = sta.status_report("purchase", D_BEFORE, D_AFTER, companies=OLD)
    row = next(r for r in rep["rows"] if r["company"] == OLD)
    assert row["cells"][D_BEFORE] == "ok"
    assert row["cells"][D_MERGE] == "merged" and row["cells"][D_AFTER] == "merged"
    assert row["merged_into"] == NEW
    # Mẫu số chỉ đếm những ngày đơn vị còn phải nộp — không phải cả khoảng ngày.
    days_due = (date.fromisoformat(D_MERGE) - date.fromisoformat(D_BEFORE)).days
    assert rep["totals"]["expected"] == days_due


# ── 6. Ràng buộc + gỡ sáp nhập ─────────────────────────────────────────────────
def test_merge_rejects_invalid_targets() -> None:
    for src, dst in ((OLD, OLD), (OLD, "_zz_mg_khong_co")):
        with pytest.raises(ValueError):
            merge.merge(src, dst, D_MERGE)
    merge.merge(OLD, NEW, D_MERGE)
    with pytest.raises(ValueError):          # đơn vị đã sáp nhập rồi thì không sáp nhập tiếp
        merge.merge(OLD, THIRD, D_AFTER)
    with pytest.raises(ValueError):          # đơn vị nhận đã sáp nhập đi nơi khác
        merge.merge(THIRD, OLD, D_AFTER)


def test_merging_a_parent_into_its_own_child_keeps_the_tree_sane() -> None:
    """Công ty mẹ nhập vào chính công ty con của nó: không được để đơn vị tự làm mẹ của mình."""
    member_unit_repo.set_parent(NEW, OLD)      # NEW là con của OLD
    member_unit_repo.set_parent(THIRD, OLD)    # THIRD cũng là con của OLD
    merge.merge(OLD, NEW, D_MERGE)

    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[NEW]["parent_company"] is None, "đơn vị nhận không thể là mẹ của chính nó"
    assert units[THIRD]["parent_company"] == NEW
    # Cây còn đi được → danh sách tiêu thụ nội bộ dựng ra bình thường, không lặp vô tận.
    assert isinstance(member_unit_repo.internal_targets(), dict)


def test_merge_chain_resolves_to_the_last_unit() -> None:
    """A→B rồi B→C: số của A phải chảy tới C."""
    _purchase(OLD, D_BEFORE, 100)
    merge.merge(OLD, NEW, D_MERGE)
    merge.merge(NEW, THIRD, D_AFTER)
    assert merge.current_name(OLD) == THIRD
    assert set(merge.lineage(THIRD)) == {THIRD, NEW, OLD}
    assert _by_company(pur.purchase_report(D_BEFORE, date.today().isoformat(),
                                           companies=THIRD)) == {THIRD: 100.0}


def test_renaming_the_target_keeps_the_link() -> None:
    merge.merge(OLD, NEW, D_MERGE)
    member_unit_repo.rename_unit(NEW, THIRD + "_x")
    try:
        units = {u["name"]: u for u in member_unit_repo.list_units()}
        assert units[OLD]["merged_into"] == THIRD + "_x"
    finally:
        member_unit_repo.rename_unit(THIRD + "_x", NEW)


# ── 6b. Hợp đồng dở dang vẫn chạy hết ở đơn vị cũ ─────────────────────────────
def test_old_contracts_keep_running_but_no_new_ones() -> None:
    """Chốt 24/08/2026: chặn KÝ MỚI ở đơn vị đã sáp nhập, nhưng hợp đồng cũ vẫn giao tiếp được.

    Chuyển hợp đồng sang đơn vị mới sẽ kéo cả sản lượng ĐÃ GIAO trước đó nhảy đơn vị — nên hợp
    đồng ở lại, chỉ đóng đường ký mới.
    """
    from app.services import customer_repo, sales_contract_repo

    khach = customer_repo.save({"name": "KH sáp nhập"}, OLD, "test")["id"]
    parent = sales_contract_repo.save(
        {"code": "HD-TRUOC-SAP", "delivery_type": "multi", "contract_type": "spot",
         "sign_date": D_BEFORE, "customer_id": khach,
         "lines": [{"grade": "SVR 3L", "qty": 100, "price": 30}]}, OLD, "test")
    merge.merge(OLD, NEW, D_MERGE)

    # Đợt giao của hợp đồng cũ: vẫn ghi được.
    sales_contract_repo.save(
        {"code": "DOT-1", "parent_id": parent["id"], "start_date": D_AFTER, "delivered_at": D_AFTER,
         "channel": "domestic",
         "lines": [{"grade": "SVR 3L", "qty": 40, "price": 30}]}, OLD, "test")

    # Hợp đồng MỚI ở đơn vị đã sáp nhập: chặn, kèm câu chỉ sang đơn vị nhận.
    with pytest.raises(ValueError) as exc:
        sales_contract_repo.save(
            {"code": "HD-MOI", "delivery_type": "single", "contract_type": "spot",
             "sign_date": D_AFTER, "customer_id": khach,
             "lines": [{"grade": "SVR 3L", "qty": 10, "price": 30}]}, OLD, "test")
    assert NEW in str(exc.value)


def test_unmerge_restores_the_unit_without_touching_data() -> None:
    _purchase(OLD, D_BEFORE, 100)
    merge.merge(OLD, NEW, D_MERGE)
    merge.unmerge(OLD)

    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[OLD]["merged_into"] is None and units[OLD]["is_active"] is True
    merge.assert_can_enter(OLD, D_AFTER)              # nhập liệu mở lại
    assert _by_company(pur.purchase_report(D_BEFORE, D_AFTER, companies=OLD)) == {OLD: 100.0}


def test_deleting_the_target_unit_frees_the_merged_one() -> None:
    """Xoá đơn vị nhận: đơn vị cũ không được vừa bị ẩn vừa trỏ về một đơn vị không còn tồn tại."""
    merge.merge(OLD, NEW, D_MERGE)
    member_unit_repo.delete_unit(NEW)
    units = {u["name"]: u for u in member_unit_repo.list_units()}
    assert units[OLD]["merged_into"] is None and units[OLD]["is_active"] is True
