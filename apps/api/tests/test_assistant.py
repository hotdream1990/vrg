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
    packs = client.get("/api/assistant/packs", headers=eh).json()["packs"]
    by_key = {p["key"]: p for p in packs}
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
