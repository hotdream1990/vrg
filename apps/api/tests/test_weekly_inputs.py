"""Test đầu vào Báo cáo tuần: Yahoo JSON · tin vietnambiz · trích chữ DOCX · đính kèm (DB dev, tự dọn)."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.services import user_repo, weekly_attachment_service as att_svc, weekly_news
from app.services.weekly_attachment_text import extract_docx, guess_kind, normalize_text
from app.services.weekly_market_feed import parse_chart, summarize_closes
from app.services.weekly_period import period

# ── Yahoo Finance ──
_NY = -14400  # EDT


def _ts(iso: str) -> int:  # 00:00 giờ New York của ngày giao dịch = 04:00 UTC
    from datetime import datetime, timezone
    d = date.fromisoformat(iso)
    return int(datetime(d.year, d.month, d.day, 4, tzinfo=timezone.utc).timestamp())


def _chart(days: list[str], closes: list[float | None]) -> dict:
    return {"chart": {"error": None, "result": [{
        "meta": {"symbol": "DX-Y.NYB", "gmtoffset": _NY},
        "timestamp": [_ts(d) for d in days],
        "indicators": {"quote": [{"close": closes}]}}]}}


def test_parse_chart_uses_exchange_local_date_and_skips_missing_close() -> None:
    rows = parse_chart(_chart(["2026-08-24", "2026-08-25", "2026-08-26"], [99.0, None, 99.17]))
    assert rows == [("2026-08-24", 99.0), ("2026-08-26", 99.17)]
    with pytest.raises(ValueError, match="No data found"):
        parse_chart({"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}})


def test_summarize_closes_weekly_average_changes_and_span_high_low() -> None:
    weeks = period("2026-08-24", 2)["weeks"]  # [T34 mốc, T35, T36]
    closes = [("2026-08-17", 100.0), ("2026-08-21", 102.0),                     # T34: TB 101 (cao nhưng ngoài kỳ)
              ("2026-08-24", 99.0), ("2026-08-26", 98.0),                        # T35: TB 98.5
              ("2026-09-01", 99.5), ("2026-09-04", 97.25)]                       # T36: TB 98.375
    s = summarize_closes(closes, weeks)
    assert s["values"] == [101.0, 98.5, 98.38]
    assert s["last_closes"] == [102.0, 98.0, 97.25]
    assert s["changes"] == [-2.5, -0.12] and s["changes_pct"] == [-2.48, -0.12]  # +/- tính trên số TB đã làm tròn (khớp số hiển thị)
    assert s["high"] == {"value": 99.5, "date": "01/09"} and s["low"] == {"value": 97.25, "date": "04/09"}
    gap = summarize_closes([("2026-08-24", 99.0)], weeks)  # tuần không có phiên → None, không bù ngày khác
    assert gap["values"] == [None, 99.0, None] and gap["changes"] == [None, None]


# ── vietnambiz ──
_ART = """<html><head><title>Giá cao su hôm nay 29/8: Nhật Bản giảm theo giá dầu</title>
<meta property="og:title" content="Giá cao su hôm nay 29/8: Nhật Bản giảm theo giá dầu &amp; USD" />
<meta property="article:published_time" content="2026-08-29T07:55:00" />
<script type="application/ld+json">{"datePublished":"2026-08-29T07:55:05+07:00"}</script>
</head><body>Menu Chia sẻ Giá cao su kỳ hạn tháng 12 tại OSE giảm.</body></html>"""


def test_parse_vietnambiz_article_meta_and_links() -> None:
    assert weekly_news.parse_published(_ART) == "2026-08-29T07:55:00"
    assert weekly_news.parse_published('{"datePublished":"2026-09-01T08:00:00+07:00"}') == "2026-09-01T08:00:00+07:00"
    assert weekly_news.parse_published("<html></html>") is None
    assert weekly_news.parse_title(_ART) == "Giá cao su hôm nay 29/8: Nhật Bản giảm theo giá dầu & USD"
    page = ('<a href="/gia-cao-su-hom-nay-298-a-2026828214815239.htm">x</a>'
            '<a href="/gia-cao-su-hom-nay-298-a-2026828214815239.htm">dup</a><a href="/khac-1.htm">y</a>')
    assert weekly_news.article_links(page, "https://vietnambiz.vn/gia-cao-su.html") == [
        "https://vietnambiz.vn/gia-cao-su-hom-nay-298-a-2026828214815239.htm"]
    assert weekly_news.page_url("https://vietnambiz.vn/gia-cao-su.html", 2) == \
        "https://vietnambiz.vn/gia-cao-su/trang-2.html"


def test_fetch_period_articles_filters_by_published_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Luồng phân trang/lọc ngày chạy trên HTML dựng sẵn (bản chạy mạng thật kiểm riêng)."""
    pub = {"a1": "2026-09-05T07:00:00", "a2": "2026-08-25T07:00:00", "a3": "2026-09-07T07:00:00",
           "b1": "2026-08-24T07:00:00", "b2": "2026-08-21T07:00:00", "c1": "2026-08-10T07:00:00"}
    pages = {"https://vietnambiz.vn/gia-cao-su.html": ["a1", "a2", "a3"],
             "https://vietnambiz.vn/gia-cao-su/trang-2.html": ["b1", "b2"],
             "https://vietnambiz.vn/gia-cao-su/trang-3.html": ["c1"]}
    calls: list[str] = []

    def fake_get(url: str) -> str:
        calls.append(url)
        if url in pages:
            return "".join(f'<a href="/gia-cao-su-hom-nay-{k}.htm">' for k in pages[url])
        key = url.rsplit("gia-cao-su-hom-nay-", 1)[1][:-4]
        return (f'<meta property="og:title" content="Bài {key}" />'
                f'<meta property="article:published_time" content="{pub[key]}" /> Chia sẻ nội dung {key}')

    monkeypatch.setattr(weekly_news, "_get", fake_get)
    monkeypatch.setattr(weekly_news, "_page_cache", {})
    monkeypatch.setattr(weekly_news, "_article_cache", {})
    got = weekly_news.fetch_period_articles("https://vietnambiz.vn/gia-cao-su.html",
                                            date(2026, 8, 24), date(2026, 9, 4))
    assert [(a["published"], a["title"]) for a in got] == [
        ("2026-08-24", "Bài b1"), ("2026-08-25", "Bài a2"), ("2026-09-05", "Bài a1")]
    assert "https://vietnambiz.vn/gia-cao-su/trang-3.html" in calls  # trang 2 còn bài trong kỳ → đọc tiếp
    assert weekly_news._spread(list(range(10)), 4) == [0, 3, 6, 9]


