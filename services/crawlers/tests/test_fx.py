"""Test offline cho FX CNY/JPY/THB + MYR (BNM) — không cần mạng.

Nguồn chính exchangerates.org.uk (bảng "Recent history" giao diện 03/09/2026) + dự phòng x-rates.com
(chỉ nhận trang ĐÃ CHỐT, Close ngày D = ảnh chụp ngày D+1) + quy tắc dùng dự phòng theo từng đồng.
"""

from datetime import date, datetime

import pytest

from crawlers.base.models import Source
from crawlers.macro import fx, fx_exchangerates, fx_xrates


# ---------- exchangerates (nguồn chính) ----------

def _er_row(day: str, code: str, rate: str, ohl: bool) -> str:
    # Đúng markup thật: JPY/CNY có 3 cột Open/High/Low trước Close, THB thì không.
    extra = "".join(f'<td class="erukPairOptionalColumn">{v}</td>' for v in ("1.1", "1.2", "1.0")) if ohl else ""
    return (f'<tr>\n<th scope="row"><time datetime="{day}">{day}</time></th>\n{extra}\n'
            f'<td><strong>1 USD to {code} = {rate}</strong></td>\n'
            f'<td class="text-end"><span class="erukPairPerformanceChange is-down">-0.62%</span></td>\n</tr>')


def _er_page(code: str, rows: list[tuple[str, str]], ohl: bool = True) -> str:
    body = "".join(_er_row(d, code, r, ohl) for d, r in rows)
    return f'<table class="erukPairHistoryTable"><tbody>{body}</tbody></table>'


JPY_PAGE = _er_page("JPY", [("2026-09-11", "153.5195"), ("2026-09-10", "154.4765"),
                            ("2026-09-04", "156.2510"), ("2026-09-03", "155.6598"),
                            ("2026-09-02", "158.9247")])


def test_exchangerates_parse_reads_close_column_with_ohl() -> None:
    got = fx_exchangerates.parse_history(JPY_PAGE, "JPY", date(2026, 9, 3), date(2026, 9, 13))
    assert got == [(date(2026, 9, 11), 153.5195), (date(2026, 9, 10), 154.4765),
                   (date(2026, 9, 4), 156.251), (date(2026, 9, 3), 155.6598)]


def test_exchangerates_parse_skips_weekend_rows_without_ohl() -> None:
    thb = _er_page("THB", [("2026-09-07", "32.8600"), ("2026-09-06", "32.9300"), ("2026-09-04", "32.9150")],
                   ohl=False)
    got = fx_exchangerates.parse_history(thb, "THB", date(2026, 9, 1), date(2026, 9, 13))
    assert got == [(date(2026, 9, 7), 32.86), (date(2026, 9, 4), 32.915)]  # bỏ Chủ nhật 06/09


def test_exchangerates_parse_rejects_today_other_code_and_blocked_page() -> None:
    page = _er_page("JPY", [("2026-09-14", "150.0"), ("2026-09-11", "153.5195")])
    assert fx_exchangerates.parse_history(page, "JPY", date(2026, 9, 1), date(2026, 9, 14)) == [
        (date(2026, 9, 11), 153.5195)]
    assert fx_exchangerates.parse_history(page, "CNY", date(2026, 9, 1), date(2026, 9, 14)) == []
    assert fx_exchangerates.parse_history("<title>Just a moment...</title>", "JPY",
                                          date(2026, 9, 1), date(2026, 9, 14)) == []


# ---------- x-rates (dự phòng) ----------

def _xr_row(code: str, value: str) -> str:
    # Đúng markup thật của x-rates (nháy đơn + &amp;), kèm cột nghịch đảo phải bị bỏ qua.
    return (f"<tr><td>X</td><td class='rtRates'><a href='https://www.x-rates.com/graph/?from=USD&amp;"
            f"to={code}'>{value}</a></td><td class='rtRates'><a href='https://www.x-rates.com/graph/"
            f"?from={code}&amp;to=USD'>0.1</a></td></tr>")


def _xr_page(stamp: str, rows: dict[str, str]) -> str:
    table = "".join(_xr_row(c, v) for c, v in rows.items())
    return f'<span class="ratesTimestamp">{stamp}</span>{table}<span class="ratesTimestamp">{stamp}</span>{table}'


CODES = ("CNY", "JPY", "THB")


def test_xrates_parse_snapshot_page_rounds_to_4_decimals() -> None:
    page = _xr_page("Jan 01, 2026 16:00 UTC",
                    {"EUR": "0.85", "JPY": "158.917198", "CNY": "6.719628", "THB": "33.187484"})
    assert fx_xrates.parse_snapshot(page, CODES) == {"JPY": 158.9172, "CNY": 6.7196, "THB": 33.1875}
    assert fx_xrates.parse_snapshot(page, ("JPY",)) == {"JPY": 158.9172}


