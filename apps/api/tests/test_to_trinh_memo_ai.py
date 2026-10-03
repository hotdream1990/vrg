"""Test thuần (không DB, không mạng): nội dung tờ trình mặc định, làm sạch, AI tách khung + cảnh báo,
hình dự thảo, quy tắc bước."""

from __future__ import annotations

import pytest

from app.services import du_thao_sheet, floor_draft_stage as st, to_trinh_ai, to_trinh_memo

T1, T2 = "2026-09-23", "2026-09-22"


def _s(san, g, p, c):
    d = None if p is None or c is None else c - p
    return {"san": san, "grade": g, "prev": p, "curr": c, "d_abs": d,
            "d_pct": None if d is None else round(d / p * 100, 1), "curr_as_of": T1 if c else None}


DOC = {"as_of": "2026-09-24", "year": 2026, "lan": 22, "prev_lan": 21, "t1": T1, "t2": T2,
       "settlement": [_s("OSE", "RSS3", None, None), _s("SHANGHAI", "RSS3", 2830, 2849),
                      _s("SGX", "RSS3", 2780, 2790), _s("SGX", "TSR20", 2417, 2495)],
       "physical": [{"grade": "STR20", "prev": 2519, "curr": 2513, "d_abs": -6, "d_pct": -0.2}]}


def test_defaults_follow_template_and_only_state_numbers() -> None:
    inv = [{"as_of": "2026-09-17", "ton_kho": 56674}, {"as_of": "2026-09-10", "ton_kho": 59566}]
    m = to_trinh_memo.defaults(DOC, inv)
    leads = [p["lead"] for p in m["futures"]]
    assert leads == ["OSE (Osaka Exchange) – RSS3:", "SHANGHAI (SHFE) – RSS3:",
                     "SGX (Singapore Exchange/SICOM) – RSS3 & TSR20:"]
    assert m["futures"][0]["text"] == "Sàn OSE nghỉ giao dịch, không phát sinh giá tham chiếu mới."
    assert "tăng từ 2.830 lên 2.849 USD/tấn (+19 USD/tấn, +0,7%)" in m["futures"][1]["text"]
    assert "khảo sát ngày 22/9/2026 và 23/9/2026" in m["futures_note"] and "OSE không có phiên" in m["futures_note"]
    assert "STR20 giảm 6 USD/tấn (-0,2%) còn 2.513 USD/tấn" in m["physical"][0]["text"]
    assert m["inventory"] == {"lead": "Tồn kho Tập đoàn lũy kế tuần 38: 17/09/2026: 56.674 tấn giảm 2.892 tấn",
                              "text": "so với tuần trước đó là 59.566 tấn."}
    assert "lần thứ 22 năm 2026" in m["intro"] and m["signers"]["approver_name"] == "Lê Thanh Hưng"
    assert m["physical_title"] == "tham chiếu giá nguồn từ ANRPC các ngày 22/9 và 23/9" and m["so"] == ""
    # Bản nháp cũ đã sửa tay diễn giải (n1) → giữ đoạn đó thay vì đoạn tự dựng.
    assert to_trinh_memo.defaults({**DOC, "n1": ["- Đoạn sửa tay"]})["futures"] == [{"lead": "", "text": "Đoạn sửa tay"}]


def test_clean_merges_with_base_and_trims() -> None:
    base = to_trinh_memo.defaults(DOC)
    out = to_trinh_memo.clean({"so": "  54/TTr-TTKD ", "futures": [{"lead": "", "text": " "}, "Đoạn"],
                               "signers": {"left_name": "A"}, "sign_date": "x"}, base)
    assert out["so"] == "54/TTr-TTKD" and out["futures"] == [{"lead": "", "text": "Đoạn"}]
    assert out["signers"]["left_name"] == "A" and out["signers"]["right_name"] == base["signers"]["right_name"]
    assert out["intro"] == base["intro"] and out["sign_date"] == base["sign_date"]


def test_ai_parse_splits_known_leads_and_skips() -> None:
    leads = ["OSE (Osaka Exchange) – RSS3:", "SHANGHAI (SHFE) – RSS3:"]
    out = """### NGUON
Nguồn: số liệu các sàn.
### SAN
**OSE (Osaka Exchange) – RSS3:** Sàn nghỉ lễ.
- SHANGHAI (SHFE) - RSS3: Giá tăng 19 USD/tấn.
### VATCHAT_GHICHU
(bỏ qua)
### CUNGCAU
Cung – cầu thâm hụt."""
    p = to_trinh_ai.parse(out, leads)
    assert p["futures_note"] == "Nguồn: số liệu các sàn." and "physical_note" not in p
    assert p["futures"][0] == {"lead": leads[0], "text": "Sàn nghỉ lễ."}
    assert p["futures"][1]["lead"] == "SHANGHAI (SHFE) - RSS3:" and p["futures"][1]["text"] == "Giá tăng 19 USD/tấn."
    assert p["outlook"] == [{"lead": "", "text": "Cung – cầu thâm hụt."}]


