"""Test offline parser TOCOM/JPX settlement CSV (encoding cp932)."""

from crawlers.exchanges import tocom

_CSV = (
    "note line 1\n"
    "note line 2\n"
    "Issue Code,Issue Name,Put/Call,Contract Month,Strike,Settlement Price,"
    "Theo,Under,Vol,Rate,Days until Maturity,Underlying Name\n"
    "1,FUT,,202606,,424.9,,,,,9,Rubber (RSS3)\n"
    "2,FUT,,202611,,435.9,,,,,162,Rubber (RSS3)\n"
    "3,FUT,,202607,,362,,,,,15,Rubber (TSR20)\n"
    "9,FUT_225,,202609,,69400,,,,,88,Nikkei 225\n"
)


def test_parse_filters_rubber_only() -> None:
    parsed = tocom._parse(_CSV.encode("cp932"))
    assert len(parsed["RSS3"]) == 2
    assert len(parsed["TSR20"]) == 1
    assert parsed["RSS3"][0]["settle"] == 424.9


def test_front_picks_nearest_live_contract() -> None:
    parsed = tocom._parse(_CSV.encode("cp932"))
    front = tocom._front(parsed["RSS3"])
    assert front["contract"] == "202606"  # days 9 < 162