def test_xrates_parse_rejects_live_or_blocked_page() -> None:
    assert fx_xrates.parse_snapshot(_xr_page("Jan 01, 2026 11:56 UTC", {"JPY": "153.5"}), CODES) == {}
    assert fx_xrates.parse_snapshot("<title>Just a moment...</title>", CODES) == {}


def _fake_fetch(pages: dict[str, str], calls: list[str]):
    def fetch(url: str, **_: object) -> str:
        day = url.rsplit("date=", 1)[1]
        calls.append(day)
        if day not in pages:
            raise RuntimeError("network down")
        return pages[day]
    return fetch


def test_xrates_close_of_day_d_comes_from_snapshot_d_plus_1(monkeypatch: pytest.MonkeyPatch) -> None:
    # Thứ 5 03/09 → trang 04/09; Thứ 6 04/09 → trang 05/09; bỏ T7/CN; Thứ 2 07/09 → trang 08/09 = hôm nay.
    pages = {"2026-09-04": _xr_page("Jan 01, 2026 16:00 UTC", {"JPY": "155.652554"}),
             "2026-09-05": _xr_page("Jan 01, 2026 16:00 UTC", {"JPY": "156.262738"})}
    calls: list[str] = []
    monkeypatch.setattr(fx_xrates, "fetch_text", _fake_fetch(pages, calls))
    recs = fx_xrates.closes(date(2026, 9, 3), date(2026, 9, 8), date(2026, 9, 8), CODES, fx._rec)
    assert [(r.as_of, r.grade, r.price) for r in recs] == [
        (date(2026, 9, 3), "USD/JPY", 155.6526), (date(2026, 9, 4), "USD/JPY", 156.2627)]
    assert calls == ["2026-09-04", "2026-09-05"]


def test_xrates_network_error_stops_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fx_xrates, "fetch_text", _fake_fetch({}, calls))
    assert fx_xrates.closes(date(2026, 9, 1), date(2026, 9, 10), date(2026, 9, 13), CODES, fx._rec) == []
    assert calls == ["2026-09-02"]  # dừng ngay lần lỗi đầu, không kéo dài lượt quét


# ---------- chọn nguồn theo từng đồng ----------

def _stub_sources(monkeypatch: pytest.MonkeyPatch, primary: dict[str, float], backup: dict[str, float]):
    asked: list[tuple[str, ...]] = []

    def exr(since, today, codes, make):
        recs = [make(c, date(2026, 9, 11), v) for c, v in primary.items() if c in codes]
        return recs, {c: "TimeoutError" for c in codes if c not in primary}

    def xr(first, last, today, codes, make):
        asked.append(codes)
        return [make(c, date(2026, 9, 11), v) for c, v in backup.items() if c in codes]

    monkeypatch.setattr(fx_exchangerates, "closes", exr)
    monkeypatch.setattr(fx_xrates, "closes", xr)
    return asked


def test_primary_complete_does_not_touch_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _stub_sources(monkeypatch, {"CNY": 6.7083, "JPY": 153.5195, "THB": 33.06}, {"JPY": 1.0})
    recs, notes = fx._asia_closes(date(2026, 9, 6), date(2026, 9, 13))
    assert sorted((r.grade, r.price) for r in recs) == [
        ("USD/CNY", 6.7083), ("USD/JPY", 153.5195), ("USD/THB", 33.06)]
    assert notes == [] and asked == []


