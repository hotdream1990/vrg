"""Dựng 2 ảnh PNG kiểu bảng Excel về tình trạng nhập liệu của các đơn vị thành viên.

Chạy 1 lệnh: lấy số liệu (prod qua SSH, hoặc DB local) → dựng HTML → chụp PNG.
    uv run --directory apps/api python .claude/skills/bao-cao-nhap-lieu/scripts/make-report.py

Ảnh A = ai chưa nộp / nộp thiếu · ảnh B = ai nhập sai đơn vị tính.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from datetime import date, timedelta

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]                                  # gốc repo VRG
DEPLOY_ENV = ROOT / ".claude/skills/deploy/dokploy-target.local.env"

GRADE_LABEL = {"purchase": "Mủ nước", "purchase_cup": "Mủ chén"}


# ── Lấy số liệu ───────────────────────────────────────────────────────────────
def read_env(path: pathlib.Path) -> dict[str, str]:
    """Đọc file env kiểu KEY=VALUE (bỏ chú thích, bỏ nháy) — dùng chung với skill deploy."""
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def run_sql(sql: str, local: bool) -> str:
    """Chạy SQL rồi trả stdout. Prod đi qua SSH vì DB không mở ra ngoài."""
    if local:
        cmd = ["psql", "-h", "localhost", "-p", "5433", "-U", "vrg", "-d", "vrg_caosu", "-tA", "-f", "-"]
        env = {"PGPASSWORD": "changeme", "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"}
    else:
        if not DEPLOY_ENV.exists():
            sys.exit(f"Thiếu {DEPLOY_ENV} — xem skill deploy để tạo (file này gitignored).")
        e = read_env(DEPLOY_ENV)
        remote = (f"docker exec -i {e['DB_CONTAINER']} "
                  f"psql -U {e['DB_USER']} -d {e['DB_NAME']} -tA -f -")
        cmd = ["sshpass", "-e", "ssh", "-o", "StrictHostKeyChecking=no",
               "-p", e["SSH_PORT"], f"{e['SSH_USER']}@{e['SSH_HOST']}", remote]
        env = {"SSHPASS": e["SSH_PASSWORD"], "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"}
    res = subprocess.run(cmd, input=sql, capture_output=True, text=True, env=env)
    if res.returncode != 0:
        sys.exit(f"Lỗi chạy SQL:\n{res.stderr.strip()}")
    return res.stdout


def collect(days: int, local: bool) -> dict[str, list]:
    """Gom kết quả theo nhóm: A tình trạng nộp · B giá mủ sai đơn vị · C giá bán sai · D thiếu đơn giá."""
    sql = (HERE / "collect.sql").read_text().replace(":days", str(days))
    rows = [ln.split("|") for ln in run_sql(sql, local).splitlines() if ln.strip()]
    return {g: [r[1:] for r in rows if r[0] == g] for g in "ABCDE"}


# ── Dựng HTML ─────────────────────────────────────────────────────────────────
CSS = """
<style>
  * { box-sizing: border-box; }
  body { margin: 0; padding: 26px; background: #fff;
         font: 13px/1.45 'Segoe UI', system-ui, -apple-system, sans-serif; color: #14261d; }
  h1 { font-size: 19px; margin: 0 0 2px; }
  h2 { font-size: 15px; margin: 20px 0 6px; color: #14432b; }
  .sub { color: #5f6f67; font-size: 12.5px; margin-bottom: 14px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #b9c6be; padding: 5px 9px; }
  thead th { background: #1f7a4d; color: #fff; font-weight: 600; font-size: 12.5px;
             text-align: center; border-color: #16603b; }
  tbody tr:nth-child(even) td { background: #f4f8f5; }
  td.stt { width: 34px; text-align: center; color: #6b7a72; }
  td.mark { text-align: center; font-weight: 700; width: 118px; }
  .bad { color: #c0392b; } .good { color: #1f7a4d; } .na { color: #9aa8a0; }
  .grp td { background: #e6efe9 !important; font-weight: 700; color: #14432b; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .note { margin-top: 12px; font-size: 12px; color: #5f6f67; font-style: italic; }
  .empty { padding: 10px 2px; color: #5f6f67; font-style: italic; }
</style>
"""


def vn(n: float) -> str:
    """Số kiểu Việt Nam: chấm ngăn nghìn."""
    return f"{int(n):,}".replace(",", ".")


def mark(v: str) -> str:
    """1 ô tình trạng: '-' = không áp dụng · 0 = chưa nhập · n = đã nộp n ngày."""
    if v == "-":
        return '<td class="mark na">không áp dụng</td>'
    return ('<td class="mark bad">✗ chưa nhập</td>' if int(v) == 0
            else f'<td class="mark good">✓ {v} ngày</td>')


def page_missing(rows_a: list, rows_d: list, days: int) -> str:
    """Ảnh A: KHÔNG NỘP GÌ (thiếu mọi biểu áp dụng) và THIẾU MỘT PHẦN (thiếu ít nhất 1 biểu)."""
    def missing(v: str) -> bool:      # '-' = không áp dụng → không tính là thiếu
        return v != "-" and int(v) == 0

    full = [a for a in rows_a if all(missing(v) or v == "-" for v in a[1:])]
    part = [a for a in rows_a if a not in full and any(missing(v) for v in a[1:])]
    today = date.today()
    ky = f"{(today - timedelta(days=days - 1)).strftime('%d/%m')} – {today.strftime('%d/%m/%Y')}"

    def block(title: str, items: list) -> str:
        out = [f'<tr class="grp"><td colspan="4">{title} — {len(items)} đơn vị</td></tr>']
        for i, (name, pur, con) in enumerate(items, 1):
            out.append(f'<tr><td class="stt">{i}</td><td>{name}</td>{mark(pur)}{mark(con)}</tr>')
        return "".join(out)

    # Thiếu đơn giá là lỗi NẰM TRONG biểu Thu mua (nhập sản lượng, bỏ trống ô đơn giá) → bảng riêng,
    # không phải một mục nộp riêng.
    d = "".join(
        f'<tr><td class="stt">{i}</td><td>{r[0]}</td>'
        f'<td class="mark">{r[1][8:10]}/{r[1][5:7]}/{r[1][:4]}</td></tr>'
        for i, r in enumerate(rows_d, 1))
    d_table = f"""
<h2>Có tổ chức thu mua nhưng chưa nhập đơn giá — {len(rows_d)} ngày</h2>
<table style="width:auto;min-width:420px"><thead><tr><th>#</th>
  <th style="text-align:left">Đơn vị</th><th>Ngày</th></tr></thead><tbody>{d}</tbody></table>
<div class="note">Đơn giá mủ nước/mủ chén nhập ngay trong biểu Thu mua. Ngày không tổ chức thu mua
  thì không cần giá — các ngày dưới đây đã có tổ chức mua nhưng ô đơn giá còn trống.</div>""" if d else ""

    return f"""{CSS}
<h1>ĐƠN VỊ CHƯA NHẬP LIỆU</h1>
<div class="sub">Kỳ {ky} · {len(rows_a)} đơn vị đang hoạt động ·
  nguồn: Hệ thống Dự báo &amp; Quản trị Giá Cao su</div>
<table>
  <thead><tr><th>#</th><th style="text-align:left">Đơn vị</th>
    <th>Báo cáo thu mua</th><th>Tiêu thụ – Tồn kho</th></tr></thead>
  <tbody>{block("KHÔNG NỘP GÌ TRONG KỲ", full)}{block("THIẾU MỘT PHẦN", part)}</tbody>
</table>
<div class="note">“không áp dụng” = đơn vị không được giao kế hoạch thu mua nên không phải nộp
  biểu Thu mua.</div>
{d_table}
"""


def page_wrong(rows_b: list, rows_c: list) -> str:
    """Ảnh B: nhập sai đơn vị tính — giá mủ nguyên liệu (đ/độ) và giá bán (triệu đ/tấn)."""
    b = "".join(
        f'<tr><td class="stt">{i}</td><td>{r[0]}</td>'
        f'<td>{GRADE_LABEL.get(r[1], r[1])}</td>'
        f'<td class="num bad">{vn(float(r[2]))}</td><td class="num">{r[3]}</td></tr>'
        for i, r in enumerate(rows_b, 1))
    c = "".join(
        f'<tr><td class="stt">{i}</td><td>{r[0]}</td>'
        f'<td>{r[2][8:10]}/{r[2][5:7]}'
        f'{"" if r[2] == r[3] else " – " + r[3][8:10] + "/" + r[3][5:7]}</td>'
        f'<td class="num bad">{vn(float(r[4]))}{" USD" if "USD" in r[5] else ""}</td>'
        f'<td class="num">{r[1]}</td></tr>'
        for i, r in enumerate(rows_c, 1))
    # Dòng USD mà thiếu tỷ giá thì doanh thu không quy ra VND được → nêu đích danh đơn vị.
    no_fx = [r[0] for r in rows_c if "USD" in r[5] and len(r) > 6 and r[6] == "t"]
    note = (f'<div class="note">{", ".join(no_fx)} nhập giá bằng USD/tấn và chưa có tỷ giá → '
            "doanh thu không tính được; đề nghị xác nhận lại cả đơn giá lẫn tỷ giá.</div>"
            if no_fx else "")
    none = '<div class="empty">Không có đơn vị nào sai — mọi giá đang trong mặt bằng hợp lý.</div>'
    return f"""{CSS}
<h1>ĐƠN VỊ NHẬP SAI ĐƠN VỊ TÍNH</h1>
<div class="sub">Số liệu còn sai trên hệ thống lúc {date.today().strftime('%d/%m/%Y')} —
  đề nghị các đơn vị mở lại phiếu và sửa</div>

<h2>1. Giá mủ nguyên liệu — phải nhập theo ĐỒNG/ĐỘ (mặt bằng 100 – 1.500)</h2>
{f'''<table><thead><tr><th>#</th><th style="text-align:left">Đơn vị</th><th>Loại mủ</th>
  <th>Giá đã nhập</th><th>Số ô sai</th></tr></thead><tbody>{b}</tbody></table>''' if b else none}

<h2>2. Giá bán ở biểu Tiêu thụ — phải nhập theo TRIỆU ĐỒNG/TẤN (mặt bằng 40 – 70)</h2>
{f'''<table><thead><tr><th>#</th><th style="text-align:left">Đơn vị</th><th>Ngày</th>
  <th>Giá đã nhập</th><th>Số dòng sai</th></tr></thead><tbody>{c}</tbody></table>''' if c else none}
{note}
"""


def page_stock_missing(rows_e: list, days: int) -> str:
    """Ảnh C: RIÊNG biểu Tồn kho, cùng khuôn với ảnh A (chia nhóm, không phải ma trận).

    Chia 2 nhóm để đốc thúc đúng đối tượng: đơn vị **không nhập ngày nào** (cần gọi ngay) và đơn vị
    **thiếu một phần** (chỉ cần nhắc bù ngày trống). Nhóm sau liệt kê luôn ngày còn thiếu.
    """
    today = date.today()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    ky = f"{dates[0][8:10]}/{dates[0][5:7]} – {today.strftime('%d/%m/%Y')}"
    dm = lambda d: f"{d[8:10]}/{d[5:7]}"  # noqa: E731

    units = []
    for name, region, done_csv in rows_e:
        done = set(filter(None, done_csv.split(",")))
        miss = [d for d in dates if d not in done]
        units.append({"name": name, "region": region or "—", "miss": miss,
                      "filled": len(dates) - len(miss)})
    none = [u for u in units if u["filled"] == 0]
    part = sorted([u for u in units if u["miss"] and u["filled"]],
                  key=lambda u: (-len(u["miss"]), u["name"]))
    filled_total = sum(u["filled"] for u in units)
    total = len(dates) * len(units)

    def block(title: str, items: list, show_days: bool) -> str:
        out = [f'<tr class="grp"><td colspan="5">{title} — {len(items)} đơn vị</td></tr>']
        for i, u in enumerate(items, 1):
            cell = ('<td class="mark bad">✗ chưa nhập</td>' if not u["filled"]
                    else f'<td class="mark good">✓ {u["filled"]}/{len(dates)} ngày</td>')
            miss_txt = ", ".join(dm(d) for d in u["miss"]) if show_days else ""
            out.append(f'<tr><td class="stt">{i}</td><td>{u["name"]}</td>'
                       f'<td class="reg">{u["region"]}</td>{cell}'
                       f'<td class="days">{miss_txt}</td></tr>')
        return "".join(out)

    return f"""{CSS}
<style>
  td.reg {{ color: #5f6f67; font-size: 12px; white-space: nowrap; }}
  td.days {{ color: #c0392b; font-size: 12px; }}
  tbody td:nth-child(2) {{ white-space: nowrap; }}
</style>
<h1>ĐƠN VỊ CHƯA NHẬP TỒN KHO</h1>
<div class="sub">Kỳ {ky} · {len(units)} đơn vị đang hoạt động · đã nhập {vn(filled_total)}/{vn(total)}
  lượt ({round(filled_total / total * 100) if total else 0}%) ·
  nguồn: Hệ thống Dự báo &amp; Quản trị Giá Cao su</div>
<table>
  <thead><tr><th>#</th><th style="text-align:left">Đơn vị</th><th>Khu vực</th>
    <th>Tồn kho</th><th style="text-align:left">Ngày còn thiếu</th></tr></thead>
  <tbody>{block(f"KHÔNG NHẬP NGÀY NÀO TRONG {len(dates)} NGÀY", none, False)}
         {block("THIẾU MỘT PHẦN", part, True)}</tbody>
</table>
<div class="note">Ngày đơn vị tích “không phát sinh tồn kho để khai” vẫn được tính là ĐÃ NỘP.
  Đơn vị nhập đủ cả kỳ không có tên trong bảng này.</div>
"""


# ── Chụp ảnh ──────────────────────────────────────────────────────────────────
def shoot(pages: list[tuple], out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Mỗi trang: (tên file, html[, bề ngang px]). Bảng nhiều cột phải nới bề ngang, không thì tên
    đơn vị vắt 4-5 dòng và ảnh cao gấp mấy lần — gửi Zalo không ai đọc nổi."""
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # device_scale_factor=2 → ảnh nét, đọc được số khi gửi qua Zalo/Excel.
        # Viewport để THẤP: ảnh full_page không bao giờ ngắn hơn viewport, để cao thì bảng ít dòng
        # sẽ thừa một mảng trắng dưới đáy.
        page = browser.new_page(viewport={"width": 1000, "height": 200}, device_scale_factor=2)
        for entry in pages:
            name, html = entry[0], entry[1]
            page.set_viewport_size({"width": entry[2] if len(entry) > 2 else 1000, "height": 200})
            page.set_content(html)
            page.wait_for_timeout(250)
            path = out_dir / name
            page.screenshot(path=str(path), full_page=True)
            made.append(path)
        browser.close()
    return made


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7, help="số ngày của kỳ xét đã nộp (mặc định 7)")
    ap.add_argument("--out", default="plans/visuals", help="thư mục lưu ảnh (mặc định plans/visuals)")
    ap.add_argument("--local", action="store_true", help="lấy số liệu ở DB local thay vì prod")
    ap.add_argument("--only", choices=("all", "stock"), default="all",
                    help="'stock' = chỉ ảnh ma trận Tồn kho theo ngày (mặc định: cả 3 ảnh)")
    args = ap.parse_args()

    g = collect(args.days, args.local)
    out_dir = pathlib.Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    # 1500px: đủ cho 14 cột ngày + tên đơn vị nằm gọn 1 dòng (ngày dài hơn thì nới thêm).
    pages = [("C-don-vi-chua-nhap-ton-kho.png", page_stock_missing(g["E"], args.days), 1200)]
    if args.only == "all":
        pages = [("A-don-vi-chua-nhap-lieu.png", page_missing(g["A"], g["D"], args.days)),
                 ("B-don-vi-nhap-sai-don-vi-tinh.png", page_wrong(g["B"], g["C"]))] + pages
    made = shoot(pages, out_dir)
    print(f"{len(g['A'])} đơn vị đang hoạt động · {len(g['D'])} ngày thiếu đơn giá · "
          f"{len(g['B'])} ô giá mủ sai đơn vị · {len(g['C'])} đơn vị sai giá bán")
    for p in made:
        print("đã tạo", p)


if __name__ == "__main__":
    main()
