#!/usr/bin/env python3
"""Dữ liệu mẫu + dọn dẹp cho BỘ ẢNH của hai sổ tay "Đề nghị sửa số liệu".

Dùng chung cho `de-nghi-sua-so-lieu/shoot.py` (đơn vị) và `duyet-de-nghi-sua/shoot.py` (Ban).

DB dev là bản sao production ⇒ mọi thứ tạo ra ở đây phải được hoàn nguyên: chụp xong gọi `restore()`
để trả lại payload biểu ngày + giá, xoá đợt chốt, đề nghị và nhật ký phát sinh trong lúc chụp.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "apps/api"))

from sqlalchemy import text  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.core.security import create_access_token  # noqa: E402

WEB = "http://localhost:5390"

TN = "Công ty Cổ phần Cao Su Tây Ninh"
DAY = "2026-08-20"            # ngày cũ đã quá hạn sửa + nằm trong kỳ đã chốt
LOCK_DATES = ("2026-08-15", "2026-08-31")
LOCK_NOTE = "Chốt số liệu tháng 8"

#: Tài khoản thật trên dev — chỉ mượn để chụp, không đổi gì trong hồ sơ tài khoản.
ACC = {
    "tn": "thunguyettd@gmail.com",       # đơn vị Tây Ninh (nhập liệu)
    "dp": "doruco.bpc@gmail.com",        # Đồng Phú — có Nhu cầu thị trường ngày cũ
    "brk": "nguyenthambrk@gmail.com",    # Bà Rịa - Kampong Thom — có hợp đồng đã giao ngày cũ
    "admin": "admin",
}

#: Popup AntD hay kẹt animation khi chạy headless → ép hiện, và giấu toast cho ảnh sạch.
FORCE_MODAL = """
document.addEventListener('DOMContentLoaded', () => {
  const s = document.createElement('style');
  s.textContent = '.ant-modal,.ant-modal-mask,.ant-modal-wrap{opacity:1!important;'
    + 'transform:none!important;animation:none!important}.ant-message{display:none!important}';
  document.head.appendChild(s);
});
"""


def sql(q: str, params: dict | None = None):
    with session_scope() as db:
        res = db.execute(text(q), params or {})
        try:
            return res.mappings().all()
        except Exception:      # noqa: BLE001 — câu lệnh không trả dòng
            return []


def page_for(browser, who: str, width: int = 1500, height: int = 880):
    """Tab mới đã đăng nhập sẵn bằng tài khoản `who` (đặt thẳng token vào localStorage)."""
    ctx = browser.new_context(viewport={"width": width, "height": height},
                              device_scale_factor=2, locale="vi-VN")
    ctx.add_init_script(f"localStorage.setItem('vrg_token', {json.dumps(create_access_token(ACC[who]))});"
                        "localStorage.removeItem('vrg_admin_token');")
    ctx.add_init_script(FORCE_MODAL)
    return ctx.new_page()


class Sandbox:
    """Chụp ảnh trên dữ liệu thật ⇒ ghi lại hiện trạng trước, trả lại y nguyên sau."""

    def __init__(self) -> None:
        self.audit_from = sql("SELECT COALESCE(max(id),0) AS m FROM audit_log")[0]["m"]
        self.req_from = sql("SELECT COALESCE(max(id),0) AS m FROM edit_request")[0]["m"]
        row = sql("SELECT payload, updated_by, updated_at FROM unit_daily_report "
                  "WHERE kind='purchase' AND company=:c AND as_of=CAST(:d AS date)",
                  {"c": TN, "d": DAY})
        self.day = dict(row[0]) if row else None
        self.prices = [dict(r) for r in sql(
            "SELECT source, price_type, price FROM fact_price WHERE grade=:c AND as_of=CAST(:d AS date)",
            {"c": TN, "d": DAY})]
        self.rounds: list[int] = []

    # ── dữ liệu mẫu ────────────────────────────────────────────────────────────
    def lock_rounds(self) -> None:
        """Hai đợt chốt số liệu tháng 8 mà Tây Ninh đã xác nhận (để ngày 20/08 bị khoá)."""
        for d in LOCK_DATES:
            rid = sql("INSERT INTO data_lock_round (lock_date, note, created_by) "
                      "VALUES (CAST(:d AS date), :n, 'admin') RETURNING id",
                      {"d": d, "n": LOCK_NOTE})[0]["id"]
            sql("INSERT INTO unit_data_lock (round_id, company, locked_by, by_admin) "
                "VALUES (:r, :c, 'admin', true)", {"r": rid, "c": TN})
            self.rounds.append(rid)

    def bump_day_price(self, delta: float = 3) -> None:
        """Đổi nhẹ giá đã lưu để trang duyệt hiện cảnh báo “số liệu đã thay đổi kể từ lúc gửi”."""
        sql("UPDATE fact_price SET price = price + :v WHERE grade=:c AND as_of=CAST(:d AS date) "
            "AND source='vrg_unit'", {"v": delta, "c": TN, "d": DAY})

    # ── dọn dẹp ────────────────────────────────────────────────────────────────
    def restore(self) -> None:
        if self.day is not None:
            sql("UPDATE unit_daily_report SET payload=CAST(:p AS jsonb), updated_by=:u, updated_at=:t "
                "WHERE kind='purchase' AND company=:c AND as_of=CAST(:d AS date)",
                {"p": json.dumps(self.day["payload"]), "u": self.day["updated_by"],
                 "t": self.day["updated_at"], "c": TN, "d": DAY})
        keep = {(r["source"], r["price_type"]) for r in self.prices}
        for r in sql("SELECT source, price_type FROM fact_price WHERE grade=:c AND as_of=CAST(:d AS date)",
                     {"c": TN, "d": DAY}):
            if (r["source"], r["price_type"]) not in keep:
                sql("DELETE FROM fact_price WHERE grade=:c AND as_of=CAST(:d AS date) "
                    "AND source=:s AND price_type=:t",
                    {"c": TN, "d": DAY, "s": r["source"], "t": r["price_type"]})
        for r in self.prices:
            sql("UPDATE fact_price SET price=:v WHERE grade=:c AND as_of=CAST(:d AS date) "
                "AND source=:s AND price_type=:t",
                {"v": r["price"], "c": TN, "d": DAY, "s": r["source"], "t": r["price_type"]})
        sql("DELETE FROM unit_data_lock WHERE round_id = ANY(:r)", {"r": self.rounds or [0]})
        sql("DELETE FROM data_lock_round WHERE id = ANY(:r)", {"r": self.rounds or [0]})
        sql("DELETE FROM edit_request WHERE id > :i", {"i": self.req_from})
        sql("DELETE FROM audit_log WHERE id > :i", {"i": self.audit_from})


def check_clean() -> None:
    """In ra trạng thái kho dữ liệu sau khi dọn — chạy lại được nhiều lần."""
    n_req = sql("SELECT count(*) AS n FROM edit_request")[0]["n"]
    n_round = sql("SELECT count(*) AS n FROM data_lock_round")[0]["n"]
    print(f"còn lại: edit_request={n_req} · data_lock_round={n_round}")


if __name__ == "__main__":
    check_clean()