def test_backup_only_for_missing_codes_and_noted(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = _stub_sources(monkeypatch, {"CNY": 6.7083}, {"JPY": 153.58, "CNY": 9.9})
    recs, notes = fx._asia_closes(date(2026, 9, 6), date(2026, 9, 13))
    assert asked == [("JPY", "THB")]
    assert sorted((r.grade, r.price) for r in recs) == [("USD/CNY", 6.7083), ("USD/JPY", 153.58)]
    assert notes == ["exchangerates lỗi (JPY: TimeoutError) → dùng x-rates dự phòng", "tỷ giá thiếu: THB"]


def test_exchangerates_closes_reports_reason_per_code(monkeypatch: pytest.MonkeyPatch) -> None:
    blocked = "<title>Just a moment...</title>"
    monkeypatch.setattr(fx_exchangerates, "_fetch_pages",
                        lambda codes: ({"JPY": JPY_PAGE, "THB": blocked}, {"CNY": "TimeoutError"}))
    recs, errors = fx_exchangerates.closes(date(2026, 9, 10), date(2026, 9, 13), CODES, fx._rec)
    assert [(r.grade, r.as_of) for r in recs] == [("USD/JPY", date(2026, 9, 11)), ("USD/JPY", date(2026, 9, 10))]
    assert errors == {"CNY": "TimeoutError", "THB": "không đọc được bảng"}


def test_exchangerates_closes_browser_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(codes):
        raise FileNotFoundError("firefox")
    monkeypatch.setattr(fx_exchangerates, "_fetch_pages", boom)
    assert fx_exchangerates.closes(date(2026, 9, 1), date(2026, 9, 13), ("JPY",), fx._rec) == (
        [], {"JPY": "trình duyệt: FileNotFoundError"})


def test_rec_shape() -> None:
    r = fx._rec("THB", date(2026, 9, 3), 33.1875)
    assert r.source is Source.FX
    assert r.grade == "USD/THB"
    assert r.unit == "THB per USD"
    assert r.price_type == "fx"
    assert r.as_of == date(2026, 9, 3)


# ---------- MYR (BNM): quét theo tháng, lấp lại ngày thiếu ----------

def _bnm_month_payload(*days: tuple[str, float]) -> dict:
    return {"data": {"currency_code": "USD", "rate": [{"date": d, "buying_rate": r} for d, r in days]}}


def _stub_bnm(monkeypatch: pytest.MonkeyPatch, months: dict[str, dict | None]) -> list[str]:
    """Giả lập BNM theo tháng: months['2026/9'] = payload, None = lỗi mạng. Trả về danh sách URL đã gọi."""
    calls: list[str] = []

    def fake(url: str, **_: object) -> dict:
        calls.append(url)
        key = url.split("/year/", 1)[1].split("?", 1)[0].replace("/month/", "/")
        payload = months.get(key)
        if payload is None:
            raise RuntimeError("BNM down")
        return payload

    monkeypatch.setattr(fx, "fetch_json", fake)
    return calls


def test_bnm_myr_spans_months_and_keeps_days_from_since(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_bnm(monkeypatch, {
        "2026/9": _bnm_month_payload(("2026-09-25", 4.075), ("2026-09-28", 4.082), ("2026-09-30", 4.077)),
        "2026/10": _bnm_month_payload(("2026-10-01", 4.084), ("2026-10-05", 4.085)),
    })
    recs = fx._bnm_myr(date(2026, 9, 28), date(2026, 10, 12))
    assert [(r.grade, r.as_of, r.price) for r in recs] == [
        ("USD/MYR", date(2026, 9, 28), 4.082), ("USD/MYR", date(2026, 9, 30), 4.077),
        ("USD/MYR", date(2026, 10, 1), 4.084), ("USD/MYR", date(2026, 10, 5), 4.085)]
    assert len(calls) == 2 and "/month/9?" in calls[0] and "/month/10?" in calls[1]


def test_bnm_myr_one_month_failing_keeps_the_other(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_bnm(monkeypatch, {"2026/9": None, "2026/10": _bnm_month_payload(("2026-10-06", 4.083))})
    recs = fx._bnm_myr(date(2026, 9, 20), date(2026, 10, 12))
    assert [r.as_of for r in recs] == [date(2026, 10, 6)]


def test_bnm_myr_year_rollover_and_empty_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_bnm(monkeypatch, {})
    assert fx._bnm_myr(date(2026, 12, 20), date(2027, 1, 5)) == []
    assert [c.split("/year/", 1)[1].split("?", 1)[0] for c in calls] == ["2026/month/12", "2027/month/1"]


def test_crawl_refills_myr_days_missed_by_earlier_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    # Hồi quy sự cố 28/09–06/10/2026: BNM lỗi nhiều ngày rồi trở lại → lượt quét đầu tiên sau đó
    # phải trả lại CẢ các ngày đã lỡ, không chỉ ngày mới nhất.
    _stub_bnm(monkeypatch, {"2026/10": _bnm_month_payload(
        ("2026-10-01", 4.084), ("2026-10-02", 4.083), ("2026-10-05", 4.085), ("2026-10-06", 4.083))})
    monkeypatch.setattr(fx, "_asia_closes", lambda since, today: ([], []))
    monkeypatch.setattr(fx, "_vnd_records", lambda day=None: [])

    class _FixedNow:
        @staticmethod
        def now(tz=None):  # noqa: ANN001
            return datetime(2026, 10, 7, 0, 30, tzinfo=tz)

    monkeypatch.setattr(fx, "datetime", _FixedNow)
    res = fx.crawl()
    myr = [r for r in res.records if r.grade == "USD/MYR"]
    assert [r.as_of.day for r in myr] == [1, 2, 5, 6]
    assert "MYR (BNM) lỗi" not in (res.note or "")
