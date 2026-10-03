"""Xuất tệp từ bản nháp giá sàn đã lưu: hình dự thảo (PNG) · tờ trình mẫu mới (PDF, Word).

Luôn dựng từ BẢN ĐÃ LƯU — giao diện lưu trước khi tải, nên tệp gửi đi đúng là bản trong hệ thống.
"""
from __future__ import annotations

from app.services import doc_render, du_thao_sheet
from app.services import floor_draft_service as svc
from app.services import floor_proposal as fp
from app.services import to_trinh_docx, to_trinh_view


def _suffix(draft: dict) -> str:
    doc = draft["doc"]
    return f"lan-{doc['lan']}-{doc['year']}"


def du_thao_png(draft: dict) -> tuple[bytes, str]:
    html = du_thao_sheet.render(draft["proposal"], draft["doc"], draft.get("sheet"))
    return doc_render.html_to_png(html, du_thao_sheet.SELECTOR), f"Du-thao-gia-san-{_suffix(draft)}.png"


def to_trinh_pdf(draft: dict) -> tuple[bytes, str]:
    html = svc.render(draft["proposal"], draft["doc"], memo=svc.memo_for(draft))
    return doc_render.html_to_pdf(html), f"To-trinh-gia-san-{_suffix(draft)}.pdf"


def to_trinh_docx_bytes(draft: dict) -> tuple[bytes, str]:
    view = to_trinh_view.build(draft["doc"], svc.memo_for(draft), fp.to_trinh_rows(draft["proposal"]))
    return to_trinh_docx.build_docx(view), f"To-trinh-gia-san-{_suffix(draft)}.docx"
