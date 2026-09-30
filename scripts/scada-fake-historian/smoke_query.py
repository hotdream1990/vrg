"""Smoke test SCADA giả lập: chạy đúng 2 dạng truy vấn ứng dụng VRG sẽ gửi (qua pymssql, login scada_ro).

Chạy:  uv run --with pymssql python scripts/scada-fake-historian/smoke_query.py
Biến môi trường (tuỳ chọn): SCADA_FAKE_HOST, SCADA_FAKE_PORT, SCADA_FAKE_RO_PASSWORD (mặc định dev-only).
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pymssql

HOST = os.environ.get("SCADA_FAKE_HOST", "localhost")
PORT = int(os.environ.get("SCADA_FAKE_PORT", "14330"))
PASSWORD = os.environ.get("SCADA_FAKE_RO_PASSWORD", "ScadaRo!Dev2026")  # dev-only
TAGS = "[PM_EnergyReal0], [PM_EnergyReal1], [PM_EnergyReal2], [PM_EnergyReal3], [Water_TotalVolume], [Packing_BaleCount]"

# Nguyên văn dạng ứng dụng gửi: OPENQUERY + nháy đơn nhân đôi
Q_HOURLY = f"""SELECT * FROM OPENQUERY(INSQL, 'SELECT DateTime, {TAGS}
 FROM WideHistory
 WHERE wwRetrievalMode = ''Cyclic'' AND wwResolution = 3600000
 AND wwQualityRule = ''Extended'' AND wwVersion = ''Latest''
 AND DateTime >= ''2026-09-01 00:00:00'' AND DateTime <= GetDate()')"""
Q_HOURLY_FIXED = Q_HOURLY.replace("DateTime <= GetDate()", "DateTime <= ''2026-10-01 00:00:00''")
Q_HOURLY_SUBSET = """SELECT * FROM OPENQUERY(INSQL, 'SELECT DateTime, [Water_TotalVolume], [Packing_BaleCount]
 FROM WideHistory
 WHERE wwRetrievalMode = ''Cyclic'' AND wwResolution = 3600000
 AND wwQualityRule = ''Extended'' AND wwVersion = ''Latest''
 AND DateTime >= ''2026-09-01 00:00:00'' AND DateTime <= GetDate()')"""
Q_LATEST = f"""SELECT * FROM OPENQUERY(INSQL, 'SELECT DateTime, {TAGS}
 FROM WideHistory
 WHERE wwRetrievalMode = ''Cyclic'' AND wwResolution = 60000
 AND wwQualityRule = ''Extended'' AND wwVersion = ''Latest''
 AND DateTime >= DateAdd(mi,-10,GetDate()) AND DateTime <= GetDate()')"""

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(f"  [{'OK ' if ok else 'FAIL'}] {msg}")
    if not ok:
        failures.append(msg)


def kwh(row) -> float | None:
    """Ghép 4 thanh ghi 16-bit -> kWh; mask & 0xFFFF vì thanh ghi có thể bị đọc thành số âm."""
    regs = row[1:5]
    if any(r is None for r in regs):
        return None
    r0, r1, r2, r3 = (int(r) & 0xFFFF for r in regs)
    return ((r0 << 48) | (r1 << 32) | (r2 << 16) | r3) / 1000


def fmt(row) -> str:
    k = kwh(row) if len(row) >= 7 else None
    return f"{row[0]}  raw={list(row[1:])}" + (f"  -> {k:,.3f} kWh" if k is not None else "")


def show(rows, n=3) -> None:
    for r in rows[:n]:
        print("    ", fmt(r))
    if len(rows) > n:
        print("     ...")
        for r in rows[-n:]:
            print("    ", fmt(r))


def main() -> int:
    conn = pymssql.connect(server=HOST, port=PORT, user="scada_ro", password=PASSWORD,
                           database="Runtime", login_timeout=15, timeout=60)
    cur = conn.cursor()
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)

    print("1) Mẫu theo giờ, 2026-09-01 -> GetDate()")
    cur.execute(Q_HOURLY)
    rows = cur.fetchall()
    expected = int((now.replace(minute=0, second=0, microsecond=0) - datetime(2026, 9, 1)) / timedelta(hours=1)) + 1
    print(f"  {len(rows)} dòng (kỳ vọng ~{expected}); giờ VN hiện tại {now:%Y-%m-%d %H:%M}")
    show(rows)
    check(abs(len(rows) - expected) <= 1, "số dòng theo giờ khớp số giờ từ 2026-09-01 tới bây giờ")
    check(all(rows[i][0] < rows[i + 1][0] for i in range(len(rows) - 1)), "DateTime tăng dần")
    check(all(r[0] <= now + timedelta(minutes=1) for r in rows), "không lộ mốc tương lai")
    check(any(int(r[4]) < 0 for r in rows if r[4] is not None), "R3 có mốc âm (int16 có dấu) - ứng dụng phải mask")
    check(all(v == int(v) for r in rows for v in r[1:5] if v is not None), "4 thanh ghi điện đều là số nguyên")
    check(all(-32768 <= r[4] <= 32767 and 0 <= r[3] <= 65535 for r in rows if r[4] is not None), "R3 trong khoảng int16, R2 trong khoảng uint16")
    k = [kwh(r) for r in rows]
    valid = [x for x in k if x is not None]
    check(all(a <= b for a, b in zip(valid, valid[1:])), "kWh ghép (đã mask) không giảm")
    at = {r[0]: r for r in rows}
    k_sep1, k_last = kwh(rows[0]), kwh(rows[-1])
    print(f"  kWh 2026-09-01 00:00 = {k_sep1:,.3f} ; kWh mốc cuối = {k_last:,.3f}")
    check(179_000 <= k_sep1 <= 181_000, "điện đầu 09/2026 ~180.000 kWh")
    trap_w = at.get(datetime(2026, 9, 12, 0, 0))
    check(trap_w is not None and trap_w[5] is None, "bẫy: 2026-09-12 00:00 Water_TotalVolume = NULL")
    day20 = [r for r in rows if r[0].date() == datetime(2026, 9, 20).date()]
    check(len(day20) == 24 and all(r[6] is None for r in day20), "bẫy: cả ngày 2026-09-20 Packing_BaleCount = NULL")

    print("2) Cùng truy vấn, chặn trên cố định 2026-10-01 00:00")
    cur.execute(Q_HOURLY_FIXED)
    fixed = cur.fetchall()
    print(f"  {len(fixed)} dòng"); show(fixed, 2)
    check(len(fixed) == len(rows), "chặn trên cố định (quá khứ/tương lai) vẫn ẩn tương lai")

    print("3) Chỉ một tập con cột tag (Water, Bale)")
    cur.execute(Q_HOURLY_SUBSET)
    sub = cur.fetchall()
    print(f"  {len(sub)} dòng; dòng đầu: {sub[0]}")
    check(len(sub) == len(rows) and len(sub[0]) == 3, "tập con cột trả đủ dòng, đúng 3 cột")

    print("4) Số mới nhất (mẫu phút, 10 phút gần nhất)")
    cur.execute(Q_LATEST)
    latest = cur.fetchall()
    print(f"  {len(latest)} dòng"); show(latest, 2)
    check(len(latest) >= 1, "truy vấn 'số mới nhất' trả >= 1 dòng")
    check(all(v == int(v) for r in latest for v in r[1:5] if v is not None), "mốc phút: thanh ghi điện là số nguyên")
    check([r[0] for r in latest] == sorted(r[0] for r in latest), "mốc phút tăng dần (dòng cuối = mới nhất)")
    check(all(r[1] is not None and r[5] is not None and r[6] is not None for r in latest), "số mới nhất có đủ điện/nước/bành")
    if latest:
        kl = kwh(latest[-1])
        print(f"  kWh mới nhất = {kl:,.3f}")
        check(kl >= k_last - 1e-6 or k_last is None, "kWh mới nhất >= mốc giờ trước đó")

    conn.close()
    print("\nKẾT QUẢ:", "ĐẠT" if not failures else f"{len(failures)} lỗi")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
