"""Test offline cho SGX/SICOM — đọc báo cáo Daily Futures theo PHIÊN (không gọi mạng).

Dữ liệu mẫu lấy nguyên văn từ file thật của SGX: phiên 07/08/2026 (có giao dịch) và phiên
10/08/2026 (SETTLE = 0 — sàn không ra settlement cho cao su = No Trading).
"""

import csv
import io
from datetime import date

from crawlers.exchanges import sgx_sicom as sgx

_HEAD = "DATE,COM,COM_MM,COM_YY,OPEN,HIGH,LOW,CLOSE,SETTLE,VOLUME,OINT,SERIES"

# Phiên 07/08/2026 — RT (RSS3) và TF (TSR20) đều có settlement.
_CSV_0807 = "\n".join([
    _HEAD,
    "20260807,RT   ,09,2026,273.9,273.9,273.9,273.9,273.9,1,14,RTU26",
    "20260807,RT   ,10,2026,,,,,271.9,0,68,RTV26",
    "20260807,TF   ,09,2026,218.4,219.8,218.3,218.8,219.2,552,4751,TFU26",
    "20260807,TF   ,10,2026,218.1,219.2,217.3,218.2,218.3,2335,15514,TFV26",
    "20260807,CN   ,09,2026,100,100,100,100,100,10,10,CNU26",
])

# Phiên 10/08/2026 — SGX không ra settlement cho cao su: SETTLE = 0.
_CSV_0810 = "\n".join([
    _HEAD,
    "20260810,RT   ,09,2026,,,,,0,0,14,RTU26",
    "20260810,TF   ,09,2026,218.3,220.1,217.9,220,0,102,4686,TFU26",
])


def _rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_lay_dung_ky_han_thang_sau() -> None:
    recs = {r.grade: r for r in sgx._records(date(2026, 8, 7), _rows(_CSV_0807))}
    assert set(recs) == {"RSS3", "TSR20"}                 # bỏ mã ngoài rubber (CN)
    assert recs["RSS3"].price == 273.9                    # RT tháng 09/2026
    assert recs["TSR20"].price == 219.2                   # TF tháng 09/2026
    assert recs["RSS3"].contract == "2026-09"
    assert recs["RSS3"].unit == "US cents/kg"
    assert all(r.as_of == date(2026, 8, 7) for r in recs.values())


def test_settle_0_giu_nguyen_la_no_trading() -> None:
    """SETTLE = 0 trong file chính thức = No Trading → lưu 0, KHÔNG đắp giá phiên trước."""
    recs = {r.grade: r for r in sgx._records(date(2026, 8, 10), _rows(_CSV_0810))}
    assert recs["RSS3"].price == 0
    assert recs["TSR20"].price == 0
    assert all(r.extra["no_trading"] for r in recs.values())


def test_ky_han_thang_sau_theo_ngay_phien() -> None:
    assert sgx._target_delivery_month(date(2026, 8, 7)) == (2026, 9)
    assert sgx._target_delivery_month(date(2026, 12, 31)) == (2027, 1)


def test_weekdays_co_dau() -> None:
    # 07/08/2026 (T6) → 10/08/2026 (T2): đúng 1 ngày trong tuần; chiều ngược lại là số âm.
    assert sgx._weekdays(date(2026, 8, 7), date(2026, 8, 10)) == 1
    assert sgx._weekdays(date(2026, 8, 10), date(2026, 8, 7)) == -1
    assert sgx._weekdays(date(2026, 8, 7), date(2026, 8, 7)) == 0
