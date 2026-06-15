"""Test offline parser ANRPC bằng fixture tĩnh (không gọi mạng)."""

from datetime import date
from pathlib import Path

from crawlers.exchanges import anrpc

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "anrpc_sample.html"


def test_parse_picks_latest_date_column() -> None:
    records = anrpc.parse(FIXTURE.read_text(encoding="utf-8"))
    by_grade = {r.grade: r for r in records}

    assert len(records) == 4
    # lấy đúng cột ngày MỚI NHẤT (15/06 chứ không phải 12/06)
    assert by_grade["SMR20"].price == 2.33
    assert by_grade["STR20"].price == 2.54
    assert by_grade["SIR20"].price == 2.26
    assert by_grade["RSS3"].price == 3.16
    assert by_grade["SMR20"].as_of == date(2026, 6, 15)
    assert by_grade["SMR20"].unit == "US$/kg"
    assert by_grade["SMR20"].price_type == "physical"
