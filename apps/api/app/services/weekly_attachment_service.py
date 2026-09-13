"""Tài liệu đính kèm của Báo cáo tuần (bảng `weekly_report_attachment`) — lưu file + trích chữ.

File nằm ở `data_dir()/weekly-reports/attachments/` (volume sẵn có của báo cáo tuần). Chỉ nhận PDF
và DOCX — hai loại trích được chữ cho AI đọc. File không trích được chữ (bản scan) vẫn lưu,
`text_chars = 0`, để chuyên viên tự nhập tóm tắt.
Mọi hàm nhận `week_key` và lọc theo nó: id đính kèm của tuần khác coi như không có (chặn IDOR).
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo
from app.services.attachment_store import AttachmentStore, ext_of
from app.services.weekly_attachment_text import extract, guess_kind
from app.services.weekly_source_defaults import KINDS

_ENTITY = "bulletin_weekly"
ALLOWED_EXTS = (".pdf", ".docx")
store = AttachmentStore("weekly-reports/attachments")

_SUMMARY_COLS = "id, week_key, file, filename, size, kind, pages, length(text_content) AS text_chars, " \
                "summary, uploaded_by, created_at, updated_at"


def _out(r: Any) -> dict[str, Any]:
    d = dict(r)
    for k in ("created_at", "updated_at"):
        d[k] = d[k].isoformat() if d.get(k) else None
    d["text_chars"] = int(d.get("text_chars") or 0)
    return d


def _audit_view(d: dict[str, Any]) -> dict[str, Any]:
    """Bản ghi gọn cho Nhật ký (không nhét 200.000 ký tự chữ trích vào log)."""
    return {k: d.get(k) for k in ("id", "filename", "size", "kind", "pages", "text_chars", "summary")}


def list_attachments(week_key: str) -> list[dict[str, Any]]:
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(f"SELECT {_SUMMARY_COLS} FROM weekly_report_attachment "
                               "WHERE week_key = :k ORDER BY id"), {"k": week_key}).mappings().all()
    return [_out(r) for r in rows]


def get_attachment(week_key: str, att_id: int, with_text: bool = False) -> dict[str, Any] | None:
    """1 đính kèm của đúng tuần; `with_text=True` kèm `text_content` (cho AI tóm tắt)."""
    ensure_schema()
    cols = _SUMMARY_COLS + (", text_content" if with_text else "")
    with session_scope() as db:
        r = db.execute(text(f"SELECT {cols} FROM weekly_report_attachment "
                            "WHERE id = :i AND week_key = :k"), {"i": att_id, "k": week_key}).mappings().first()
    return _out(r) if r else None


def upload(week_key: str, file: UploadFile, kind: str | None, username: str | None) -> dict[str, Any]:
    """Lưu file + trích chữ + đoán loại (nếu không chọn). 400 nếu không phải PDF/DOCX."""
    if ext_of(file) not in ALLOWED_EXTS:
        raise HTTPException(400, "Chỉ nhận tài liệu PDF hoặc Word (.docx).")
    if kind and kind not in KINDS:
        raise HTTPException(400, f"Loại tài liệu không hợp lệ: “{kind}”.")
    saved = store.save(file)
    path = store.path_for(saved["file"])
    ensure_schema()
    try:
        content, pages = extract(path)
        with session_scope() as db:
            # Tải tài liệu trước khi viết chữ nào → vẫn tạo bản ghi báo cáo rỗng, để kỳ hiện trong danh sách
            # "Báo cáo đã lưu" (không thì tài liệu bị lạc) và nút Xoá xoá được cả tài liệu.
            db.execute(text("INSERT INTO weekly_report (week_key, payload) VALUES (:k, CAST('{}' AS jsonb)) "
                            "ON CONFLICT (week_key) DO NOTHING"), {"k": week_key})
            r = db.execute(text(f"""
                INSERT INTO weekly_report_attachment
                    (week_key, file, filename, size, kind, pages, text_content, uploaded_by)
                VALUES (:k, :file, :filename, :size, :kind, :pages, :content, :u)
                RETURNING {_SUMMARY_COLS}
            """), {"k": week_key, **saved, "kind": kind or guess_kind(saved["filename"], content),
                   "pages": pages, "content": content, "u": username}).mappings().first()
    except Exception:
        path.unlink(missing_ok=True)  # trích chữ/ghi DB lỗi thì đừng để file mồ côi
        raise
    created = _out(r)
    audit_repo.log(_ENTITY, "create", f"{week_key}:attachment:{created['id']}", as_of=week_key,
                   after=_audit_view(created), note=f"Tải tài liệu đính kèm: {created['filename']}")
    return created


def update(week_key: str, att_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
    """Sửa `kind` và/hoặc `summary` (chuỗi rỗng = xoá tóm tắt). None nếu không có."""
    before = get_attachment(week_key, att_id)
    if not before:
        return None
    kind = changes.get("kind", before["kind"]) or before["kind"]
    if kind not in KINDS:
        raise HTTPException(400, f"Loại tài liệu không hợp lệ: “{kind}”.")
    summary = changes["summary"] if "summary" in changes else before["summary"]
    summary = (summary or "").strip()[:20000] or None
    with session_scope() as db:
        r = db.execute(text(f"""
            UPDATE weekly_report_attachment SET kind = :kind, summary = :summary, updated_at = now()
             WHERE id = :i AND week_key = :k RETURNING {_SUMMARY_COLS}
        """), {"kind": kind, "summary": summary, "i": att_id, "k": week_key}).mappings().first()
    if not r:
        return None
    after = _out(r)
    audit_repo.log(_ENTITY, "update", f"{week_key}:attachment:{att_id}", as_of=week_key,
                   before=_audit_view(before), after=_audit_view(after),
                   note=f"Sửa tài liệu đính kèm: {after['filename']}")
    return after


def set_summary(week_key: str, att_id: int, summary: str) -> dict[str, Any] | None:
    """Lưu tóm tắt (AI hoặc chuyên viên)."""
    return update(week_key, att_id, {"summary": summary})


def delete(week_key: str, att_id: int) -> bool:
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(f"DELETE FROM weekly_report_attachment WHERE id = :i AND week_key = :k "
                            f"RETURNING {_SUMMARY_COLS}"), {"i": att_id, "k": week_key}).mappings().first()
    if not r:
        return False
    before = _out(r)
    (store.dir / before["file"]).unlink(missing_ok=True)
    audit_repo.log(_ENTITY, "delete", f"{week_key}:attachment:{att_id}", as_of=week_key,
                   before=_audit_view(before), note=f"Xoá tài liệu đính kèm: {before['filename']}")
    return True


def delete_all(week_key: str) -> int:
    """Xoá mọi đính kèm (bản ghi + file) của 1 báo cáo tuần → số file đã xoá."""
    return sum(1 for a in list_attachments(week_key) if delete(week_key, a["id"]))


def serve_file(week_key: str, att_id: int):
    att = get_attachment(week_key, att_id)
    if not att:
        raise HTTPException(404, "Không tìm thấy tài liệu đính kèm.")
    return store.serve(att["file"], att["filename"])


def context_documents(week_key: str, max_chars: int = 24000) -> list[dict[str, Any]]:
    """Tài liệu cho AI: ưu tiên tóm tắt, không có thì chữ trích; chia đều ngân sách ký tự giữa các file."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT id, filename, kind, summary, text_content "
                               "FROM weekly_report_attachment WHERE week_key = :k ORDER BY id"),
                          {"k": week_key}).mappings().all()
    docs = []
    for r in rows:
        summary = (r["summary"] or "").strip()
        body = summary or (r["text_content"] or "").strip()
        if body:
            docs.append({"id": r["id"], "filename": r["filename"], "kind": r["kind"],
                         "used": "summary" if summary else "text", "content": body})
    if not docs:
        return []
    budget = max(max_chars // len(docs), 0)
    return [{**d, "content": d["content"][:budget]} for d in docs]
