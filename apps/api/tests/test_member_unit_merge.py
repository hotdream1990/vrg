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


def _stock(company: str, as_of: str, qty: float) -> None:
    """Một lần khai TỒN KHO (số thời điểm) — tồn nguyên liệu để bằng 1/10 cho dễ đối chiếu."""
    unit_daily_repo.upsert("consumption", as_of, company,
                           {"stock_warehoused": [{"grade": "SVR 10", "qty": qty}],
                            "stock_material": qty / 10}, "test")


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


def test_period_ending_before_the_merge_is_still_rolled_up() -> None:
    """Kỳ kết thúc TRƯỚC ngày sáp nhập vẫn GỘP về đơn vị nhận (luật 27/08/2026).

    Công ty mới xem báo cáo là thấy tổng lũy kế của cả hai từ đầu năm, không phải chỉ từ ngày
    sáp nhập; muốn xem riêng giai đoạn trước đó thì bật `split_merged`.
    """
    d0 = (date.fromisoformat(D_BEFORE) - timedelta(days=1)).isoformat()
    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_BEFORE, 30)
    merge.merge(OLD, NEW, D_MERGE)

    assert _by_company(pur.purchase_report(d0, D_BEFORE, companies=f"{OLD},{NEW}")) == {NEW: 130.0}
    apart = _by_company(pur.purchase_report(d0, D_BEFORE, companies=f"{OLD},{NEW}",
                                            split_merged=True))
    assert apart == {OLD: 100.0, NEW: 30.0}


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


def _stock_of(company: str, d_from: str, d_to: str, key: str = "stock_finished"):
    from app.services import unit_period_report

    row = next((r for r in unit_period_report.period_report("consumption", d_from, d_to,
                                                            [company])["rows"]
                if r["company"] == company), {})
    return row.get(key)


def test_rolled_up_stock_adds_both_units_while_the_warehouses_are_still_separate() -> None:
    """Hai kho còn khai riêng → tồn gộp là TỔNG, không phải một trong hai.

    Bẫy đã xảy ra thật (Chư păh 27/08/2026): tồn kho là số THỜI ĐIỂM nên chỉ lấy một ảnh chụp gần
    nhất — gom hai đơn vị vào một rổ rồi lấy "bản ghi mới nhất" thì tồn của bên kia bay mất, tổng
    tồn toàn hệ thống hụt đúng bằng lô hàng đó.
    """
    d_prev = (date.fromisoformat(D_MERGE) - timedelta(days=1)).isoformat()
    _stock(OLD, D_BEFORE, 800)                 # mỗi bên khai lần cuối TRƯỚC ngày sáp nhập…
    _stock(NEW, d_prev, 400)                   # …nên kho vẫn đang được khai riêng
    merge.merge(OLD, NEW, D_MERGE)

    assert _stock_of(NEW, D_BEFORE, D_AFTER) == 1200.0
    assert _stock_of(NEW, D_BEFORE, D_AFTER, "stock_material") == 120.0


def test_rolled_up_stock_stops_adding_once_the_new_unit_declares_the_joint_warehouse() -> None:
    """Đơn vị nhận đã khai tồn KỂ TỪ ngày sáp nhập → thôi cộng ảnh chụp cũ của đơn vị kia.

    Từ ngày hiệu lực, kho của đơn vị cũ do đơn vị nhận quản lý và khai chung. Cộng thêm ảnh chụp
    cuối của đơn vị cũ là tính trùng đúng lô hàng đó — số tồn phồng lên gấp rưỡi.
    """
    _stock(OLD, D_BEFORE, 800)
    _stock(NEW, D_AFTER, 1300)                 # khai sau ngày sáp nhập: đã gồm cả kho tiếp quản
    merge.merge(OLD, NEW, D_MERGE)

    assert _stock_of(NEW, D_BEFORE, D_AFTER) == 1300.0


