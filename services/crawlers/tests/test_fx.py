"""Test offline cho FX CNY/JPY/THB (x-rates.com) — không cần mạng.

Kiểm parser trang lịch sử (chỉ nhận trang ĐÃ CHỐT, bỏ trang live) + quy tắc ngày
(Close ngày D = ảnh chụp ngày D+1, bỏ cuối tuần, không lấy ảnh chụp của hôm nay).
"""

from datetime import date

import pytest

from crawlers.base.models import Source
from crawlers.macro import fx


def _row(code: str, value: str) -> str:
    # Đúng markup thật của x-rates (nháy đơn + &amp;), kèm cột nghịch đảo phải bị bỏ qua.
    return (f"<tr><td>X</td><td class='rtRates'><a href='https://www.x-rates.com/graph/?from=USD&amp;"
            f"to={code}'>{value}</a></td><td class='rtRates'><a href='https://www.x-rates.com/graph/"
            f"?from={code}&amp;to=USD'>0.1</a></td></tr>")


def _page(stamp: str, rows: dict[str, str]) -> str:
    table = "".join(_row(c, v) for c, v in rows.items())
    return f'<span class="ratesTimestamp">{stamp}</span>{table}<span class="ratesTimestamp">{stamp}</span>{table}'


SNAPSHOT = _page("Jan 01, 2026 16:00 UTC",
                 {"EUR": "0.85", "JPY": "158.917198", "CNY": "6.719628", "THB": "33.187484"})


def test_parse_snapshot_page_rounds_to_4_decimals() -> None:
    assert fx._parse_xrates(SNAPSHOT) == {"JPY": 158.9172, "CNY": 6.7196, "THB": 33.1875}


def test_parse_rejects_live_page() -> None:
    # Trang của ngày chưa chốt hiện tỷ giá LIVE, nhãn giờ = giờ hiện tại → không được nhận.
    live = _page("Jan 01, 2026 11:56 UTC", {"JPY": "153.567403"})
    assert fx._parse_xrates(live) == {}


def test_parse_rejects_blocked_or_changed_page() -> None:
    assert fx._parse_xrates("<title>Just a moment...</title>") == {}
    assert fx._parse_xrates('<span class="ratesTimestamp">Jan 01, 2026 16:00 UTC</span>') == {}


def _fake_fetch(pages: dict[str, str], calls: list[str]):
    def fetch(url: str, **_: object) -> str:
        day = url.rsplit("date=", 1)[1]
        calls.append(day)
        if day not in pages:
            raise RuntimeError("network down")
        return pages[day]
    return fetch


def test_close_of_day_d_comes_from_snapshot_d_plus_1(monkeypatch: pytest.MonkeyPatch) -> None:
    # Thứ 5 03/09 → trang 04/09; Thứ 6 04/09 → trang 05/09; bỏ T7 05/09 + CN 06/09;
    # Thứ 2 07/09 → trang 08/09 = hôm nay (chưa chốt) → không gọi.
    pages = {"2026-09-04": _page("Jan 01, 2026 16:00 UTC", {"JPY": "155.652554"}),
             "2026-09-05": _page("Jan 01, 2026 16:00 UTC", {"JPY": "156.262738"})}
    calls: list[str] = []
    monkeypatch.setattr(fx, "fetch_text", _fake_fetch(pages, calls))
    recs = fx._xrates_closes(date(2026, 9, 3), date(2026, 9, 8), today=date(2026, 9, 8))
    assert [(r.as_of, r.grade, r.price) for r in recs] == [
        (date(2026, 9, 3), "USD/JPY", 155.6526),
        (date(2026, 9, 4), "USD/JPY", 156.2627),
    ]
    assert calls == ["2026-09-04", "2026-09-05"]


def test_network_error_stops_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(fx, "fetch_text", _fake_fetch({}, calls))
    assert fx._xrates_closes(date(2026, 9, 1), date(2026, 9, 10), today=date(2026, 9, 13)) == []
    assert calls == ["2026-09-02"]  # dừng ngay lần lỗi đầu, không kéo dài lượt quét


def test_rec_shape() -> None:
    r = fx._rec("THB", date(2026, 9, 3), 33.1875)
    assert r.source is Source.FX
    assert r.grade == "USD/THB"
    assert r.unit == "THB per USD"
    assert r.price_type == "fx"
    assert r.as_of == date(2026, 9, 3)
