"""Test engine gợi ý giá sàn: đại số ridge, metrics, CHỐNG look-ahead, và endpoint backtest.

Phần toán học chạy độc lập (không cần DB); phần endpoint tự bỏ qua nếu DB không sẵn sàng.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import floor_model as fm
from app.services import floor_recommend as fr
from app.services import floor_suggest as fs

# ----------------------------- Toán học (không cần DB) -----------------------------


def test_ridge_fit_equals_ols_when_alpha_zero() -> None:
    # y = 2x (chuẩn): alpha=0 ⇒ OLS, slope≈2, intercept≈0.
    x = np.array([[1.0], [2.0], [3.0], [4.0]])
    y = np.array([2.0, 4.0, 6.0, 8.0])
    inter, beta = fm.ridge_fit(x, y, 0.0)
    assert abs(inter) < 1e-9
    assert abs(beta[0] - 2.0) < 1e-9


def test_ridge_shrinks_coefficient() -> None:
    # alpha lớn ⇒ hệ số co về 0 (nhỏ hơn OLS).
    x = np.array([[-1.0], [0.0], [1.0], [2.0]])
    y = np.array([-2.0, 0.0, 2.0, 4.0])
    _, b0 = fm.ridge_fit(x, y, 0.0)
    _, b1 = fm.ridge_fit(x, y, 10.0)
    assert abs(b1[0]) < abs(b0[0])


def test_metrics_perfect_and_known() -> None:
    assert fm.metrics([100, 110, 90], [100, 110, 90]) == {
        "mae": 0.0, "mape": 0.0, "rmse": 0.0, "r2": 1.0, "n": 3}
    m = fm.metrics([100.0, 200.0], [110.0, 180.0])  # lệch 10 & 20
    assert m["mae"] == 15.0
    assert m["mape"] == 10.0  # (10% + 10%)/2


def test_hit_rate_direction() -> None:
    # actual đi +,- ; pred đoán đúng cả hai hướng so với lần trước ⇒ 100%.
    assert fm.hit_rate([100, 110, 105], [100, 120, 100]) == 100.0
    # đoán sai cả hai ⇒ 0%.
    assert fm.hit_rate([100, 110, 105], [100, 90, 130]) == 0.0


def _synthetic() -> tuple[list[str], dict, dict]:
    """11 lần ban hành với quan hệ tuyến tính floor↑ theo futures↑ (để kiểm causal)."""
    dates = [f"2025-{m:02d}-01" for m in range(1, 12)]
    fmap, idx = {}, {}
    for i, d in enumerate(dates):
        drv = 100.0 + 10.0 * i
        for k in fs.FEATS[1:]:  # 4 futures = driver + offset nhỏ
            idx.setdefault(k, []).append((d, drv + hash(k) % 5))
        fmap[(d, "SVR 10")] = 1500.0 + 8.0 * i
    return dates, fmap, idx


def test_fit_at_no_lookahead() -> None:
    """Dự báo tại 1 lần KHÔNG được đổi khi nối thêm dữ liệu TƯƠNG LAI (chống look-ahead)."""
    dates, fmap, idx = _synthetic()
    train, target = dates[:8], dates[8]
    r1 = fs._fit_at(train, target, "SVR 10", fmap, idx, "v1", 0.0)

    # Nối thêm 2 lần tương lai vào idx + fmap (sau target), giữ NGUYÊN train & target.
    fmap2 = dict(fmap)
    idx2 = {k: list(v) for k, v in idx.items()}
    for j, d in enumerate(["2025-12-01", "2026-01-01"]):
        for k in fs.FEATS[1:]:
            idx2[k].append((d, 999.0 + j))  # giá trị tương lai cực đoan
        fmap2[(d, "SVR 10")] = 3000.0 + j
    r2 = fs._fit_at(train, target, "SVR 10", fmap2, idx2, "v1", 0.0)

    assert r1 is not None and r2 is not None
    assert r1["pred"] == r2["pred"], "chuẩn hoá phải causal — không rò rỉ tương lai"


def test_target_and_unit_for_domestic_only_grade() -> None:
    """SkimBlock (chỉ-nội-địa) hồi quy trên VNĐ/T; grade thường vẫn dùng FOB USD/T."""
    # grade thường: lấy FOB, đơn vị USD/T (bỏ qua domestic).
    assert fs._target("SVR 10", 2250.0, 57700000.0) == 2250.0
    assert fs._unit("SVR 10") == "USD/T"
    # Skim Block: lấy domestic_vnd (không có FOB), đơn vị VNĐ/T.
    assert fs._target("Skim Block", None, 43000000.0) == 43000000.0
    assert fs._unit("Skim Block") == "VNĐ/T"
    # thiếu cả hai ⇒ None (bị loại khỏi fmap).
    assert fs._target("Skim Block", None, None) is None


def test_build_item_carries_unit() -> None:
    bt = {"mae": 50.0, "mape": 4.0, "hit": 90.0, "n": 20}
    it = fr.build_item("SkimBlock", None, 43000000.0, {"r": 0.9}, 44050000.0, bt,
                       shfe_chg=None, unit="VNĐ/T")
    assert it["unit"] == "VNĐ/T" and it["action"] == "lower"
    # mặc định vẫn USD/T cho grade thường.
    assert fr.build_item("SVR 10", 1500.0, 1520.0, {"r": 0.9}, 1500.0, bt, 2.0)["unit"] == "USD/T"


def test_fit_at_shock_moves_prediction_in_order() -> None:
    """Cú sốc rổ +/- phải đẩy dự báo lên/xuống đúng hướng (kịch bản Tăng/Giảm)."""
    dates, fmap, idx = _synthetic()
    train, target = dates[:8], dates[8]
    base = fs._fit_at(train, target, "SVR 10", fmap, idx, "v1", 0.0)
    up = fs._fit_at(train, target, "SVR 10", fmap, idx, "v1", 0.0, shock=0.1)
    down = fs._fit_at(train, target, "SVR 10", fmap, idx, "v1", 0.0, shock=-0.1)
    assert down["pred"] < base["pred"] < up["pred"]


# ----------------------- Luật đề xuất điều chỉnh (không cần DB) -----------------------


def test_decide_action_dead_band() -> None:
    # |Δ| <= band ⇒ giữ (nhiễu); vượt band ⇒ nâng/hạ theo dấu.
    assert fm.decide_action(None, 10) is None
    assert fm.decide_action(5, 10) == "hold"
    assert fm.decide_action(-10, 10) == "hold"   # đúng biên vẫn giữ
    assert fm.decide_action(25, 10) == "raise"
    assert fm.decide_action(-25, 10) == "lower"


def test_confidence_levels() -> None:
    assert fm.confidence(1.9, 88.0, 22) == "high"     # đạt mục tiêu đề án
    assert fm.confidence(8.0, 60.0, 20) == "medium"   # MAPE 6–10%
    assert fm.confidence(12.0, 50.0, 20) == "low"     # MAPE > 10%
    assert fm.confidence(2.0, 90.0, 4) == "low"       # quá ít lần kiểm định
    assert fm.confidence(None, None, 10) == "low"


def test_prev_floor_picks_latest_prior_with_value() -> None:
    fd = ["2025-01-01", "2025-02-01", "2025-03-01"]
    fmap = {("2025-01-01", "SVR 10"): 1500.0, ("2025-03-01", "SVR 10"): 1600.0}
    # tại 2025-03-01: lần trước CÓ GIÁ gần nhất là 2025-01-01 (02-01 thiếu grade).
    assert fr.prev_floor(fd, fmap, "SVR 10", "2025-03-01") == ("2025-01-01", 1500.0)
    assert fr.prev_floor(fd, fmap, "SVR 10", "2025-01-01") == (None, None)


def test_drivers_change_pct() -> None:
    idx = {("shfe", "RU"): [("2025-01-01", 100.0), ("2025-02-01", 110.0)]}
    drv = fr.drivers(idx, [("shfe", "RU")], fs.LABELS, fs._at, "2025-01-01", "2025-02-01")
    assert drv[0]["index"] == "SHFE RU" and drv[0]["change_pct"] == 10.0


def test_build_item_hold_and_shfe_caution() -> None:
    bt = {"mae": 50.0, "mape": 4.0, "hit": 90.0, "n": 20}
    # |Δ|=20 ≤ band 50 ⇒ GIỮ; tin cậy cao.
    hold = fr.build_item("SVR 10", 1500.0, 1520.0, {"r": 0.9}, 1500.0, bt, shfe_chg=2.0)
    assert hold["action"] == "hold" and hold["delta"] == 20 and hold["confidence"] == "high"
    # Δ=+120 (raise) nhưng SHFE -3% ngược hướng ⇒ hạ tin cậy + caution.
    opp = fr.build_item("SVR 10", 1700.0, 1620.0, {"r": 0.9}, 1500.0, bt, shfe_chg=-3.0)
    assert opp["action"] == "raise" and opp["cautions"] == ["shfe_opposite"]
    assert opp["confidence"] == "medium"  # high → medium


def test_inventory_lean_uses_total_and_free_with_threshold() -> None:
    """Tồn kho tổng + tự do so lần trước: dưới ±3% là đi ngang; hai chỉ số trái chiều thì không nghiêng."""
    assert fr.inventory_lean(None) is None
    assert fr.inventory_lean({"d_ton_kho_pct": None, "d_free_pct": None}) is None
    assert fr.inventory_lean({"d_ton_kho_pct": 2.9, "d_free_pct": -2.9})["direction"] == "flat"
    assert fr.inventory_lean({"d_ton_kho_pct": 1.0, "d_free_pct": 8.0})["direction"] == "up"
    assert fr.inventory_lean({"d_ton_kho_pct": -4.0, "d_free_pct": None})["direction"] == "down"
    assert fr.inventory_lean({"d_ton_kho_pct": 5.0, "d_free_pct": -6.0})["direction"] == "mixed"


def test_build_item_inventory_opposite_lowers_confidence() -> None:
    """Nâng mà tồn kho tăng / hạ mà tồn kho giảm ⇒ hạ tin cậy; số mô hình giữ nguyên."""
    bt = {"mae": 50.0, "mape": 4.0, "hit": 90.0, "n": 20}
    up = fr.build_item("SVR 10", None, 1620.0, {"r": 0.9}, 1500.0, bt, shfe_chg=2.0, lean="up")
    assert up["action"] == "raise" and up["suggested"] == 1620.0
    assert up["cautions"] == ["inventory_opposite"] and up["confidence"] == "medium"
    agree = fr.build_item("SVR 10", None, 1620.0, {"r": 0.9}, 1500.0, bt, shfe_chg=2.0, lean="down")
    assert agree["cautions"] == [] and agree["confidence"] == "high"
    both = fr.build_item("SVR 10", None, 1380.0, {"r": 0.9}, 1500.0, bt, shfe_chg=3.0, lean="down")
    assert both["action"] == "lower" and both["cautions"] == ["shfe_opposite", "inventory_opposite"]
    assert both["confidence"] == "low"          # 2 tín hiệu ngược ⇒ hạ 2 bậc
    hold = fr.build_item("SVR 10", None, 1520.0, {"r": 0.9}, 1500.0, bt, shfe_chg=2.0, lean="up")
    assert hold["action"] == "hold" and hold["cautions"] == []


def test_build_item_confidence_uses_actionable_error() -> None:
    # MAPE gộp tốt (3%) nhưng sai số TRÊN CÁC LẦN ĐIỀU CHỈNH cao (9%, n=6).
    bt = {"mae": 50.0, "mape": 3.0, "hit": 90.0, "n": 20, "mape_move": 9.0, "n_move": 6}
    # GIỮ ⇒ vẫn dùng MAPE gộp ⇒ tin cậy CAO.
    hold = fr.build_item("SVR 10", 1500.0, 1510.0, {"r": 0.9}, 1500.0, bt, shfe_chg=2.0)
    assert hold["action"] == "hold" and hold["confidence"] == "high"
    # NÂNG ⇒ chấm theo mape_move 9% ⇒ chỉ TRUNG BÌNH (không phải CAO theo 3% gộp).
    rz = fr.build_item("SVR 10", 1700.0, 1620.0, {"r": 0.9}, 1500.0, bt, shfe_chg=2.0)
    assert rz["action"] == "raise" and rz["mape_move"] == 9.0 and rz["confidence"] == "medium"


# ----------------------------- Endpoint (cần DB + auth) -----------------------------

pytestmark_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
client = TestClient(app)


def _token() -> dict:
    from app.services import user_repo
    user_repo.seed_admin()
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytestmark_db
def test_backtest_endpoint_protected_and_shape() -> None:
    assert client.get("/api/floor-suggest/backtest").status_code == 401  # chặn khi chưa auth
    h = _token()
    r = client.get("/api/floor-suggest/backtest", params={"grade": "SVR 10 / CSR 10", "model": "v1"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["grade"] == "SVR 10 / CSR 10" and "metrics" in body and "points" in body
    if body["points"]:  # nếu DB có dữ liệu giá sàn
        assert "mape" in body["metrics"] and body["metrics"]["n"] == len(body["points"])
        p = body["points"][0]
        assert {"as_of", "actual", "pred", "err", "err_pct"} <= set(p)


@pytestmark_db
def test_backtest_summary_endpoint() -> None:
    r = client.get("/api/floor-suggest/backtest/summary?model=v1", headers=_token())
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    if rows:
        assert rows[0]["grade"] == "SVR 10 / CSR 10"  # mặt hàng PoC đứng đầu
        assert {"grade", "mape", "hit", "n"} <= set(rows[0])
