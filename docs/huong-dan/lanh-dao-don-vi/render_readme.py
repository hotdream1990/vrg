#!/usr/bin/env python3
"""Dựng README.md TỪ spec.json — một nguồn sự thật cho cả bản Word lẫn bản Markdown.

Trước đây hai file sửa tay song song nên rất dễ lệch (sửa spec quên sửa README). Nay chỉ sửa
`spec.json` rồi chạy:

    python3 docs/huong-dan/nhap-lieu-don-vi-thanh-vien/render_readme.py

Phần đầu README (tiêu đề + 2 đoạn dẫn + khối link) lấy từ `cover` và `readme_head` trong spec.
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent


def render(spec: dict) -> str:
    out: list[str] = [f"# {spec['cover']['title']}", ""]
    out += [p for para in spec["readme_head"]["intro"] for p in (para, "")]
    out += ["> " + line for line in spec["readme_head"]["links"]]
    out.append("")

    for sec in spec["sections"]:
        out += [f"## {sec['title']}", ""]
        if sec.get("location"):
            out += [f"**Vị trí:** {sec['location']}", ""]
        if sec.get("intro"):
            out += [sec["intro"], ""]
        images = sec.get("image")
        images = images if isinstance(images, list) else [images] if images else []
        # `caption` là chuỗi khi 1 ảnh, LIST khi nhiều ảnh — ghép đúng cặp ảnh↔chú thích, không
        # thì mọi ảnh đều mang cả danh sách chú thích.
        caps = sec.get("caption", "")
        caps = caps if isinstance(caps, list) else [caps] * len(images)
        for img, cap in zip(images, caps):
            out += [f"![{cap}]({img['path']})", "", f"*{cap}*", ""]
        if sec.get("pre"):
            out += [sec["pre"], ""]
        for i, step in enumerate(sec.get("steps", []), start=1):
            out.append(f"{i}. {step}")
        if sec.get("steps"):
            out.append("")
        notes = sec.get("notes") or []
        if notes:
            # Mục "Những lỗi hay gặp" đọc dễ hơn nhiều ở dạng BẢNG (hiện tượng ↔ cách xử lý);
            # bản Word vẫn dựng thành gạch đầu dòng như các mục khác.
            if sec.get("notes_as_table"):
                out += ["| Hiện tượng | Nguyên nhân & cách xử lý |", "|---|---|"]
                out += ["| " + n.replace(" → ", " | ", 1) + " |" for n in notes]
            else:
                out += ["> - " + n for n in notes] if len(notes) > 1 else [f"> {notes[0]}"]
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    spec = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
    (HERE / "README.md").write_text(render(spec), encoding="utf-8")
    print(f"Đã dựng README.md từ spec.json ({len(spec['sections'])} mục).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
