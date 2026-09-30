"""Test dựng câu OPENQUERY cho Historian (thuần chuỗi, không cần SQL Server)."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services import scada_historian_sql as hsql

TAGS = ["PM_EnergyReal0", "PM_EnergyReal1", "PM_EnergyReal2", "PM_EnergyReal3",
        "Water_TotalVolume"]


def test_range_query_past_period_uses_fixed_upper_bound() -> None:
    sql = hsql.range_query("INSQL", TAGS, datetime(2026, 9, 1), datetime(2026, 10, 1))
    assert sql == (
        "SELECT * FROM OPENQUERY(INSQL, 'SELECT DateTime, [PM_EnergyReal0], [PM_EnergyReal1], "
        "[PM_EnergyReal2], [PM_EnergyReal3], [Water_TotalVolume] FROM WideHistory"
        " WHERE wwRetrievalMode = ''Cyclic'' AND wwResolution = 3600000"
        " AND wwQualityRule = ''Extended'' AND wwVersion = ''Latest''"
        " AND DateTime >= ''2026-09-01 00:00:00'' AND DateTime <= ''2026-10-01 00:00:00''')"
    )


def test_range_query_including_today_ends_at_scada_clock() -> None:
    sql = hsql.range_query("INSQL", ["Water_TotalVolume"], datetime(2026, 9, 1), None)
    assert sql.endswith("AND DateTime >= ''2026-09-01 00:00:00'' AND DateTime <= GetDate()')")
    assert "wwResolution = 3600000" in sql


def test_latest_query_uses_minute_resolution_last_10_minutes() -> None:
    sql = hsql.latest_query("INSQL", ["Water_TotalVolume"])
    assert "wwResolution = 60000" in sql
    assert "DateTime >= DateAdd(mi,-10,GetDate()) AND DateTime <= GetDate()" in sql
    assert sql.startswith("SELECT * FROM OPENQUERY(INSQL, 'SELECT DateTime, [Water_TotalVolume]")


def test_inner_quotes_are_doubled_and_balanced() -> None:
    """Chuỗi trong OPENQUERY chỉ có nháy đơn nhân đôi — bỏ 2 nháy bao ngoài phải còn số chẵn."""
    sql = hsql.range_query("INSQL", TAGS, datetime(2026, 9, 1), None)
    inner = sql[sql.index("'") + 1: sql.rindex("'")]
    assert "''" in inner and inner.replace("''", "").count("'") == 0


@pytest.mark.parametrize("bad", [
    "Tag]; DROP TABLE x--", "Tag'", "Tag Name", "Tag;", "", "a" * 129, "Tag[1]", "Tag\n",
    "Tag,Other", "Tag/*",
])
def test_bad_tag_rejected(bad: str) -> None:
    assert not hsql.valid_tag(bad)
    with pytest.raises(ValueError):
        hsql.range_query("INSQL", [bad], datetime(2026, 9, 1), None)
    with pytest.raises(ValueError):
        hsql.latest_query("INSQL", ["Ok_Tag", bad])


@pytest.mark.parametrize("good", ["PM_EnergyReal0", "Line1.Water$Total", "A-B#1", "x" * 128])
def test_good_tag_accepted(good: str) -> None:
    assert hsql.valid_tag(good)
    assert f"[{good}]" in hsql.latest_query("INSQL", [good])


@pytest.mark.parametrize("bad", ["INSQL]", "IN SQL", "INSQL;--", "INSQL'", "IN.SQL", "IN-SQL", ""])
def test_bad_linked_server_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        hsql.latest_query(bad, ["Water_TotalVolume"])


def test_no_tags_rejected() -> None:
    with pytest.raises(ValueError):
        hsql.latest_query("INSQL", [])


def test_start_must_be_datetime_not_user_string() -> None:
    with pytest.raises(ValueError):
        hsql.range_query("INSQL", ["T"], "2026-09-01' OR 1=1 --", None)  # type: ignore[arg-type]


def test_factory_tags_order_skip_blank_dedupe_case_insensitive() -> None:
    f = {"energy_tags": ["R0", "R1", "R2", "R3"], "water_tag": "r1", "bales_tag": None}
    assert hsql.factory_tags(f) == ["R0", "R1", "R2", "R3"]
    f = {"energy_tags": [], "water_tag": "W", "bales_tag": "B"}
    assert hsql.factory_tags(f) == ["W", "B"]
    assert hsql.factory_tags({"energy_tags": [], "water_tag": "", "bales_tag": None}) == []