def test_no_number_is_lost_in_a_period_ending_before_the_merge() -> None:
    """Kỳ kết thúc TRƯỚC ngày sáp nhập: số của đơn vị cũ nằm trong dòng của đơn vị nhận.

    Đã có lúc số rơi vào khoảng không — khung đơn vị bỏ đơn vị cũ ra trong khi luật gộp lại chưa
    áp dụng cho kỳ đó, nên 2.896 tấn tiêu thụ của Chư păh biến mất khỏi báo cáo (27/08/2026).
    """
    from app.services import unit_period_report

    _purchase(OLD, D_BEFORE, 100)
    _purchase(NEW, D_BEFORE, 30)
    merge.merge(OLD, NEW, D_MERGE)

    d_end = (date.fromisoformat(D_MERGE) - timedelta(days=1)).isoformat()
    rows = {r["company"]: r["latex_wet"]
            for r in unit_period_report.period_report("purchase", D_BEFORE, d_end)["rows"]
            if r["company"] in UNITS}
    assert rows == {NEW: 130.0, THIRD: None}, "đơn vị cũ không đứng riêng, số phải nằm ở đơn vị nhận"


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


def test_receiving_unit_account_sees_the_old_units_contracts() -> None:
    """Tài khoản đơn vị NHẬN phải thấy hợp đồng của đơn vị đã sáp nhập vào mình.

    Chốt với chủ dự án 27/08/2026: "hợp đồng khi đã gộp thì xem chung, họ tiếp tục làm nhưng tính
    số liệu tổng; tạo mới thì chỉ chọn được đơn vị nhận". Không mở phạm vi thì hợp đồng dở dang
    của đơn vị cũ không ai thấy để thêm đợt giao — trên prod đã có 3 hợp đồng rơi vào cảnh đó.
    """
    from app.core.security import cap_or_member_scope
    from app.services import user_repo

    merge.merge(OLD, NEW, D_MERGE)
    user_repo.create_user(ACCOUNT, "matkhau123", None, "member", member_units=[NEW])
    _, companies = cap_or_member_scope("sales_contract")(ACCOUNT)
    assert set(companies) == {NEW, OLD}, "phạm vi phải gồm cả đơn vị đã sáp nhập vào mình"


def test_contract_screens_sum_the_old_unit_into_the_new_one() -> None:
    """Màn Hợp đồng: chọn đơn vị nhận thì thấy CHUNG và cộng TỔNG cả phần đơn vị đã sáp nhập.

    Chốt với chủ dự án 27/08/2026: "hợp đồng khi đã gộp thì xem chung, họ tiếp tục làm nhưng tính
    số liệu tổng". Lọc đúng một tên đơn vị mà không kéo theo dòng đời thì phần hàng của đơn vị cũ
    rơi ra ngoài bảng.
    """
    from app.routers import sales_contracts as sc
    from app.services import customer_repo, sales_contract_repo

    for unit, qty in ((OLD, 100.0), (NEW, 30.0)):
        khach = customer_repo.save({"name": f"KH {unit}"}, unit, "test")["id"]
        sales_contract_repo.save(
            {"code": f"HD-{unit}", "delivery_type": "single", "contract_type": "spot",
             "sign_date": D_BEFORE, "start_date": D_BEFORE, "customer_id": khach,
             "delivered_at": D_BEFORE, "channel": "domestic",
             "lines": [{"grade": "SVR 3L", "qty": qty, "price": 30}]}, unit, "test")
    merge.merge(OLD, NEW, D_MERGE)

    rep = sc._consumption([NEW], D_BEFORE, D_AFTER, NEW, None, None)
    assert set(rep["by_company"]) == {NEW}, "đơn vị cũ không đứng thành dòng riêng"
    assert rep["by_company"][NEW]["qty"] == 130.0, "phải cộng cả phần của đơn vị đã sáp nhập"


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


