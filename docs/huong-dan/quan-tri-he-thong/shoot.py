#!/usr/bin/env python3
"""Dựng lại ảnh màn "Đơn vị thành viên" của hướng dẫn QUẢN TRỊ (chạy khi cột trên màn đổi).

Chỉ chụp ĐÚNG màn này — các ảnh còn lại của bộ hướng dẫn quản trị (người dùng, cấu hình, lịch
chạy) hiện vẫn chụp tay. Màn Đơn vị thành viên đổi cột nhiều nhất (khu vực · quốc gia/tiền · nhà
máy · công ty mẹ) nên tách riêng cho tự động.

Chạy:  ./scripts/dev.sh (API 8390 + Web 5390) rồi
       uv run --directory apps/api --with playwright python \
           ../../docs/huong-dan/quan-tri-he-thong/shoot.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

SKILL = pathlib.Path.home() / ".claude/skills/screenshot-annotate/scripts"
sys.path.insert(0, str(SKILL))
from shoot import annotated_shot, browser_page  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

API = "http://localhost:8390"
WEB = "http://localhost:5390"
OUT = pathlib.Path(__file__).parent / "img"

#: Chú thích khớp ĐÚNG thứ tự các bước ở mục 7 trong `spec.json` — thêm/bớt bước thì sửa cả hai nơi.
TARGETS = """(() => {
  const tab = (t) => [...document.querySelectorAll('.ant-segmented-item-label, button, .blt-tab')]
      .find(e => e.textContent.trim() === t);
  const th = (t) => [...document.querySelectorAll('th')]
      .find(e => e.textContent.replace(/\\s+/g, ' ').trim().startsWith(t));
  return window.__annotate([
    tab('Đơn vị'), tab('Khu vực'),
    document.querySelector('input[placeholder^="Tên đơn vị mới"]'),
    th('Khu vực'), th('Quốc gia'), th('Nhà máy'), th('Công ty mẹ'),
  ]);
})()"""


def main() -> int:
    req = urllib.request.Request(f"{API}/api/auth/login", method="POST",
                                 data=json.dumps({"username": "admin", "password": "admin"}).encode())
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        tok = json.loads(r.read())["access_token"]

    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        page = browser_page(p, 1500, 950)
        page.context.add_init_script(f"localStorage.setItem('vrg_token', {tok!r});")
        annotated_shot(page, f"{WEB}/quan-ly-so-lieu/don-vi-thanh-vien", TARGETS,
                       str(OUT / "06-don-vi-thanh-vien.png"), wait_for="table")
    print(f"Xong. Ảnh ở {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
