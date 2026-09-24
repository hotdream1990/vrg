"""Nghiệp vụ bản nháp tờ trình giá sàn: dựng từ phương án, sửa, xem trước (HTML).

Ghép 3 phần có sẵn: phương án [floor_proposal] (khối 3) + phần thị trường [to_trinh.build_market]
(khối 1–2, lần thứ) + mẫu in [to_trinh_html.render]. Lưu trữ ở [floor_draft_repo].
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core import edit_window

from app.services import floor_draft_repo as repo
from app.services import floor_proposal as fp
from app.services import to_trinh, to_trinh_html


class DraftConflict(Exception):
    """Bản nháp đã bị người khác lưu đè sau khi mình mở."""


def _vn_time(iso: str) -> str:
    """Mốc updated_at (có múi giờ, prod chạy UTC) → 'HH:MM:SS' giờ Việt Nam."""
    return datetime.fromisoformat(iso).astimezone(edit_window.now().tzinfo).strftime("%H:%M:%S")


def _dmy(iso: str) -> str:
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def default_title(doc: dict) -> str:
    return f"Dự kiến giá sàn lần {doc['lan']}/{doc['year']} — {_dmy(doc['as_of'])}"


def market_doc(as_of: str) -> dict[str, Any]:
    """Ảnh chụp phần thị trường của tờ trình tại as_of (khối 1–2 + diễn giải mặc định)."""
    return to_trinh.build_market(as_of)


def render(prop: dict, doc: dict, n1: list[str] | None = None, n2: list[str] | None = None) -> str:
    """HTML tờ trình: phần thị trường của `doc` + khối 3 từ phương án (+ diễn giải sửa tay nếu có)."""
    data = {**doc, "proposal": fp.to_trinh_rows(prop)}
    if n1 is not None:
        data["n1"] = n1
    if n2 is not None:
        data["n2"] = n2
    return to_trinh_html.render(data)


def create(*, proposal: dict | None, as_of: str | None, model: str | None, title: str | None,
           note: str | None, source: str, username: str | None) -> dict[str, Any]:
    """Tạo bản nháp. Không kèm phương án ⇒ dựng từ mức mô hình tại as_of (mặc định hôm nay)."""
    prop = fp.sanitize(proposal) if proposal else fp.build(as_of, "model", model or fp.fs.DEFAULT_MODEL)
    doc = market_doc(prop["as_of"])
    return repo.create(as_of=prop["as_of"], title=(title or "").strip() or default_title(doc),
                       note=(note or "").strip() or None, source=source, proposal=prop, doc=doc,
                       headline=fp.headline(prop), username=username)


def update(draft_id: int, *, title: str, note: str | None, proposal: dict, n1: list[str],
           n2: list[str], username: str | None, base_updated_at: str | None = None) -> dict[str, Any] | None:
    """Lưu phần sửa tay. Ngày tờ trình cố định theo bản nháp (ảnh chụp thị trường gắn với ngày đó).

    `base_updated_at` = mốc `updated_at` của bản người dùng đang sửa: đã có người lưu sau mốc đó ⇒
    DraftConflict, không để người lưu sau lặng lẽ đè mất phần của người trước.
    """
    current = repo.get(draft_id)
    if not current:
        return None
    if base_updated_at and base_updated_at != current["updated_at"]:
        raise DraftConflict(f"Bản nháp vừa được {current['updated_by'] or 'người khác'} lưu lúc "
                            f"{_vn_time(current['updated_at'])} — tải lại để xem bản mới trước khi lưu.")
    prop = fp.sanitize(proposal)
    if not prop:
        raise fp.ProposalError("Thiếu phương án.")
    if prop["as_of"] != current["as_of"]:
        raise fp.ProposalError("Không đổi được ngày tờ trình của bản nháp — hãy tạo bản nháp mới.")
    doc = {**current["doc"], "n1": n1, "n2": n2}
    return repo.update(draft_id, title=title.strip(), note=(note or "").strip() or None, proposal=prop,
                       doc=doc, headline=fp.headline(prop), username=username)
