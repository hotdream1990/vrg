"""ANRPC Daily Price — giá physical (US$/kg) các grade chuẩn: SMR20, STR20, SIR20, RSS3.

Nguồn: https://www.anrpc.org/anrpc-daily-price (spec: lay-gia-cac-san.md).
Bảng có nhiều cột ngày → tự chọn cột ngày MỚI NHẤT.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from html.parser import HTMLParser

from ..base.fetcher import fetch_text
from ..base.models import CrawlResult, PriceRecord, Source, Status

URL = "https://www.anrpc.org/anrpc-daily-price"

# nhãn trên web (chuẩn hóa) -> (mã grade, xuất xứ)
_GRADES: dict[str, tuple[str, str]] = {
    "BKK (RSS3)": ("RSS3", "Bangkok"),
    "SMR 20": ("SMR20", "Malaysia"),
    "STR 20": ("STR20", "Thailand"),
    "SIR 20": ("SIR20", "Indonesia"),
    "LATEX": ("LATEX", "—"),
}


class _TableExtractor(HTMLParser):
    """Trích mọi <table> thành list[rows][cells] bằng parser built-in (không cần lxml)."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell = False
        self._buf = ""

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "table":
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._buf = True, ""

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", self._buf).strip())
            self._cell = False
        elif tag == "tr" and self._row is not None and self._rows is not None:
            self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._rows is not None:
            self.tables.append(self._rows)
            self._rows = None

    def handle_data(self, data: str) -> None:
        if self._cell:
            self._buf += data


def _parse_date(s: str) -> date | None:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _match_grade(label: str) -> tuple[str, str] | None:
    norm = re.sub(r"\s+", " ", label).strip().upper()
    for key, val in _GRADES.items():
        if key.upper() in norm:
            return val
    return None


def parse(html: str) -> list[PriceRecord]:
    """Tìm bảng có cột ngày, lấy cột ngày mới nhất, map grade → PriceRecord."""
    extractor = _TableExtractor()
    extractor.feed(html)
    for rows in extractor.tables:
        if not rows:
            continue
        date_cols = {i: _parse_date(c) for i, c in enumerate(rows[0])}
        date_cols = {i: d for i, d in date_cols.items() if d}
        if not date_cols:
            continue
        latest_i = max(date_cols, key=lambda i: date_cols[i])
        as_of = date_cols[latest_i]
        records: list[PriceRecord] = []
        for row in rows[1:]:
            if len(row) <= latest_i:
                continue
            match = _match_grade(row[0])
            if not match:
                continue
            nums = re.findall(r"-?\d+\.?\d*", row[latest_i].replace(",", ""))
            if not nums:
                continue
            code, origin = match
            records.append(
                PriceRecord(
                    source=Source.ANRPC,
                    grade=code,
                    price=float(nums[0]),
                    currency="USD",
                    unit="US$/kg",
                    price_type="physical",
                    as_of=as_of,
                    extra={"label": row[0], "origin": origin},
                )
            )
        if records:
            return records
    return []


def crawl() -> CrawlResult:
    try:
        records = parse(fetch_text(URL))
        if records:
            return CrawlResult(source=Source.ANRPC, status=Status.OK, records=records)
        return CrawlResult(source=Source.ANRPC, status=Status.EMPTY, note="Không thấy bảng giá")
    except Exception as exc:  # noqa: BLE001
        return CrawlResult(source=Source.ANRPC, status=Status.ERROR, note=str(exc))
