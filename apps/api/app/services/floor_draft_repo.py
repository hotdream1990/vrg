"""Bản nháp TỜ TRÌNH giá sàn (`floor_draft`) — phương án người dùng đã chỉnh + ảnh chụp số thị trường.

Tách hẳn biểu giá sàn chính thức (`vrg_floor_price` không bị đụng). Lưu ẢNH CHỤP phần thị trường
(khối 1–2, lần thứ, ngày so sánh) lúc tạo: đây là văn bản trình duyệt, mở lại phải thấy đúng số
lúc soạn dù sau đó dữ liệu được nhập bù. Bảng tạo trong module này (idempotent, như
`assistant_log_repo`), không sửa `core/db.py`.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.core.db import get_engine, session_scope
from app.services import audit_repo
from app.services.floor_draft_stage import proposal_sig

ENTITY = "floor_suggest"   # nhật ký hoạt động: gom dưới mục "Gợi ý giá sàn"
SOURCES = ("assistant", "floor_suggest", "manual")
PAGE_SIZE_MAX = 100

_DDL = """
CREATE TABLE IF NOT EXISTS floor_draft (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    as_of       date NOT NULL,
    title       text NOT NULL,
    note        text,
    source      text NOT NULL DEFAULT 'manual',
    payload     jsonb NOT NULL,
    created_by  text,
    updated_by  text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_floor_draft_updated ON floor_draft (updated_at DESC);
-- Bước quy trình (floor_draft_stage): nhap · du_thao · to_trinh · ap_dung. Bản cũ = nhap.
ALTER TABLE floor_draft ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT 'nhap';
"""

_COLS = "id, as_of, title, note, source, stage, payload, created_by, updated_by, created_at, updated_at"
_ready = False


def _ensure_schema() -> None:
    global _ready
    if _ready:
        return
    with get_engine().begin() as conn:
        conn.execute(text(_DDL))
    _ready = True


def _row(r: Any, full: bool = True) -> dict[str, Any]:
    payload = dict(r["payload"])
    doc = payload.get("doc") or {}
    out = {"id": r["id"], "as_of": str(r["as_of"]), "title": r["title"], "source": r["source"],
           "stage": r["stage"],
           "created_by": r["created_by"], "updated_by": r["updated_by"],
           "created_at": r["created_at"].isoformat(timespec="seconds"),
           "updated_at": r["updated_at"].isoformat(timespec="seconds")}
    if full:
        out.update(note=r["note"], proposal=payload.get("proposal"), doc=doc, sheet=payload.get("sheet"),
                   memo=payload.get("memo"), history=payload.get("history") or [],
                   sig=proposal_sig(payload.get("proposal")))
    else:
        out.update(lan=doc.get("lan"), headline=payload.get("headline") or "")
    return out


def _audit_view(d: dict | None) -> dict | None:
    """Phần đáng ghi nhật ký: tiêu đề + số đề xuất từng dòng (không chép cả ảnh chụp thị trường)."""
    if not d:
        return None
    rows = (d.get("proposal") or {}).get("rows") or []
    return {"title": d.get("title"), "note": d.get("note"),
            "rows": {r["grade"]: [r.get("fob"), r.get("vnd")] for r in rows},
            "n1": (d.get("doc") or {}).get("n1"), "n2": (d.get("doc") or {}).get("n2"),
            "stage": d.get("stage"), "sheet": d.get("sheet"), "memo": d.get("memo")}


def _payload(proposal: dict, doc: dict, headline: str, sheet: dict | None = None, memo: dict | None = None,
             history: list | None = None) -> str:
    return json.dumps({"proposal": proposal, "doc": doc, "headline": headline, "sheet": sheet, "memo": memo,
                       "history": history or []}, ensure_ascii=False, default=str)


def get(draft_id: int) -> dict[str, Any] | None:
    _ensure_schema()
    with session_scope() as db:
        r = db.execute(text(f"SELECT {_COLS} FROM floor_draft WHERE id = :i"),
                       {"i": draft_id}).mappings().first()
    return _row(r) if r else None


def list_page(page: int = 1, page_size: int = 25) -> dict[str, Any]:
    """Phân trang Ở SERVER (quy tắc dự án: không màn nào tải hết dữ liệu), mới sửa trước."""
    _ensure_schema()
    page = max(1, page)
    page_size = min(max(1, page_size), PAGE_SIZE_MAX)
    with session_scope() as db:
        total = db.execute(text("SELECT count(*) FROM floor_draft")).scalar() or 0
        # Danh sách chỉ cần lần thứ + dòng tóm tắt — không kéo cả ảnh chụp thị trường của từng nháp.
        rows = db.execute(text(
            "SELECT id, as_of, title, note, source, stage, created_by, updated_by, created_at, updated_at, "
            "jsonb_build_object('doc', jsonb_build_object('lan', payload->'doc'->'lan'), "
            "'headline', payload->'headline') AS payload "
            "FROM floor_draft ORDER BY updated_at DESC, id DESC LIMIT :n OFFSET :o"),
                          {"n": page_size, "o": (page - 1) * page_size}).mappings().all()
    return {"items": [_row(r, full=False) for r in rows], "total": int(total),
            "page": page, "page_size": page_size}


def create(*, as_of: str, title: str, note: str | None, source: str, proposal: dict,
           doc: dict, headline: str, username: str | None) -> dict[str, Any]:
    _ensure_schema()
    with session_scope() as db:
        new_id = db.execute(text(
            "INSERT INTO floor_draft (as_of, title, note, source, payload, created_by, updated_by) "
            "VALUES (CAST(:d AS date), :t, :n, :s, CAST(:p AS jsonb), :u, :u) RETURNING id"),
            {"d": as_of, "t": title, "n": note, "s": source if source in SOURCES else "manual",
             "p": _payload(proposal, doc, headline), "u": username}).scalar()
    saved = get(int(new_id))
    audit_repo.log(ENTITY, "create", f"ban-nhap-{new_id}", after=_audit_view(saved), as_of=as_of,
                   note="Bản nháp tờ trình giá sàn")
    return saved


def update(draft_id: int, *, title: str, note: str | None, proposal: dict, doc: dict, headline: str,
           sheet: dict | None, memo: dict | None, username: str | None,
           stage: str | None = None, history: list | None = None) -> dict[str, Any] | None:
    """Ghi đè nội dung (và bước, nếu `stage` khác None). Kiểm tra quyền sửa theo bước ở tầng service."""
    before = get(draft_id)
    if not before:
        return None
    with session_scope() as db:
        db.execute(text("UPDATE floor_draft SET title = :t, note = :n, payload = CAST(:p AS jsonb), "
                        "stage = :st, updated_by = :u, updated_at = now() WHERE id = :i"),
                   {"t": title, "n": note, "u": username, "i": draft_id, "st": stage or before["stage"],
                    "p": _payload(proposal, doc, headline, sheet, memo,
                                  before["history"] if history is None else history)})
    saved = get(draft_id)
    # Soạn nháp hay lưu liên tục → gộp các lần lưu liền nhau cho nhật ký gọn; chuyển bước ghi riêng.
    moved = stage is not None and stage != before["stage"]
    note = f"Bản nháp tờ trình giá sàn — chuyển bước {before['stage']} → {stage}" if moved else \
        "Bản nháp tờ trình giá sàn"
    audit_repo.log(ENTITY, "update", f"ban-nhap-{draft_id}", before=_audit_view(before),
                   after=_audit_view(saved), as_of=before["as_of"], note=note, coalesce=not moved)
    return saved


def delete(draft_id: int) -> int:
    before = get(draft_id)
    if not before:
        return 0
    with session_scope() as db:
        removed = db.execute(text("DELETE FROM floor_draft WHERE id = :i"), {"i": draft_id}).rowcount
    if removed:
        audit_repo.log(ENTITY, "delete", f"ban-nhap-{draft_id}", before=_audit_view(before),
                       as_of=before["as_of"], note="Bản nháp tờ trình giá sàn")
    return removed
