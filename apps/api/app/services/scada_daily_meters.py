"""Chỉ số điện · nước · số bành THEO NGÀY từ mẫu Historian — thuần hàm (nhận `now` để test được).

Luật (chốt 30/09/2026, xem plans/260930-nha-may-thong-minh-scada/):
  - Đầu ngày D = mẫu đúng D 00:00; cuối ngày D = mẫu đúng D+1 00:00 (hôm nay = số mới nhất).
    Tiêu thụ = cuối − đầu ⇒ cộng các ngày = cả kỳ, không rơi phần tiêu thụ giữa hai lần ghi.
  - Mẫu phút (truy vấn số mới nhất) được GỘP vào chuỗi mẫu giờ trước khi chia ngày → hôm nay có số
    ngay cả khi Historian chưa trả mẫu giờ nào của hôm nay.
  - Mốc 00:00 trống → dùng mẫu có số gần nhất TRONG ngày, cờ `partial`. KHÔNG BAO GIỜ mượn mẫu
    của ngày khác (nguyên tắc cứng của dự án: không dựng số ngày X bằng số ngày khác).
  - Bộ đếm lũy kế chỉ được tăng: hai mẫu kề nhau trong ngày GIẢM quá `RESET_DROP_RATIO` (đặt lại
    về 0, đặt lại theo ca, thay đồng hồ) → tiêu thụ null, cờ `reset`. Lùi nhỏ hơn = nhiễu đo, bỏ qua.
"""

from __future__ import annotations

from bisect import bisect_left
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

#: key → (nhãn, đơn vị) theo đúng thứ tự hiển thị.
METRICS: dict[str, tuple[str, str]] = {
    "energy": ("Điện năng", "kWh"),
    "water": ("Nước", "m³"),
    "bales": ("Số bành", "bành"),
}
#: Cờ ưu tiên cao → thấp (một ô chỉ mang MỘT cờ).
FLAG_ORDER = ("no_data", "reset", "in_progress", "partial")
#: Giảm dưới tỷ lệ này (so với số trước) = NHIỄU đo, không phải đặt lại bộ đếm. Đo thật 30/09/2026 ở
#: Phú Riềng: đồng hồ nước lùi 0,003 m³ lúc 05:00 ngày 08/09 ("giảm bất kỳ" gắn reset oan, mất 158 m³);
#: thanh ghi điện lệch nhịp ≤ 65,536 kWh ≈ 0,03% lũy kế. Đặt lại thật (về 0, theo ca) giảm ~100%.
RESET_DROP_RATIO = 0.01

Sample = tuple[datetime, dict[str, float | None]]
Latest = dict[str, tuple[datetime, float]]


def vn_now() -> datetime:
    """Giờ Việt Nam, naive (VN/Lào/Campuchia cùng UTC+7 — đồng hồ của nhà máy)."""
    return datetime.now(VN_TZ).replace(tzinfo=None)


def iso(ts: datetime | None) -> str | None:
    return ts.isoformat(timespec="seconds") if ts else None  # giờ nhà máy, không kèm múi


def factory_metrics(factory: dict) -> list[str]:
    """Chỉ số của nhà máy = chỉ số đã khai tag (điện cần đúng 1 hoặc 4 tag)."""
    out = []
    if len(factory.get("energy_tags") or []) in (1, 4):
        out.append("energy")
    out += [m for m in ("water", "bales") if factory.get(f"{m}_tag")]
    return out


def combine_energy(regs: list[float | None]) -> float | None:
    """4 thanh ghi 16-bit [R0..R3] (cao → thấp) → kWh; 1 tag = đã là kWh. `& 0xFFFF` sửa thanh ghi
    Historian lưu thành số âm; int Python vì bigint T-SQL tràn ở R0 << 48. Thiếu thanh ghi → None."""
    if len(regs) not in (1, 4) or any(v is None for v in regs):
        return None
    if len(regs) == 1:
        return float(regs[0])
    r0, r1, r2, r3 = (int(round(v)) & 0xFFFF for v in regs)
    return ((r0 << 48) | (r1 << 32) | (r2 << 16) | r3) / 1000


