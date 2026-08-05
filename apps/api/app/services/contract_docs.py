"""Danh sách chứng từ đính kèm (nhiều file) cho 1 ô đính kèm.

Trước đây mỗi ô chỉ giữ ĐƯỢC 1 file, lưu thành cặp khoá phẳng `(file, filename)`. Nay mỗi ô giữ
DANH SÁCH file, nhưng **vẫn ghi lại file đầu tiên vào cặp khoá cũ**:

- Bản ghi CŨ (chỉ có `file`/`filename`) đọc lên vẫn ra đúng 1 file — không cần chuyển đổi dữ liệu.
- Chỗ nào còn đọc khoá cũ (Excel nhập lại, nhật ký hoạt động…) vẫn chạy bình thường.

Vì vậy tuyệt đối KHÔNG bỏ cặp khoá cũ khi ghi.
"""

from __future__ import annotations

from typing import Any

MAX_DOCS = 20        # trần số file mỗi ô — đủ cho một bộ hợp đồng nhiều đợt giao
_NAME_MAX = 120      # khớp độ dài tên lưu (uuid + đuôi) đang dùng
_ORIG_MAX = 200      # tên gốc hiển thị


def normalize(raw: Any, legacy_file: Any = None, legacy_name: Any = None) -> list[dict[str, str]]:
    """Chuẩn hoá danh sách chứng từ → `[{"file": …, "filename": …}]`.

    `raw` là danh sách mới; thiếu/rỗng thì lùi về cặp khoá cũ `legacy_file`/`legacy_name` để bản ghi
    cũ vẫn hiện đúng file đã đính kèm. Bỏ mục rỗng, khử trùng lặp theo tên lưu, cắt trần `MAX_DOCS`.
    """
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(f: Any, n: Any) -> None:
        name = str(f or "").strip()[:_NAME_MAX]
        if not name or name in seen:
            return
        seen.add(name)
        out.append({"file": name, "filename": str(n or "").strip()[:_ORIG_MAX] or name})

    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            add(item.get("file"), item.get("filename"))
    if not out:
        add(legacy_file, legacy_name)
    return out[:MAX_DOCS]


def first(docs: list[dict[str, str]]) -> tuple[str | None, str | None]:
    """Cặp `(file, filename)` cũ = chứng từ đầu danh sách — để ghi kèm cho tương thích ngược."""
    return (docs[0]["file"], docs[0]["filename"]) if docs else (None, None)