def test_daily_stock_rows_stop_double_counting_after_the_merge_date() -> None:
    """Bảng tồn kho xem theo NGÀY: ngày cả hai cùng khai sau ngày hiệu lực chỉ tính đơn vị nhận.

    Trước 06/09/2026 luật sáp nhập chỉ áp cho dòng Tổng cộng, còn từng dòng ngày vẫn cộng cả hai —
    nên chính bảng đó tự cãi nhau, và lệch luôn với biểu đồ tồn kho theo ngày ở Bản tin biến động.
    Ngày TRƯỚC ngày hiệu lực phải giữ nguyên cả hai: lúc đó hai kho còn khai riêng thật.
    """
    from app.services import unit_report_stock as st

    d_before = (date.fromisoformat(D_MERGE) - timedelta(days=1)).isoformat()
    for day, old_qty, new_qty in ((d_before, 800.0, 400.0), (D_AFTER, 800.0, 1300.0)):
        _stock(OLD, day, old_qty)
        _stock(NEW, day, new_qty)
    merge.merge(OLD, NEW, D_MERGE)

    days = st.stock_report(D_AFTER, days_back=30, companies=f"{OLD},{NEW}", group_by="day")
    by_day = {r["key"]: r["warehoused"] for r in days["rows"]}
    assert by_day[d_before] == 1200.0, "ngày trước sáp nhập: hai kho còn riêng, phải cộng cả hai"
    assert by_day[D_AFTER] == 1300.0, "sau ngày hiệu lực: kho cũ đã nằm trong số của đơn vị nhận"


def test_receiving_unit_account_sees_the_old_units_daily_rows() -> None:
    """Màn của ĐƠN VỊ: tài khoản đơn vị nhận phải thấy cả số liệu ngày của đơn vị đã sáp nhập.

    Phản ánh thật 11/09/2026 (Chư Sê nhận Mang Yang): sáp nhập giữ nguyên tên đơn vị cũ trên dữ
    liệu cũ, còn tài khoản thì chuyển hẳn sang đơn vị nhận — nên phần số liệu đầu năm của đơn vị cũ
    biến mất khỏi màn của họ và dòng "Lũy kế (khoảng đang xem)" thiếu hẳn một mảng, dù báo cáo của
    Ban đã gộp đủ. Đơn vị đối chiếu với sổ của mình là lệch, tưởng mất số liệu.
    """
    from app.routers import member_self

    _purchase(OLD, D_BEFORE, 7.0)
    _purchase(NEW, D_BEFORE, 3.0)
    merge.merge(OLD, NEW, D_MERGE)

    got = member_self.my_daily_timeline(
        kind="purchase", days=90, date_from=None, date_to=None, page=1, page_size=500,
        member={"username": ACCOUNT, "member_units": [NEW]})
    assert {e["company"] for e in got["entries"]} == {NEW, OLD}
    assert sum(e["fields"]["latex_wet"] for e in got["entries"]) == 10.0, "lũy kế phải gồm cả hai"
    assert got["view_only_units"] == [OLD], "phần của đơn vị đã sáp nhập chỉ được XEM"
    assert OLD in got["units"], "vẫn nằm trong danh sách đơn vị của màn (để mở phiếu xem lại)"


def test_receiving_unit_account_still_cannot_write_for_the_merged_unit() -> None:
    """Mở phạm vi ĐỌC không được kéo theo quyền GHI: đơn vị đã sáp nhập vẫn chỉ để tra cứu."""
    from fastapi import HTTPException

    from app.routers import member_self
    from app.schemas.unit_daily import UnitDailyEdit

    merge.merge(OLD, NEW, D_MERGE)
    body = UnitDailyEdit(kind="purchase", company=OLD, as_of=D_BEFORE, fields={"latex_wet": 1.0})
    with pytest.raises(HTTPException) as err:
        member_self.upsert_my_daily(body, member={"username": ACCOUNT, "member_units": [NEW]})
    assert err.value.status_code == 403


def test_member_entry_forms_keep_only_the_units_the_account_can_write() -> None:
    """Các form NHẬP (kế hoạch năm · phiếu nhu cầu) không được mời chọn đơn vị đã sáp nhập."""
    from app.routers import member_self

    merge.merge(OLD, NEW, D_MERGE)
    member = {"username": ACCOUNT, "member_units": [NEW]}
    assert member_self.my_year_plan(year=date.today().year, member=member)["units"] == [NEW]
    # Màn nhu cầu mở phạm vi ĐỌC sang đơn vị cũ, nhưng đánh dấu chỉ xem → form chỉ còn đơn vị mới.
    demand = member_self.my_market_demand_items(date_from=None, date_to=None, grade=None, q=None,
                                                member=member)
    assert demand["view_only_units"] == [OLD]
    assert [u for u in demand["units"] if u not in demand["view_only_units"]] == [NEW]
