"""Quy đổi giá gốc của sàn → USD/tấn (bulletin/convert.py).

Khoá lại lỗi chuyên viên báo 21/07/2026: MRB SMR20 yết 223,85 US cents/kg = 2238,5 USD/tấn
nhưng hệ thống hiện 2238. Hai nguyên nhân chồng nhau:
  1. hàm quy đổi trả SỐ NGUYÊN → mất phần ,5 mà nguồn có thật;
  2. round() của Python làm tròn về số CHẴN nên 2238,5 → 2238 (luôn thiệt xuống), không phải
     làm tròn nửa lên như người dùng vẫn hiểu.
"""

import sys
from pathlib import Path

_BULLETIN = Path(__file__).resolve().parents[3] / "services" / "bulletin"
if str(_BULLETIN) not in sys.path:
    sys.path.insert(0, str(_BULLETIN))

from bulletin.convert import (  # noqa: E402
    cny_tonne_to_usd_tonne,
    jpy_kg_to_usd_tonne,
    r0,
    r1,
    to_usd_tonne_detail,
    uscents_kg_to_usd_tonne,
)


# Bảng MRB ngày 20/07/2026 (ảnh nguồn chuyên viên gửi) — cents/kg → USD/tấn.
MRB_20_07 = [
    ("SMR CV", 306.10, 3061.0),
    ("SMR L", 303.60, 3036.0),
    ("SMR 5", 228.85, 2288.5),   # ca lỗi: trước đây ra 2288
    ("SMR GP", 227.60, 2276.0),
    ("SMR 10", 225.10, 2251.0),
    ("SMR 20", 223.85, 2238.5),  # ca lỗi được báo
]


def test_mrb_cents_giu_nguyen_nua_don_vi() -> None:
    for grade, cents, expected in MRB_20_07:
        assert uscents_kg_to_usd_tonne(cents) == expected, grade


def test_smr20_khop_dung_so_chuyen_vien_doi_chieu() -> None:
    usd, fx_pair, fx_rate = to_usd_tonne_detail(223.85, "US cents/kg", {})
    assert usd == 2238.5          # KHÔNG phải 2238
    assert fx_pair is None and fx_rate is None   # cents/kg đã ở hệ USD, không cần tỷ giá


def test_r1_lam_tron_nua_LEN_khong_ve_so_chan() -> None:
    # round() dựng sẵn cho 2238 và 2288 (về số chẵn) — đây là lý do giá luôn bị hạ.
    assert (round(2238.5), round(2288.5)) == (2238, 2288)
    assert r1(2238.5) == 2238.5 and r1(2288.5) == 2288.5
    assert r1(2238.44) == 2238.4 and r1(2238.45) == 2238.5


def test_r0_cho_ban_tin_lam_tron_nua_len() -> None:
    # Bản tin in số nguyên; ,5 phải lên chứ không hạ xuống như round().
    assert r0(2238.5) == 2239
    assert r0(2288.5) == 2289
    assert r0(2238.4) == 2238


def test_cac_don_vi_khac_van_quy_doi_dung() -> None:
    # SHFE CNY/tấn và OSE JPY/kg — dùng tỷ giá, giữ 1 số lẻ.
    assert cny_tonne_to_usd_tonne(16955, 6.7689) == r1(16955 / 6.7689)
    assert jpy_kg_to_usd_tonne(407.4, 162.5055) == r1(407.4 * 1000 / 162.5055)


def test_thieu_ty_gia_thi_khong_doan_bua() -> None:
    usd, fx_pair, fx_rate = to_usd_tonne_detail(724.0, "Sen/kg", {})
    assert usd is None                  # thiếu USD/MYR → để trống
    assert fx_pair == "USD/MYR" and fx_rate is None