def metric_values(values: dict[str, float | None], factory: dict,
                  metrics: list[str]) -> dict[str, float | None]:
    """Một mẫu thô {tag: giá trị} → {chỉ số: giá trị}; tra tag không phân biệt hoa thường."""
    low = {k.lower(): v for k, v in values.items()}
    out: dict[str, float | None] = {}
    for m in metrics:
        if m == "energy":
            out[m] = combine_energy([low.get(t.lower()) for t in factory["energy_tags"]])
            continue
        v = low.get(str(factory.get(f"{m}_tag") or "").lower())
        out[m] = None if v is None else (int(round(v)) if m == "bales" else float(v))
    return out


def to_samples(raw: list[Sample], factory: dict, metrics: list[str]) -> list[Sample]:
    return sorted(((ts, metric_values(v, factory, metrics)) for ts, v in raw), key=lambda s: s[0])


def latest_of(samples: list[Sample], metrics: list[str]) -> Latest:
    """Số có giá trị MỚI NHẤT của từng chỉ số (mẫu đã sắp tăng dần)."""
    out: Latest = {}
    for ts, vals in samples:
        for m in metrics:
            if vals.get(m) is not None:
                out[m] = (ts, vals[m])
    return out


def round_metric(metric: str, v: float | None) -> float | int | None:
    return None if v is None else (int(round(v)) if metric == "bales" else round(v, 3))


def merge_samples(hourly: list[Sample], minute: list[Sample]) -> list[Sample]:
    """Gộp mẫu phút vào mẫu giờ theo mốc thời gian (bỏ trùng mốc); cùng mốc thì số của mẫu giờ
    thắng, ô trống của mẫu giờ được mẫu phút lấp. Kết quả sắp tăng dần."""
    by_ts: dict[datetime, dict[str, float | None]] = {}
    for ts, vals in [*minute, *hourly]:  # mẫu giờ đi sau → ghi đè
        by_ts.setdefault(ts, {}).update({k: v for k, v in vals.items() if v is not None})
    return sorted(by_ts.items(), key=lambda s: s[0])


def _dropped(prev: float, cur: float) -> bool:
    return prev - cur > abs(prev) * RESET_DROP_RATIO


def _cell(metric: str, keys: list[datetime], values: list[float], day: date, today: date) -> dict:
    """Ô của MỘT chỉ số trong MỘT ngày. `keys`/`values` = mẫu CÓ SỐ của chỉ số, sắp tăng dần."""
    start = datetime.combine(day, time())
    end = start + timedelta(days=1)
    lo, hi = bisect_left(keys, start), bisect_left(keys, end)
    if lo == hi:
        return {"open": None, "open_at": None, "close": None, "close_at": None,
                "used": None, "flag": "no_data"}
    flags: set[str] = set()
    if keys[lo] != start:  # mốc 00:00 trống → mẫu có số đầu tiên trong ngày
        flags.add("partial")
    # Có mẫu ĐÚNG mốc D+1 00:00 → đóng ngày bằng nó, kể cả "hôm nay" khi đồng hồ SCADA nhanh hơn app.
    if hi < len(keys) and keys[hi] == end:
        last = hi
    else:  # không lấy mẫu sau D+1 00:00: hôm nay = số mới nhất, ngày cũ = mẫu cuối TRONG ngày
        last = hi - 1
        flags.add("in_progress" if day == today else "partial")
    # So sau khi làm tròn theo chỉ số → sai số dấu phẩy động không thành "giảm" giả.
    seg = [round_metric(metric, v) for v in values[lo:last + 1]]
    used = None
    if any(_dropped(a, b) for a, b in zip(seg, seg[1:])) or _dropped(seg[0], seg[-1]):
        flags.add("reset")
    else:  # lùi nhỏ (nhiễu) cả ngày → 0 chứ không âm
        used = round_metric(metric, max(seg[-1] - seg[0], 0))
    return {"open": seg[0], "open_at": iso(keys[lo]), "close": seg[-1], "close_at": iso(keys[last]),
            "used": used, "flag": next((f for f in FLAG_ORDER if f in flags), None)}