def test_ai_warnings_numbers_direction_and_missing_parts() -> None:
    part = {"futures": [{"lead": "SGX:", "text": "RSS3 tăng 10 USD/tấn lên 9.999 USD/tấn, chắc chắn còn tăng."}],
            "outlook": [{"lead": "", "text": "Ban TTKD đề xuất giảm giá sàn lần này."}]}
    w = to_trinh_ai.warnings(part, "RSS3: 2.780 → 2.790; +10 USD/tấn", "tăng")
    assert any("9.999" in x for x in w) and any("tuyệt đối" in x for x in w)
    assert any('"giảm" trong khi phương án tăng' in x for x in w)
    assert any("chưa viết đủ" in x for x in to_trinh_ai.warnings({"futures": []}, "", "giữ nguyên"))


def test_ai_generate_merges_and_stamps_sig(monkeypatch) -> None:
    monkeypatch.setattr(to_trinh_ai.ctx, "build", lambda draft, inv: "SHANGHAI RSS3 +19 USD/tấn")
    monkeypatch.setattr(to_trinh_ai.llm, "complete",
                        lambda system, user, max_tokens: "### SAN\nSHANGHAI (SHFE) – RSS3: Tăng 19 USD/tấn.\n"
                                                         "### CUNGCAU\nHỗ trợ điều chỉnh tăng giá sàn.")
    rows = [{"grade": "SVR 10 / CSR 10", "unit": "USD/T", "fob": 2420, "vnd": 1, "fob_delta": 80, "vnd_delta": 1}]
    draft = {"doc": DOC, "proposal": {"rows": rows}, "as_of": DOC["as_of"]}
    memo = to_trinh_memo.defaults(DOC)
    res = to_trinh_ai.generate(draft, memo, "admin")
    m = res["memo"]
    assert m["futures"] == [{"lead": "SHANGHAI (SHFE) – RSS3:", "text": "Tăng 19 USD/tấn."}]
    assert m["intro"] == memo["intro"] and m["ai"]["sig"] == st.proposal_sig(draft["proposal"])
    assert m["ai"]["by"] == "admin" and res["warnings"] == []


def test_du_thao_sheet_labels_and_vcb_line() -> None:
    prop = {"rows": [{"grade": "SVR 10 / CSR 10", "prev_fob": 2340, "fob": 2420, "fob_delta": 80,
                      "prev_vnd": 59_250_000, "vnd": 61_350_000, "vnd_delta": 2_100_000},
                     {"grade": "Skim Block", "prev_fob": None, "fob": None, "fob_delta": None,
                      "prev_vnd": 39_850_000, "vnd": 41_950_000, "vnd_delta": -50_000}]}
    html = du_thao_sheet.render(prop, DOC, {"vcb_rate": 25790, "vcb_time": "8g30", "vcb_date": "2026-09-09"})
    assert "DỰ THẢO GIÁ SÀN ĐIỀU CHỈNH" in html and "(Giá sàn lần thứ 22/2026 ngày 24/9/2026)" in html
    assert "SVR10/CSR 10" in html and "2.100.000" in html and "-50.000" in html
    assert "Tỷ giá VCB mua CK ngày lấy lúc 8g30 ngày 09/9/2026: 25.790 đ" in html
    assert "…… đ" in du_thao_sheet.render(prop, DOC, None)


def test_stage_rules() -> None:
    full = {"rows": [{"grade": "x", "label": "SVR10", "unit": "USD/T", "fob": 1, "vnd": 1}]}
    st.check_move("nhap", "du_thao", full)
    with pytest.raises(st.StageError, match="SVR10"):
        st.check_move("nhap", "du_thao", {"rows": [{**full["rows"][0], "fob": None}]})
    with pytest.raises(st.StageError, match="bước kế tiếp"):
        st.check_move("nhap", "to_trinh", full)
    st.check_move("to_trinh", "nhap", full)          # trả về thẳng bước bất kỳ phía trước
    with pytest.raises(st.StageError, match="chưa triển khai"):
        st.check_move("to_trinh", "ap_dung", full)
    st.check_edit("to_trinh", "memo")
    with pytest.raises(st.StageError, match="bước Tờ trình"):
        st.check_edit("nhap", "memo")
    assert st.normalize(None) == "nhap" and st.proposal_sig(full) != st.proposal_sig({"rows": []})
