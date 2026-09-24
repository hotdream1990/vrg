"""Test Trợ lý AI: công cụ trả số liệu thật + phân quyền cap `assistant` + gói kỹ năng.
Không gọi LLM thật (cần key/mạng) — chỉ kiểm tool layer, gating gói và hàng rào quyền."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.core.permissions import DATA_CAPS, LEVEL_EDIT
from app.services import assistant_service, assistant_tools, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

#: Tool không cần tham số — chạy được ngay trên dữ liệu thật.
NO_ARG_TOOLS = (
    "get_exchange_prices", "get_physical_prices", "get_fx_rates",
    "get_floor_prices", "get_floor_history", "simulate_floor_scenarios",
    "get_inventory_trend", "get_market_quote", "get_data_freshness",
    "get_undelivered_volume", "get_contract_deliveries", "get_contract_summary",
    "get_top_customers", "get_master_contracts",
)


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(u: str, p: str) -> dict[str, str]:
    t = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def _admin_caps() -> dict[str, str]:
    """Quyền của admin — mọi mục ở mức Sửa."""
    return {k: LEVEL_EDIT for k in DATA_CAPS}


def test_tools_return_structured_data() -> None:
    caps = _admin_caps()
    for name in NO_ARG_TOOLS:
        assert name in assistant_tools.TOOLS, f"thiếu tool {name}"
        res = assistant_tools.run_tool(name, {}, caps)
        assert isinstance(res.get("summary"), dict), name
        art = res.get("artifact")
        if art:
            assert art["type"] in ("table", "line") and "title" in art, name
    # schema hợp lệ + mỗi tool thuộc đúng 1 gói.
    schemas = assistant_tools.openai_tools(caps)
    assert schemas and all(s["type"] == "function" and s["function"]["name"] for s in schemas)
    assert all(t["pack"] in assistant_tools.PACKS for t in assistant_tools.TOOLS.values())
    # tên tool lạ → báo lỗi gọn, không ném.
    assert "error" in assistant_tools.run_tool("khong_ton_tai", {}, caps)["summary"]


def test_pack_gating_by_cap_and_selection() -> None:
    """Gói `unit` cần cap `unit_daily`; gói nền luôn bật dù người dùng không chọn."""
    no_cap: dict[str, str] = {}
    with_cap = {"unit_daily": LEVEL_EDIT}
    assert "unit" not in assistant_tools.allowed_packs(no_cap)
    assert "unit" in assistant_tools.allowed_packs(with_cap)
    # Gói hợp đồng cũng gác riêng bằng cap `sales_contract`.
    assert "contract" not in assistant_tools.allowed_packs(no_cap)
    assert "contract" in assistant_tools.allowed_packs({"sales_contract": LEVEL_EDIT})
    # Không có cap → tool của gói unit bị chặn ở tầng thực thi (phòng khi LLM gọi bừa).
    unit_tools = [n for n, t in assistant_tools.TOOLS.items() if t["pack"] == "unit"]
    if unit_tools:
        assert "error" in assistant_tools.run_tool(unit_tools[0], {}, no_cap)["summary"]
    # Người dùng chỉ chọn gói "internal" → gói nền vẫn còn, gói unit thì không.
    packs = assistant_tools.allowed_packs(with_cap, ["internal"])
    assert "market" in packs and "floor" in packs and "unit" not in packs
    # Không tool nào của gói bị loại lọt vào schema gửi LLM.
    names = {s["function"]["name"] for s in assistant_tools.openai_tools(with_cap, ["internal"])}
    assert not (set(unit_tools) & names)


def test_packs_endpoint_and_cap_gating() -> None:
    h = _bearer("admin", "admin")
    for u in ("ast_ed", "ast_no", "ast_mem"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/member-units", json={"name": "_zz_ast"}, headers=h)
    client.post("/api/users", json={"username": "ast_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["assistant"]}, headers=h)
    client.post("/api/users", json={"username": "ast_no", "password": "pass123", "role": "editor"}, headers=h)
    client.post("/api/users", json={"username": "ast_mem", "password": "pass123",
                                    "role": "member", "member_units": ["_zz_ast"]}, headers=h)
    body = {"messages": [{"role": "user", "content": "Giá sàn hiện tại?"}]}

    # Editor KHÔNG có cap + đơn vị thành viên → 403 (chặn trước khi gọi LLM).
    assert client.post("/api/assistant/chat", json=body, headers=_bearer("ast_no", "pass123")).status_code == 403
    assert client.post("/api/assistant/chat", json=body, headers=_bearer("ast_mem", "pass123")).status_code == 403
    assert client.get("/api/assistant/packs", headers=_bearer("ast_no", "pass123")).status_code == 403

    # Editor CÓ cap `assistant` nhưng KHÔNG có `unit_daily` → gói unit hiện nhưng không active.
    eh = _bearer("ast_ed", "pass123")
    body = client.get("/api/assistant/packs", headers=eh).json()
    packs = body["packs"]
    by_key = {p["key"]: p for p in packs}
    # Bảng "Trợ lý làm được gì": liệt kê đủ công cụ từng gói + những việc chưa làm được.
    assert body["limits"] and all(isinstance(x, str) for x in body["limits"])
    assert all(len(p["items"]) == p["tools"] for p in packs)
    assert all(it["desc"] for p in packs for it in p["items"])
    # Gói không đủ quyền vẫn LIỆT KÊ (để người dùng biết có tính năng đó) nhưng phải nói rõ cần cap gì.
    assert by_key["unit"]["cap"] == "unit_daily" and by_key["unit"]["items"]
    assert by_key["market"]["core"] and by_key["market"]["active"]
    assert by_key["unit"]["active"] is False
    # Admin có mọi cap → gói unit active.
    assert {p["key"]: p for p in client.get("/api/assistant/packs", headers=h).json()["packs"]}["unit"]["active"]

    # Qua hàng rào quyền (tùy cấu hình LLM: 200 có key, 400/502 nếu chưa cấu hình).
    assert client.post("/api/assistant/chat", json=body, headers=eh).status_code != 403

    for u in ("ast_ed", "ast_no", "ast_mem"):
        client.delete(f"/api/users/{u}", headers=h)


def test_system_prompt_carries_ranking_and_rules() -> None:
    """Prompt phải mang luật chống bịa số + thứ tự yếu tố ảnh hưởng giá sàn."""
    p = assistant_service.SYSTEM
    assert "KHÔNG bịa số liệu" in p and "No Trading" in p
    assert "MRB SMR20" in p and "tồn kho" in p.lower()
    assert "Ban lãnh đạo" in p
    # SHFE RU là yếu tố mạnh nhất khi đo lại (r=0,67 · 89%) — từng bị bỏ sót khỏi bảng thứ tự.
    assert p.index("SHFE RU") < p.index("MRB SMR20 r=")
    # Giá mủ chén không có bằng chứng ⇒ không còn là tín hiệu "bổ sung" được phép làm lệch mô hình.
    assert "(giá mủ chén, tồn kho)" not in assistant_service.system_prompt("adjusted")


def test_system_prompt_date_is_computed_per_call(monkeypatch) -> None:
    """Ngày trong prompt phải tính mỗi lượt hỏi — hằng số lúc nạp module làm máy chủ chạy qua đêm nói sai ngày."""
    from datetime import date

    monkeypatch.setattr(assistant_service.edit_window, "today", lambda: date(2031, 5, 6))
    assert "Hôm nay là 2031-05-06" in assistant_service.system_prompt("model")
    assert "Hôm nay là" not in assistant_service.SYSTEM


def test_suggest_tool_filters_grade_and_labels_units() -> None:
    """Hỏi 1 chủng loại thì chỉ trả dòng đó; mỗi dòng mang đơn vị riêng; chủng loại lạ → báo lỗi gọn."""
    caps = _admin_caps()
    res = assistant_tools.run_tool("suggest_floor_adjustment", {"grade": "SVR 10 / CSR 10"}, caps)["summary"]
    if "error" in res:
        pytest.skip(f"DB chưa đủ dữ liệu giá sàn: {res['error'][:60]}")
    assert [it["grade"] for it in res["items"]] == ["SVR 10 / CSR 10"]
    assert res["items"][0]["don_vi"] == "USD/tấn (FOB)"
    assert res["items"][0]["muc_mo_hinh_de_xuat"] % 5 == 0         # bước ban hành FOB
    assert all("ngay_so_moi" in d for d in res["drivers"])
    assert res["drivers"][0]["chi_so"] == "SHFE RU"                  # xếp theo mức ảnh hưởng đã đo
    it = res["items"][0]   # câu tóm tắt định dạng sẵn: "SVR 10 / CSR 10: 2.340 → 2.355 USD/tấn FOB (+15, +0,6%) · GIỮ …"
    vn = lambda n: f"{n:,.0f}".replace(",", ".")  # noqa: E731
    assert f"{vn(it['gia_san_hien_hanh'])} → {vn(it['muc_mo_hinh_de_xuat'])} USD/tấn FOB" in it["tom_tat"]
    # Kịch bản: "giảm 5%" dù LLM truyền −5 thì cột giảm vẫn thấp hơn cơ sở (không đảo Bear/Bull).
    sc = assistant_tools.run_tool("simulate_floor_scenarios", {"shock_pct": -5}, caps)["summary"]
    row = next(r for r in sc["items"] if r["grade"] == "SVR 10 / CSR 10")
    assert sc["shock_pct"] == 5.0 and row["bear_giam"] < row["base_co_so"] < row["bull_tang"]
    short = assistant_tools.run_tool("suggest_floor_adjustment", {"grade": "SVR 10"}, caps)["summary"]
    assert [it["grade"] for it in short["items"]] == ["SVR 10 / CSR 10"]   # không lẫn "SVR 10 Mix"
    bad = assistant_tools.run_tool("suggest_floor_adjustment", {"grade": "SVR 99"}, caps)["summary"]
    assert "Không có chủng loại" in bad["error"]


def test_tools_match_source_services_and_reject_bad_dates() -> None:
    """Số của công cụ phải TRÙNG service gốc, và ngày hỏng không được lọt xuống SQL.

    Hai lớp lỗi đắt nhất của gói này: (1) tool tự cộng lại rồi lệch số với màn hình, (2) chuỗi ngày
    hỏng thả xuống Postgres khiến nguyên văn câu truy vấn lọt vào khung chat người dùng.
    """
    from app.services import sales_contract_report

    caps = _admin_caps()

    # (1) Đã ký chưa giao: tool bọc đúng service, không cộng thêm/bớt tầng nào.
    tool = assistant_tools.run_tool("get_undelivered_volume", {}, caps)["summary"]
    if "error" not in tool:
        raw = sales_contract_report.undelivered_on(assistant_service.edit_window.today().isoformat())
        assert tool["tong_khoi_luong_chua_giao_tan"] == round(sum(v["qty"] for v in raw.values()), 3)

    # (2) Ngày hỏng → câu báo lỗi gọn bằng tiếng Việt, TUYỆT ĐỐI không kèm SQL.
    for name, args in (("get_undelivered_volume", {"as_of": "banana"}),
                       ("get_contract_summary", {"date_from": "not-a-date"}),
                       ("get_contract_deliveries", {"date_from": "2026-13-40"}),
                       ("get_unit_stock", {"as_of": "hôm qua"})):
        msg = assistant_tools.run_tool(name, args, caps)["summary"].get("error", "")
        assert "không đúng định dạng" in msg, f"{name} chưa chặn ngày hỏng: {msg[:80]}"
        assert "SELECT" not in msg.upper(), f"{name} để lộ câu SQL ra ngoài"


def test_tool_labels_cover_every_tool() -> None:
    """Bảng "Trợ lý làm được gì?" phải có nhãn tiếng Việt cho MỌI công cụ — thêm tool mà quên nhãn
    thì người dùng nhìn thấy tên hàm."""
    assert set(assistant_tools.TOOL_LABELS) == set(assistant_tools.TOOLS)


def test_model_mode_hides_svr3l_adjustment_in_context() -> None:
    """Mức "Theo mô hình": bảng tín hiệu bối cảnh không được lộ % cần chỉnh SVR 3L nội địa."""
    from app.services.assistant_tools import floor_tools

    row = {"tin_hieu": "Giá sàn SVR 3L so với vùng giá tư nhân", "thay_doi_pct": 1.8,
           "chi_ap_dung": "chỉ giá nội địa SVR 3L",
           "ghi_chu": "THẤP hơn vùng; vùng 1–2 đồng/tấn; thay_doi_pct = mức cần chỉnh để vào vùng"}
    other = {"tin_hieu": "Tồn kho", "thay_doi_pct": -2.7, "ghi_chu": "x"}
    res = {"summary": {"tin_hieu": [other, row]}, "artifact": {"rows": [other, row]}}
    out = floor_tools.context_for_model_mode(res)
    hidden = out["summary"]["tin_hieu"][1]
    assert hidden["thay_doi_pct"] is None and "cần chỉnh" not in hidden["ghi_chu"]
    assert out["summary"]["tin_hieu"][0]["thay_doi_pct"] == -2.7
    assert out["artifact"]["rows"][1]["thay_doi_pct"] is None
    assert "get_floor_context" in assistant_service._MODEL_MODE_FILTERS


def test_inventory_trend_compares_with_latest_issuance() -> None:
    """Tồn kho phải có mốc "so với lần ban hành gần nhất" — trùng số với engine Gợi ý giá sàn."""
    from app.services import floor_repo, inventory_daily

    res = assistant_tools.run_tool("get_inventory_trend", {}, _admin_caps())["summary"]
    if "error" in res:
        pytest.skip("DB chưa có tồn kho ngày")
    vs = res["so_voi_lan_ban_hanh_gan_nhat"]
    today = assistant_service.edit_window.today().isoformat()
    sched = floor_repo.list_schedules(date_to=today)
    if vs is None:      # chưa có lần ban hành, hoặc lần ban hành trước khi có tồn kho ngày
        assert not sched or str(sched[0]["as_of"]) < inventory_daily.STOCK_START
        return
    assert vs["ngay_ban_hanh"] == str(sched[0]["as_of"])
    snaps = inventory_daily.load(vs["ngay_ban_hanh"], today)
    ref = inventory_daily.at(snaps, res["ngay_gan_nhat"], vs["ngay_ban_hanh"])
    assert vs["ton_kho_pct"] == ref["d_ton_kho_pct"] and vs["ton_tu_do_tan"] == ref["d_free"]
