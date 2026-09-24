"""Đối chiếu giá sàn SVR 3L với giá mủ tư nhân (quy tắc chuyên viên) — công thức, vùng hợp lý,
hướng tác động và cách chọn điểm trong vùng theo tồn kho."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import floor_recommend as fr, market_quote_repo, private_price_benchmark as pb

_D = "2099-01-02"


def test_cong_thuc_khop_vi_du_tai_lieu() -> None:
    """Ví dụ trong file chuyên viên: 580 × 1,08 × 100.000 + 2.000.000 = 64.640.000."""
    assert pb.svr3l_cost(580) == 64_640_000
    assert pb.svr3l_cost(580, 2_100_000) == 64_740_000


def test_chon_diem_trong_vung_theo_ton_kho() -> None:
    assert pb._inventory_trend({"d_ton_kho_pct": 10.0})[0].startswith("TĂNG")
    assert pb._inventory_trend({"d_ton_kho_pct": -10.0})[0].startswith("GIẢM")
    assert pb._inventory_trend({"d_ton_kho_pct": 2.0})[0].startswith("đi ngang")   # dưới ngưỡng ±3%
    assert pb._inventory_trend({"d_ton_kho_pct": 5.0, "d_free_pct": -5.0})[0].startswith("trái chiều")
    assert pb._inventory_trend(None)[0] == "chưa đủ dữ liệu"


@pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
def test_benchmark_vung_huong_va_muc_goi_y() -> None:
    if not pb._floor_svr3l(_D):
        pytest.skip("DB chưa có biểu giá sàn SVR 3L")
    floor = pb._floor_svr3l(_D)["noi_dia_vnd"]
    # Chọn giá mủ để giá thành tham chiếu thấp hơn giá sàn ~5 triệu → giá sàn CAO hơn vùng.
    tsc = round((floor - 5_000_000 - pb.DEFAULT_PROCESSING_COST) / (pb.PRIVATE_SVR3L_COEF * pb.TSC_TO_TONNE))
    market_quote_repo.save_quote({"as_of": _D, "private_prices": {"__TEST TN__": {"price": tsc, "price_max": None}}})
    try:
        b = pb.benchmark(_D, {"d_ton_kho_pct": 10.0})
        assert b is not None
        ref = pb.svr3l_cost(tsc)
        assert b["gia_thanh_tham_chieu"] == ref
        assert b["vung_gia_san_hop_ly"] == {"tu": ref + 700_000, "den": ref + 1_000_000}
        assert b["huong_tac_dong"] == "hỗ trợ HẠ" and b["gia_san_hien_hanh_so_voi_vung"].startswith("CAO")
        low = fr.to_step(ref + 700_000, "VNĐ/T", "up")                  # mép dưới, bội 50.000, vẫn trong vùng
        assert low % 50_000 == 0 and ref + 700_000 <= low <= ref + 1_000_000
        assert b["muc_goi_y_theo_gia_tu_nhan"] == low                  # tồn kho tăng → mép dưới
        assert b["dieu_chinh_can_thiet"] == round(low - floor)
        assert b["muc_de_xuat_noi_dia_svr3l"] == low                   # chưa có mức mô hình → điểm theo tồn kho
        # Có mức mô hình nằm TRONG vùng → giữ mô hình; nằm NGOÀI → kéo về điểm trong vùng.
        fob = pb._floor_svr3l(_D)["fob_usd"]
        inside_fob = (ref + 850_000) / floor * fob
        assert pb.benchmark(_D, None, inside_fob)["ket_luan"].startswith("Mức mô hình")
        assert pb.benchmark(_D, None, inside_fob)["muc_mo_hinh_so_voi_vung"] == "TRONG vùng hợp lý"
        above = pb.benchmark(_D, {"d_ton_kho_pct": -10.0}, fob * 1.2)
        assert above["muc_mo_hinh_so_voi_vung"] == "CAO HƠN vùng hợp lý"
        assert above["muc_de_xuat_noi_dia_svr3l"] == fr.to_step(ref + 1_000_000, "VNĐ/T", "down")
        assert above["muc_mo_hinh_noi_dia_uoc_tinh"] % 50_000 == 0 and "kéo về" in above["ket_luan"]
    finally:
        with session_scope() as db:
            db.execute(text("DELETE FROM market_quote WHERE as_of = CAST(:d AS date)"), {"d": _D})
            db.execute(text("DELETE FROM fact_price WHERE as_of = CAST(:d AS date)"), {"d": _D})


@pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
def test_tool_va_bang_tin_hieu_chay_duoc() -> None:
    """Công cụ Trợ lý + bảng tín hiệu bối cảnh chạy thật (không ném lỗi) dù có hay không có dữ liệu."""
    from app.services.assistant_tools import floor_tools, private_price_tools

    out = private_price_tools._private_benchmark({})
    assert "summary" in out or "error" in out
    ctx = floor_tools._floor_context({})
    assert "summary" in ctx or "error" in ctx


def test_muc_theo_mo_hinh_go_het_muc_dieu_chinh() -> None:
    """Mức "Theo mô hình" không được thấy mức giá sàn nào khác ngoài số mô hình."""
    from app.services.assistant_tools import private_price_tools

    full = {"summary": {"vung_gia_san_hop_ly": {"tu": 1, "den": 2}, "ghi_chu_vi_tri": "x",
                        **{k: 1 for k in pb.ADJUSTMENT_KEYS}},
            "artifact": {"rows": [{"hang_muc": "A"}, {"hang_muc": "Mức gợi ý theo giá tư nhân + tồn kho"}]}}
    out = private_price_tools.for_model_mode(full)
    assert not set(pb.ADJUSTMENT_KEYS) & set(out["summary"])
    assert out["summary"]["ghi_chu_vi_tri"] == "x"
    assert [r["hang_muc"] for r in out["artifact"]["rows"]] == ["A"]
