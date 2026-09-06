"""Chứng từ đính kèm (bộ Hợp đồng · phiếu xuất kho · hoá đơn) của biểu Tiêu thụ – Tồn kho.

Luật lưu/kiểm/phục vụ file nằm ở `attachment_store` (dùng chung với các module đính kèm khác);
module này chỉ chốt THƯ MỤC riêng `data_dir()/unit-daily-contracts` (mount volume khi deploy).
Tên lưu là uuid; tên gốc giữ riêng ở payload để hiển thị.
"""

from __future__ import annotations

from app.services.attachment_store import ACCEPT_LABEL, AttachmentStore

__all__ = ["ACCEPT_LABEL", "save", "path_for", "serve"]

_store = AttachmentStore("unit-daily-contracts")

save = _store.save
path_for = _store.path_for
serve = _store.serve