def _ratio(rows: list[dict], num: str) -> float | None:
    """Suất tiêu hao `num`/bành, chỉ cộng ngày CẢ HAI ô đủ số (flag null) — ngày chưa trọn/thiếu mốc
    làm lệch tỷ lệ. Null khi thiếu chỉ số hoặc tổng số bành = 0."""
    pairs = [(r[num]["used"], r["bales"]["used"]) for r in rows
             if num in r and "bales" in r and r[num]["flag"] is None and r["bales"]["flag"] is None]
    den = sum(b for _, b in pairs)
    return round(sum(a for a, _ in pairs) / den, 3) if pairs and den > 0 else None


def daily_rows(samples: list[Sample], date_from: date, date_to: date, today: date,
               metrics: list[str]) -> list[dict]:
    """Một dòng / ngày (tăng dần), mỗi chỉ số một ô {open, open_at, close, close_at, used, flag}."""
    series = {m: [(ts, v[m]) for ts, v in samples if v.get(m) is not None] for m in metrics}
    cols = {m: ([ts for ts, _ in pts], [v for _, v in pts]) for m, pts in series.items()}
    rows: list[dict] = []
    for i in range((date_to - date_from).days + 1):
        day = date_from + timedelta(days=i)
        row: dict = {"date": day.isoformat()}
        for m in metrics:
            row[m] = _cell(m, *cols[m], day, today)
        row["kwh_per_bale"] = _ratio([row], "energy")
        row["m3_per_bale"] = _ratio([row], "water")
        rows.append(row)
    return rows


def summary(rows: list[dict], latest: Latest, metrics: list[str]) -> dict:
    """Tổng cộng từ số ĐÃ LÀM TRÒN của từng dòng (khớp đúng tổng cột trên bảng) — gồm cả hôm nay,
    ngày thiếu mốc. BQ/ngày CHỈ tính ngày đủ số (flag null): ngày chưa trọn/thiếu mốc kéo lệch BQ.
    Kỳ không có ngày nào có số → total/avg = null (không hiện 0 gây hiểu nhầm là không tiêu thụ)."""
    out: dict = {}
    for m in metrics:
        used = [r[m]["used"] for r in rows if r[m]["used"] is not None]
        complete = [r[m]["used"] for r in rows if r[m]["flag"] is None]
        lt = latest.get(m)
        out[m] = {"latest": round_metric(m, lt[1]) if lt else None,
                  "latest_at": iso(lt[0]) if lt else None,
                  "total": round_metric(m, sum(used)) if used else None,
                  "avg_per_day": round(sum(complete) / len(complete), 3) if complete else None,
                  "days_with_data": len(used), "days_complete": len(complete)}
    return out


def build_report(factory: dict, hourly_raw: list[Sample], latest_raw: list[Sample],
                 date_from: date, date_to: date, now: datetime) -> dict:
    """Ghép toàn bộ phản hồi `/meters/daily` (đúng api-contract.md) từ mẫu thô của Historian."""
    metrics = factory_metrics(factory)
    minute = to_samples(latest_raw, factory, metrics)
    samples = merge_samples(to_samples(hourly_raw, factory, metrics), minute)
    rows = daily_rows(samples, date_from, date_to, now.date(), metrics)
    return {
        "factory": {"id": factory["id"], "name": factory["name"]},
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
        "fetched_at": iso(now.replace(microsecond=0)),
        "metrics": [{"key": m, "label": METRICS[m][0], "unit": METRICS[m][1]} for m in metrics],
        "rows": rows,
        "summary": summary(rows, latest_of(minute, metrics), metrics),
        "intensity": {"kwh_per_bale": _ratio(rows, "energy"), "m3_per_bale": _ratio(rows, "water")},
    }
