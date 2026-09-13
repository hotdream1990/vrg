"""Soát văn AI Báo cáo tuần: dò chữ tiếng Anh · viết lại dòng lỗi nhưng giữ nguyên số · lọc III.2 lạc đề."""

from __future__ import annotations

from app.services import weekly_ai, weekly_ai_polish as polish
from app.services.weekly_number_check import english_words


def test_english_words_detects_leftovers_but_not_codes() -> None:
    lines = ["Triển vọng ngắn hạn vẫn firm nhưng biến động", "ANRPC, SHFE, RSS3, WTI, DXY, PMI, FOB Bangkok"]
    assert english_words(lines) == ["firm"]
    assert english_words(["Sản lượng tăng 2,1% y-o-y"]) == ["y-o-y"]


def test_accept_keeps_original_when_numbers_or_lead_change() -> None:
    orig = "> Theo ANRPC, triển vọng vẫn firm, thâm hụt 77 nghìn tấn."
    assert polish.accept(orig, "> Theo ANRPC, triển vọng vẫn vững, thâm hụt 77 nghìn tấn.") == \
        "> Theo ANRPC, triển vọng vẫn vững, thâm hụt 77 nghìn tấn."
    assert polish.accept(orig, "> Theo ANRPC, triển vọng vẫn vững, thâm hụt 70 nghìn tấn.") == orig  # đổi số
    assert polish.accept(orig, "Theo ANRPC, triển vọng vẫn vững, thâm hụt 77 nghìn tấn.") == orig    # mất '>'
    assert polish.accept(orig, "> Theo ANRPC, triển vọng vẫn firm, thâm hụt 77 nghìn tấn.") == orig  # còn lỗi
    assert polish.accept(orig, "") == orig


def test_polish_sections_rewrites_only_flagged_lines(monkeypatch) -> None:
    calls: list[str] = []

    def fake_complete(system, user, max_tokens=0):
        calls.append(user)
        return "[0] - Kìm hãm đà tăng: áp lực chốt lời chưa được hấp thụ hết; đồng yên mạnh lên"

    monkeypatch.setattr(polish.llm, "complete", fake_complete)
    sections = {"forecast": ["Thị trường dự kiến giằng co.",
                             "- Kìm hãm đà tăng: áp lực chốt lời chưa hoàn toàn được hấp thụ; đồng yên mạnh lên"]}
    out = polish.polish_sections(sections)
    assert out["forecast"][0] == "Thị trường dự kiến giằng co."
    assert "hoàn toàn" not in out["forecast"][1] and out["forecast"][1].startswith("- Kìm hãm")
    assert len(calls) == 1 and "[0]" in calls[0] and "giằng co" not in calls[0]


def test_polish_sections_no_call_when_clean(monkeypatch) -> None:
    monkeypatch.setattr(polish.llm, "complete", lambda *a, **k: (_ for _ in ()).throw(AssertionError("gọi AI")))
    clean = {"conclusion": ["Các đơn vị cần duy trì trạng thái thận trọng."]}
    assert polish.polish_sections(clean) == clean


def test_polish_llm_error_keeps_text(monkeypatch) -> None:
    monkeypatch.setattr(polish.llm, "complete", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    data = {"x": ["Triển vọng vẫn firm."]}
    assert polish.polish_sections(data) == data


def test_physical_notes_without_prices_keep_only_physical_line() -> None:
    rep = {"physical_range_stats": []}
    lines = ["> Trung Quốc chiếm khoảng 45,8% nhu cầu toàn cầu.",
             "Theo ANRPC, giá giao ngay bình quân tháng 8/2026: STR20 FOB Bangkok 238,6 US cent/kg (+1,4%).",
             "> Thái Lan chiếm 31,9% nguồn cung."]
    assert weekly_ai._finalize("physical_notes", lines, rep) == [lines[1]]
    assert weekly_ai._finalize("physical_notes", ["> Trung Quốc chiếm 45,8% nhu cầu."], rep) == []
