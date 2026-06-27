"""Import tồn kho Tập đoàn từ báo cáo tuần (PDF chị Hạnh) vào fact_inventory.

Mỗi file "... Bao cao chi tiet den DD.MM.YYYY.pdf" có bảng TỒN KHO THÀNH PHẨM; dòng
"Tổng cộng" trên trang có header "đã ký HĐ" cho 2 số cuối = Tồn kho + Tồn kho đã có HĐ (tấn).

Chạy:
  uv run --with pdfplumber --with "psycopg[binary]" python import_inventory.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re

import pdfplumber

import _lib

PDF_DIR = _lib.DOCS / "bieu-mau" / "Hạnh"
_DATE_RE = re.compile(r"den\s*(\d{1,2})[._](\d{1,2})[._](\d{4})")
_TOTAL_RE = re.compile(r"[Tt]ổng cộng")


def parse_date(filename: str) -> str | None:
    m = _DATE_RE.search(filename)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_inventory(path) -> tuple[int, int] | None:
    """(tồn_kho, tồn_kho_đã_có_HĐ) từ dòng Tổng cộng lớn nhất trên trang bảng tồn kho."""
    cands: list[tuple[int, int]] = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            t = pg.extract_text() or ""
            if "đã ký" not in t and "hợp đồng" not in t.lower():  # chỉ bảng tồn kho
                continue
            for ln in t.split("\n"):
                if not _TOTAL_RE.search(ln):
                    continue
                # số nguyên (dot = ngăn nghìn); bỏ token thập phân ',xx' (bảng doanh thu)
                vals = [int(tk.replace(".", "")) for tk in re.findall(r"\d[\d.]*(?:,\d+)?", ln)
                        if "," not in tk]
                big = [v for v in vals if v >= 100]
                if len(big) >= 2:
                    cands.append((big[-2], big[-1]))
    return max(cands, key=lambda c: c[0]) if cands else None


def collect() -> list[dict]:
    rows: dict[str, dict] = {}  # khử trùng theo as_of (giữ file mới nhất)
    for path in sorted(PDF_DIR.rglob("*.pdf")):
        name = path.name
        if "chi tiet" not in name.lower() and "chi tiết" not in name.lower():
            continue
        as_of = parse_date(name)
        if not as_of or int(as_of[:4]) < _lib.MIN_YEAR:
            continue
        try:
            inv = parse_inventory(path)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip] {name}: {e}")
            inv = None
        if not inv or inv[0] < 5000:
            print(f"  [bỏ] {name}: không đọc được tồn kho hợp lệ ({inv})")
            continue
        rows[as_of] = {"as_of": as_of, "ton_kho": inv[0], "ton_kho_hd": inv[1],
                       "note": f"Báo cáo tuần ({name})", "source": "hanh_weekly"}
    return sorted(rows.values(), key=lambda r: r["as_of"])


def upsert(rows: list[dict], dry: bool) -> int:
    if dry or not rows:
        return len(rows)
    import psycopg
    with psycopg.connect(_lib.get_dsn()) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS fact_inventory (as_of date PRIMARY KEY, "
            "ton_kho double precision, ton_kho_hd double precision, note text, "
            "source text NOT NULL DEFAULT 'hanh_weekly', ingested_at timestamptz NOT NULL DEFAULT now())")
        conn.cursor().executemany(
            "INSERT INTO fact_inventory (as_of, ton_kho, ton_kho_hd, note, source) "
            "VALUES (%(as_of)s, %(ton_kho)s, %(ton_kho_hd)s, %(note)s, %(source)s) "
            "ON CONFLICT (as_of) DO UPDATE SET ton_kho=EXCLUDED.ton_kho, "
            "ton_kho_hd=EXCLUDED.ton_kho_hd, note=EXCLUDED.note, ingested_at=now()", rows)
        conn.commit()
    return len(rows)


def run(dry: bool) -> int:
    rows = collect()
    n = upsert(rows, dry)
    tag = "(dry-run) " if dry else ""
    if rows:
        print(f"[inventory] {n} tuần {tag}({rows[0]['as_of']} → {rows[-1]['as_of']})")
    else:
        print("[inventory] không có dữ liệu")
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    run(a.dry_run)
