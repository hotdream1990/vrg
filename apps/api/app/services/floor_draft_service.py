"""Nghiệp vụ bản nháp tờ trình giá sàn: dựng từ phương án, sửa, xem trước (HTML).

Ghép 3 phần có sẵn: phương án [floor_proposal] (khối 3) + phần thị trường [to_trinh.build_market]
(khối 1–2, lần thứ) + mẫu in [to_trinh_html.render]. Lưu trữ ở [floor_draft_repo].
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core import edit_window

from app.services import floor_draft_repo as repo
from app.services import floor_draft_stage as st
from app.services import floor_proposal as fp
from app.services import inventory_repo, to_trinh, to_trinh_html, to_trinh_memo


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


def inventory_rows(as_of: str) -> list[dict]:
    """2 tuần tồn kho Tập đoàn gần nhất tính đến ngày tờ trình (mới trước) — cho dòng tồn kho."""
    return [r for r in inventory_repo.series() if r["as_of"] <= as_of][:2]


def default_sheet(as_of: str) -> dict:
    return {"vcb_rate": None, "vcb_time": "8g30", "vcb_date": as_of}


def clean_sheet(raw: dict | None, base: dict) -> dict:
    raw = raw or {}
    rate = raw.get("vcb_rate", base.get("vcb_rate"))
    try:
        rate = float(rate) if rate is not None else None
    except (TypeError, ValueError):
        rate = None
    if rate is not None and not 10_000 <= rate <= 100_000:
        raise fp.ProposalError("Tỷ giá VCB phải trong khoảng 10.000–100.000 đ/USD.")
    day = raw.get("vcb_date", base.get("vcb_date"))
    return {"vcb_rate": rate, "vcb_time": str(raw.get("vcb_time", base.get("vcb_time")) or "")[:20].strip(),
            "vcb_date": fp.valid_date(day) if day else None}


def memo_for(draft: dict) -> dict:
    """Nội dung tờ trình của bản nháp: bản đã lưu, chưa có thì mặc định dựng từ số."""
    base = to_trinh_memo.defaults(draft["doc"], inventory_rows(draft["as_of"]))
    return to_trinh_memo.clean(draft["memo"], base) if draft.get("memo") else base


def render(prop: dict, doc: dict, n1: list[str] | None = None, n2: list[str] | None = None,
           memo: dict | None = None) -> str:
    """HTML tờ trình (mẫu mới): phần thị trường của `doc` + khối 3 từ phương án + nội dung tờ trình
    (`memo`; không có thì mặc định dựng từ số — kèm diễn giải sửa tay n1/n2 của bản nháp cũ nếu có)."""
    data = {**doc, "proposal": fp.to_trinh_rows(prop)}
    if n1 is not None:
        data["n1"] = n1
    if n2 is not None:
        data["n2"] = n2
    base = to_trinh_memo.defaults(data, inventory_rows(doc["as_of"]))
    data["memo"] = to_trinh_memo.clean(memo, base) if memo else base
    return to_trinh_html.render(data)


def create(*, proposal: dict | None, as_of: str | None, model: str | None, title: str | None,
           note: str | None, source: str, username: str | None) -> dict[str, Any]:
    """Tạo bản nháp. Không kèm phương án ⇒ dựng từ mức mô hình tại as_of (mặc định hôm nay)."""
    prop = fp.sanitize(proposal) if proposal else fp.build(as_of, "model", model or fp.fs.DEFAULT_MODEL)
    doc = market_doc(prop["as_of"])
    return repo.create(as_of=prop["as_of"], title=(title or "").strip() or default_title(doc),
                       note=(note or "").strip() or None, source=source, proposal=prop, doc=doc,
                       headline=fp.headline(prop), username=username)


def render_built(d: dict) -> str:
    """HTML tờ trình từ `to_trinh.build` (đề xuất = mức mô hình) — nội dung mặc định kèm tồn kho."""
    if not d.get("error"):
        d = {**d, "memo": to_trinh_memo.defaults(d, inventory_rows(d["as_of"]))}
    return to_trinh_html.render(d)


def _guard(draft_id: int, base_updated_at: str | None) -> dict[str, Any] | None:
    """Bản hiện tại; đã có người lưu sau mốc `base_updated_at` của người đang sửa ⇒ DraftConflict."""
    current = repo.get(draft_id)
    if current and base_updated_at and base_updated_at != current["updated_at"]:
        raise DraftConflict(f"Bản nháp vừa được {current['updated_by'] or 'người khác'} lưu lúc "
                            f"{_vn_time(current['updated_at'])} — tải lại để xem bản mới trước khi lưu.")
    return current


def _changed_numbers(a: dict, b: dict) -> bool:
    return st.proposal_sig(a) != st.proposal_sig(b) or len(a.get("log") or []) != len(b.get("log") or [])


def update(draft_id: int, *, title: str, note: str | None, proposal: dict, n1: list[str] | None,
           n2: list[str] | None, username: str | None, base_updated_at: str | None = None,
           sheet: dict | None = None, memo: dict | None = None) -> dict[str, Any] | None:
    """Lưu phần sửa tay. Ngày tờ trình cố định theo bản nháp (ảnh chụp thị trường gắn với ngày đó).
    Mỗi phần chỉ sửa ở đúng bước của nó (`floor_draft_stage.check_edit`) — gửi lại y nguyên thì cho qua.

    `base_updated_at` = mốc `updated_at` của bản người dùng đang sửa: đã có người lưu sau mốc đó ⇒
    DraftConflict, không để người lưu sau lặng lẽ đè mất phần của người trước.
    """
    current = _guard(draft_id, base_updated_at)
    if not current:
        return None
    stage = st.normalize(current["stage"])
    if stage == "ap_dung":
        raise st.StageError("Bản nháp đã ở bước Áp dụng — không sửa được nữa.")
    prop = fp.sanitize(proposal)
    if not prop:
        raise fp.ProposalError("Thiếu phương án.")
    if prop["as_of"] != current["as_of"]:
        raise fp.ProposalError("Không đổi được ngày tờ trình của bản nháp — hãy tạo bản nháp mới.")
    if _changed_numbers(prop, current["proposal"]):
        st.check_edit(stage, "proposal")
    elif stage != "nhap":
        prop = current["proposal"]          # số đã chốt: giữ đúng bản đã lưu
    new_sheet = current.get("sheet")
    if sheet is not None:
        new_sheet = clean_sheet(sheet, current.get("sheet") or default_sheet(current["as_of"]))
        if new_sheet != current.get("sheet"):
            st.check_edit(stage, "sheet")
    new_memo = current.get("memo")
    if memo is not None:
        base = memo_for(current)
        new_memo = to_trinh_memo.clean(memo, base)
        if new_memo != (base if current.get("memo") else None):
            st.check_edit(stage, "memo")
    doc = {**current["doc"], "n1": current["doc"].get("n1") if n1 is None else n1,
           "n2": current["doc"].get("n2") if n2 is None else n2}
    return repo.update(draft_id, title=title.strip(), note=(note or "").strip() or None, proposal=prop,
                       doc=doc, headline=fp.headline(prop), sheet=new_sheet, memo=new_memo, username=username)


def change_stage(draft_id: int, target: str, *, username: str | None,
                 base_updated_at: str | None = None) -> dict[str, Any] | None:
    """Chuyển một nấc. Vào Dự thảo lần đầu: tạo chú thích tỷ giá; vào Tờ trình lần đầu: dựng nội dung
    mặc định từ số. Lui về không xoá gì (nội dung tờ trình giữ nguyên để dùng lại)."""
    current = _guard(draft_id, base_updated_at)
    if not current:
        return None
    stage = st.normalize(current["stage"])
    st.check_move(stage, target, current["proposal"])
    sheet = current.get("sheet") or (default_sheet(current["as_of"]) if target == "du_thao" else None)
    memo = current.get("memo") or (memo_for(current) if target == "to_trinh" else None)
    history = [*(current.get("history") or []),
               {"from": stage, "to": target, "at": fp.now_iso(), "by": username}][-50:]
    return repo.update(draft_id, title=current["title"], note=current["note"], proposal=current["proposal"],
                       doc=current["doc"], headline=fp.headline(current["proposal"]), sheet=sheet, memo=memo,
                       username=username, stage=target, history=history)
