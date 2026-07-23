"""Helper dùng chung cho các script import lịch sử vào fact_price.

- Kết nối DB qua DATABASE_URL (mặc định trùng apps/api config).
- Upsert idempotent theo ĐÚNG khóa chính của fact_price: (as_of, source, grade, price_type)
  — `contract` KHÔNG nằm trong khóa (bỏ từ 0.2.29), ghi lại cùng khóa sẽ đè giá cũ.
- Parse số/khoảng giá ("407-412" -> trung điểm), parse ngày dd/mm.
- Dựng lại NĂM khi tiêu đề chỉ có dd/mm (năm Excel lưu ngầm không đáng tin):
  neo cột cuối = last_year, lùi sang trái mỗi khi gặp mốc Tháng12 -> Tháng1.
"""
from __future__ import annotations

import datetime
import os
import re
from pathlib import Path

DEFAULT_DSN = "postgresql://vrg:changeme@localhost:5433/vrg_caosu"
MIN_YEAR = 2024  # chỉ import từ 2024 trở đi (theo yêu cầu)

# Thư mục docs (tương đối theo repo) — để script chạy được trên mọi máy/production.
# scripts/import-history/_lib.py -> repo root -> docs.  Đổi qua env BIEU_MAU_DOCS nếu cần.
DOCS = Path(os.environ.get("BIEU_MAU_DOCS", Path(__file__).resolve().parents[2] / "docs"))


def get_dsn() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DSN)


_UPSERT = """
INSERT INTO fact_price
  (as_of, source, grade, contract, price_type, price, currency, unit, source_ts)
VALUES
  (%(as_of)s, %(source)s, %(grade)s, %(contract)s, %(price_type)s,
   %(price)s, %(currency)s, %(unit)s, %(source_ts)s)
ON CONFLICT (as_of, source, grade, price_type) DO UPDATE SET
  contract = EXCLUDED.contract, price = EXCLUDED.price, currency = EXCLUDED.currency,
  unit = EXCLUDED.unit, source_ts = EXCLUDED.source_ts, ingested_at = now();
"""


def upsert(rows: list[dict], dry_run: bool = False) -> int:
    """Ghi danh sách bản ghi (bỏ price None). Trả số bản ghi. dry_run = chỉ đếm."""
    rows = [r for r in rows if r.get("price") is not None]
    if dry_run or not rows:
        return len(rows)
    import psycopg

    with psycopg.connect(get_dsn()) as conn:
        with conn.cursor() as cur:
            cur.executemany(_UPSERT, rows)
        conn.commit()
    return len(rows)


# KHÔNG bắt dấu trừ ở đây: trong nguồn, gạch nối giữa 2 số LUÔN là dấu khoảng giá
# ('538-569'), không phải số âm. Regex cũ `-?\d+` đọc '538-569' thành [538, -569] →
# trung điểm ra -15,5 (giá mủ không bao giờ âm). Giá âm không tồn tại ở các sheet này.
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def parse_number(v) -> float | None:
    """'404' -> 404; '407-412'/'390 – 395' -> trung điểm; số -> số; rỗng/chữ -> None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("–", "-").replace("—", "-")
    nums = [float(x.replace(",", ".")) for x in _NUM.findall(s)]
    if not nums:
        return None
    if len(nums) >= 2:
        return round((nums[0] + nums[1]) / 2.0, 4)
    return nums[0]


def daymonth(v) -> tuple[int, int] | None:
    """Lấy (ngày, tháng) từ ô Date hoặc chuỗi 'd/m'. Bỏ qua năm (không tin năm ngầm)."""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return (v.day, v.month)
    m = re.match(r"^\s*(\d{1,2})[/.\-](\d{1,2})", str(v) if v is not None else "")
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if 1 <= d <= 31 and 1 <= mo <= 12:
            return (d, mo)
    return None


def reconstruct_years(dms: list[tuple[int, int]], last_year: int = 2026) -> list[int]:
    """Gán năm cho chuỗi (ngày,tháng) khi tiêu đề chỉ có dd/mm.

    Neo cột cuối = last_year; đi ngược sang trái, lùi 1 năm khi tháng nhảy lên >=6
    (dấu hiệu vượt mốc Tháng12 -> Tháng1).
    """
    n = len(dms)
    years = [last_year] * n
    for i in range(n - 2, -1, -1):
        # Mốc năm thật: ô trái là cuối năm (>=Th10) và ô phải là đầu năm (<=Th3).
        boundary = dms[i][1] >= 10 and dms[i + 1][1] <= 3
        years[i] = years[i + 1] - 1 if boundary else years[i + 1]
    return years