# ── Trích chữ ──
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx_bytes() -> bytes:
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><w:document {_W}><w:body>'
           '<w:p><w:r><w:t>ANRPC   Monthly</w:t></w:r><w:r><w:t xml:space="preserve"> Report</w:t></w:r></w:p>'
           '<w:p/><w:p/><w:p/>'
           '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Production</w:t></w:r></w:p></w:tc>'
           '<w:tc><w:p><w:r><w:t>+2.1%</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
           '<w:p><w:r><w:t>Short-term</w:t><w:tab/><w:t>Outlook</w:t></w:r></w:p></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


def test_extract_docx_paragraphs_and_table_cells(tmp_path: Path) -> None:
    p = tmp_path / "bao-cao.docx"
    p.write_bytes(_docx_bytes())
    assert extract_docx(p) == "ANRPC Monthly Report\n\nProduction | +2.1%\nShort-term Outlook"
    bad = tmp_path / "hong.docx"
    bad.write_bytes(b"not a zip")
    assert extract_docx(bad) == ""
    assert normalize_text("a\x00b  \t c\n\n\n\nd") == "ab c\n\nd"
    assert guess_kind("ANRPC Biweekly.pdf", "") == "anrpc" and guess_kind("x.pdf", "tin khác") == "other"


# ── Đính kèm qua API ──
needs_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
_WK = "1999-01-04"  # tuần giả (Thứ 2) — không đụng báo cáo thật


@needs_db
def test_attachment_api_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import app

    monkeypatch.setenv("VRG_DATA_DIR", str(tmp_path))
    client = TestClient(app)
    user_repo.seed_admin()
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    base = f"/api/weekly-reports/{_WK}/attachments"
    att_svc.delete_all(_WK)
    try:
        txt = client.post(base, files={"file": ("a.txt", b"hello", "text/plain")}, headers=h)
        assert txt.status_code == 400
        up = client.post(base, files={"file": ("tong-hop.docx", _docx_bytes(), "application/octet-stream")},
                         headers=h)
        assert up.status_code == 200, up.text
        att = up.json()
        assert att["kind"] == "anrpc" and att["pages"] is None and att["text_chars"] > 0 and "file" not in att
        aid = att["id"]
        assert [a["id"] for a in client.get(base, headers=h).json()] == [aid]
        assert "Production | +2.1%" in client.get(f"{base}/{aid}/text", headers=h).json()["text"]
        assert client.get(f"{base}/{aid}/file", headers=h).content == _docx_bytes()
        # IDOR: id của tuần này không mở được qua tuần khác
        assert client.get(f"/api/weekly-reports/2026-08-24/attachments/{aid}/text", headers=h).status_code == 404
        p = client.patch(f"{base}/{aid}", json={"kind": "other", "summary": "Cung dư 2,1%"}, headers=h)
        assert p.status_code == 200 and p.json()["summary"] == "Cung dư 2,1%" and p.json()["kind"] == "other"
        assert client.patch(f"{base}/{aid}", json={"kind": "xyz"}, headers=h).status_code == 400
        docs = att_svc.context_documents(_WK, max_chars=5)
        assert docs == [{"id": aid, "filename": "tong-hop.docx", "kind": "other", "used": "summary",
                         "content": "Cung "}]
        assert client.delete(f"{base}/{aid}", headers=h).status_code == 200
        assert client.delete(f"{base}/{aid}", headers=h).status_code == 404
        assert not any((tmp_path / "weekly-reports" / "attachments").iterdir())  # file đã xoá theo bản ghi
        assert client.get("/api/weekly-reports/abc/attachments", headers=h).status_code == 400
    finally:
        att_svc.delete_all(_WK)
