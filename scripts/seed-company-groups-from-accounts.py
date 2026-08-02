#!/usr/bin/env python3
"""Dựng CÂY CÔNG TY MẸ–CON từ các tài khoản đơn vị thành viên gán NHIỀU đơn vị (chạy MỘT LẦN).

Cơ chế cũ chỉ diễn đạt quan hệ mẹ–con bằng cách cho 1 tài khoản nhập cho nhiều đơn vị
(`app_user.member_units`). Từ 02/08/2026 tiêu thụ nội bộ chỉ được bán trong NHÓM công ty mẹ–con
(`member_unit.parent_company`) nên phải chuyển tri thức đó sang cột chính thức.

QUY TẮC: trong 1 tài khoản, đơn vị ĐẦU DANH SÁCH là công ty MẸ, các đơn vị sau là công ty CON.

NGUYÊN TẮC:
  - KHÔNG ghi đè đơn vị ĐÃ có công ty mẹ — admin đã khai tay thì tôn trọng.
  - Đơn vị bị 2 tài khoản đòi 2 mẹ khác nhau → BỎ QUA, in ra để admin tự quyết (không chọn bừa).
  - Cây chỉ 1 cấp: đơn vị đang là MẸ của đơn vị khác thì không cho thành CON của ai.
  - Sau khi chạy, cây đứng độc lập — cấp/sửa tài khoản về sau KHÔNG còn đổi phạm vi tiêu thụ nội bộ.

Chạy:  uv run --directory apps/api python ../../scripts/seed-company-groups-from-accounts.py [--commit]
Mặc định chạy THỬ (dry-run), chỉ in ra sẽ gán gì.
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg

DEFAULT_DSN = "postgresql://vrg:changeme@localhost:5433/vrg_caosu"


def _proposals(cur) -> tuple[dict[str, str], list[str], int]:
    """{đơn vị con: công ty mẹ} + vướng mắc cần admin xử lý tay + số tài khoản đã quét."""
    cur.execute("SELECT username, member_units FROM app_user "
                " WHERE role = 'member' AND jsonb_array_length(member_units) > 1 "
                " ORDER BY username")
    accounts = cur.fetchall()

    cur.execute("SELECT name, parent_company FROM member_unit")
    units = dict(cur.fetchall())
    already_parent = {p for p in units.values() if p}

    proposals: dict[str, str] = {}
    claimed_by: dict[str, str] = {}      # đơn vị con → tài khoản đề xuất (để báo xung đột)
    issues: list[str] = []
    for username, member_units in accounts:
        parent, *children = list(member_units)
        if parent not in units:
            issues.append(f"{username}: đơn vị mẹ “{parent}” không có trong danh mục — bỏ qua cả nhóm")
            continue
        if units.get(parent):
            issues.append(f"{username}: “{parent}” đang là CON của “{units[parent]}” "
                          "→ không thể vừa làm mẹ (cây chỉ 1 cấp), bỏ qua cả nhóm")
            continue
        for child in children:
            if child not in units:
                issues.append(f"{username}: “{child}” không có trong danh mục")
            elif units.get(child):
                issues.append(f"“{child}” đã có mẹ “{units[child]}” — giữ nguyên, không ghi đè")
            elif child in already_parent:
                issues.append(f"“{child}” đang là công ty MẸ của đơn vị khác → không cho làm con")
            elif child in proposals and proposals[child] != parent:
                issues.append(f"⚠ “{child}”: {claimed_by[child]} nói mẹ là “{proposals[child]}”, "
                              f"{username} nói “{parent}” — BỎ QUA, admin tự chọn")
                proposals.pop(child)
            elif child not in proposals:
                proposals[child] = parent
                claimed_by[child] = username
    return proposals, issues, len(accounts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="Ghi thật (mặc định chỉ chạy thử)")
    args = ap.parse_args()

    with psycopg.connect(os.environ.get("DATABASE_URL", DEFAULT_DSN)) as conn, conn.cursor() as cur:
        proposals, issues, n_accounts = _proposals(cur)
        if args.commit:
            for child, parent in proposals.items():
                cur.execute("UPDATE member_unit SET parent_company = %s "
                            " WHERE name = %s AND parent_company IS NULL", (parent, child))
            conn.commit()

    print(f"=== Dựng cây công ty mẹ–con từ tài khoản — "
          f"{'ĐÃ GHI' if args.commit else 'CHẠY THỬ (chưa ghi)'} ===")
    by_parent: dict[str, list[str]] = {}
    for child, parent in proposals.items():
        by_parent.setdefault(parent, []).append(child)
    for parent, children in sorted(by_parent.items()):
        print(f"  {parent} (mẹ) → {', '.join(sorted(children))}")
    if not proposals:
        print(f"  (không gán thêm gì — đã quét {n_accounts} tài khoản gán nhiều đơn vị)"
              if n_accounts else
              "  (không có tài khoản nào gán nhiều đơn vị — chưa dựng được nhóm nào)")
    if issues:
        print(f"\n⚠ {len(issues)} chỗ cần admin xử lý tay ở màn Đơn vị thành viên:")
        for s in issues:
            print(f"    - {s}")
    if not args.commit:
        print("\nChạy lại với --commit để ghi thật.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
