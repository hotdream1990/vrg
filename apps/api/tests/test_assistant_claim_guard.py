"""Hàng rào 'Trợ lý nói đã chỉnh phương án mà không chỉnh' (assistant_claim_guard) — nhận diện câu +
vòng chat với LLM giả: lần 1 báo sai ⇒ bị bắt làm lại; báo sai 2 lần ⇒ câu trả lời kèm đính chính."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.core.db import db_healthy
from app.services import assistant_claim_guard as guard
from app.services import assistant_service, floor_proposal_ops
from tests import floor_proposal_env as env

SVR10 = "SVR 10 / CSR 10"


@pytest.mark.parametrize("question,answer,changed,expected", [
    ("Thôi bỏ lần vừa rồi", "Đã hoàn tác lần chỉnh vừa rồi cho nhóm RSS trong bản nháp.", False, True),
    ("Có mức đề xuất thì đưa luôn vào bảng phương án", "Em cũng đã đưa mức này vào bảng phương án nháp.", False, True),
    ("Tăng lên tí xíu", "Đã chỉnh bản nháp: FOB 2.340 → 2.345 USD/tấn.", True, False),     # công cụ đã chạy
    ("Nên tăng hay giảm giá sàn?", "SHFE đã tăng 8% so với lần trước, mô hình đề xuất GIỮ.", False, False),
    ("Giá sàn hôm nay bao nhiêu?", "Phương án đã được lập ở lượt trước.", False, False),       # không phải yêu cầu chỉnh
    ("Đưa về như mô hình đi", "Em chưa đổi gì, chế độ Chỉ tra số không cho dùng mức mô hình.", False, False),
])
def test_false_claim_detection(question: str, answer: str, changed: bool, expected: bool) -> None:
    assert guard.false_claim(question, answer, changed) is expected


@pytest.mark.parametrize("question,expected", [
    ("Thôi bỏ lần vừa rồi", True),
    ("Hoàn tác giúp anh", True),
    ("Có mức đề xuất thì đưa luôn vào bảng phương án", True),
    ("Lập phương án giá sàn hôm nay giúp tôi", True),
    ("Tăng lên tí xíu giúp anh", True),
    ("Giảm SVR 20 một chút", True),
    ("Giải thích một chút về mô hình", False),          # không phải yêu cầu chỉnh bảng
    ("Nên tăng hay giảm giá sàn lúc này?", False),
    ("Giá sàn hôm nay bao nhiêu?", False),
])
def test_explicit_requests_are_retried_even_without_a_false_claim(question: str, expected: bool) -> None:
    assert guard.needs_retry(question, "Mô hình đề xuất GIỮ.", changed=False) is expected
    assert guard.needs_retry(question, "Đã chỉnh bản nháp.", changed=True) is False   # đã làm thật


class _ScriptedLLM:
    """LLM giả chạy theo kịch bản: mỗi phần tử là ('say', text) hoặc ('tool', name, args)."""

    def __init__(self, script: list[tuple]) -> None:
        self.script, self.calls = list(script), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw["messages"])
        step = self.script.pop(0)
        if step[0] == "tool":
            call = SimpleNamespace(id=f"c{len(self.calls)}", function=SimpleNamespace(
                name=step[1], arguments=json.dumps(step[2])))
            msg = SimpleNamespace(tool_calls=[call], content="")
        else:
            msg = SimpleNamespace(tool_calls=None, content=step[1])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _use(monkeypatch, llm: _ScriptedLLM) -> None:
    monkeypatch.setattr(assistant_service.llm, "openai_client", lambda: (llm, "fake"))
    real = assistant_service.config_repo.get_value
    monkeypatch.setattr(assistant_service.config_repo, "get_value",
                        lambda k, d=None: "openai" if k == "LLM_PROVIDER" else ("" if k == "ASSISTANT_PACKS" else real(k, d)))


@pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
def test_false_claim_is_retried_then_corrected(monkeypatch) -> None:
    env.seed()
    try:
        p = env.proposal()
        undo_ready, _, _ = floor_proposal_ops.apply(p, [{"grades": [SVR10], "op": "step", "value": 1}])
        msgs = [{"role": "user", "content": "Thôi bỏ lần vừa rồi"}]
        # Lần 1 báo sai → bị bắt làm lại → lần 2 gọi công cụ thật → trả lời đúng.
        llm = _ScriptedLLM([("say", "Đã hoàn tác lần chỉnh vừa rồi trong bản nháp."),
                            ("tool", "adjust_floor_proposal", {"changes": [{"op": "undo"}]}),
                            ("say", "Đã hoàn tác trong bản nháp: SVR 10 / CSR 10 về FOB 2.085 USD/tấn.")])
        _use(monkeypatch, llm)
        out = assistant_service.chat(msgs, None, None, "model", None, None, undo_ready)
        assert out["proposal"] is not None and out["proposal"]["log"] == []
        assert "chưa thay đổi" not in out["answer"]
        assert any(m["role"] == "system" and "KIỂM TRA TỰ ĐỘNG" in m["content"] for m in llm.calls[1])
        # Báo sai 2 lần liền → vẫn trả lời nhưng kèm đính chính, phương án không đổi.
        llm2 = _ScriptedLLM([("say", "Đã hoàn tác trong bản nháp."), ("say", "Em đã bỏ lần chỉnh đó khỏi phương án.")])
        _use(monkeypatch, llm2)
        out2 = assistant_service.chat(msgs, None, None, "model", None, None, undo_ready)
        assert out2["proposal"] is None and "chưa thay đổi" in out2["answer"]
    finally:
        env.clear()
