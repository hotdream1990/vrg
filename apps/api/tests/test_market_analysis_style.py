"""Test khối 'ví dụ văn phong' của AI mục IV: ưu tiên các bản tin ĐÃ BIÊN TẬP gần đây
làm ví dụ tông giọng, fallback ví dụ tĩnh; + repo lấy market_analysis các ngày trước."""

from __future__ import annotations

from app.core.db import db_healthy
from app.services import draft_repo
from app.services import market_analysis as ma


def test_fmt_dmy() -> None:
    assert ma._fmt_dmy("2026-07-15") == "15/07/2026"


def test_style_reference_fallback_when_no_samples() -> None:
    # report_date=None ⇒ không tra DB ⇒ dùng ví dụ tĩnh _STYLE.
    ref = ma._style_reference(None)
    assert ma._STYLE in ref and "VÍ DỤ VĂN PHONG" in ref


def test_style_reference_uses_recent_edited(monkeypatch) -> None:
    monkeypatch.setattr(draft_repo, "recent_market_analysis", lambda before, limit=5: [
        {"report_date": "2026-07-15", "paragraphs": ["Đoạn mới nhất."]},
        {"report_date": "2026-07-14", "paragraphs": ["Đoạn cũ hơn."]},
    ])
    ref = ma._style_reference("2026-07-16")
    assert "Bản tin 15/07/2026" in ref and "Đoạn mới nhất." in ref
    assert "Bản tin 14/07/2026" in ref
    assert ref.index("15/07/2026") < ref.index("14/07/2026")  # sắp mới → cũ
    assert "KHÔNG dùng lại số liệu" in ref                     # chặn bịa số của ngày cũ
    assert ma._STYLE not in ref                                # đã thay ví dụ tĩnh


def test_style_reference_char_cap(monkeypatch) -> None:
    big = ["x" * 1000 for _ in range(5)]  # mỗi ngày ~5.000 ký tự
    monkeypatch.setattr(draft_repo, "recent_market_analysis", lambda before, limit=5: [
        {"report_date": f"2026-07-0{i}", "paragraphs": big} for i in range(1, 6)
    ])
    ref = ma._style_reference("2026-07-16")
    assert ref.count("— Bản tin") < 5  # trần độ dài đã bỏ bớt ngày cũ


def test_recent_market_analysis_filters_and_orders() -> None:
    if not db_healthy():
        return
    dates = ["2019-01-01", "2019-01-02", "2019-01-03"]
    try:
        draft_repo.save_draft(dates[0], {"market_analysis": ["a1", "a2"]})
        draft_repo.save_draft(dates[1], {"market_analysis": []})       # rỗng → bị bỏ
        draft_repo.save_draft(dates[2], {"market_analysis": ["c1"]})
        got = draft_repo.recent_market_analysis("2019-02-01", limit=5)
        picked = [g["report_date"] for g in got if g["report_date"] in dates]
        assert picked == ["2019-01-03", "2019-01-01"]                  # mới→cũ, bỏ ngày rỗng
        before = draft_repo.recent_market_analysis("2019-01-03", limit=5)
        assert "2019-01-03" not in [g["report_date"] for g in before]  # loại chính nó + ngày sau
    finally:
        for d in dates:
            draft_repo.delete_draft(d)
