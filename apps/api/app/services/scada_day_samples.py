"""Mẫu THEO GIỜ của MỘT ngày — admin soi để hiểu vì sao một ô chỉ số bị gắn cờ (partial · reset ·
no_data) hoặc để đối chiếu với màn SCADA của nhà máy.

Đi CÙNG đường đọc với `/meters/daily` (khoá theo nhà máy + cache ở `scada_read_guard`, cùng truy vấn
Cyclic theo giờ) nên số thấy ở đây đúng là số thuật toán ngày đã dùng. Hôm nay thì ghép thêm mẫu
theo phút của 10 phút gần nhất (cũng là mẫu thuật toán dùng để chốt "tính đến hiện tại").
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.services import scada_client
from app.services import scada_daily_meters as dm
from app.services import scada_read_guard as guard


def day_samples(factory: dict, day: date, now: datetime) -> dict:
    """{date, metrics, samples: [{at, kind: hour|minute, values: {chỉ số: số}, raw: {tag: số}}]}."""
    start = datetime.combine(day, time())
    stop = start + timedelta(days=1)
    end = None if day >= now.date() else stop
    hourly, latest = guard.read(factory, start, end, scada_client.read_meters)
    metrics = dm.factory_metrics(factory)
    seen = {ts for ts, _ in hourly}
    merged = [(ts, raw, "hour") for ts, raw in hourly]
    merged += [(ts, raw, "minute") for ts, raw in latest if ts not in seen]
    samples = []
    for ts, raw, kind in sorted(merged, key=lambda r: r[0]):
        if not start <= ts <= stop:  # gồm mốc D+1 00:00 — chính là số cuối ngày
            continue
        vals = dm.metric_values(raw, factory, metrics)
        samples.append({"at": dm.iso(ts), "kind": kind,
                        "values": {m: dm.round_metric(m, vals[m]) for m in metrics}, "raw": raw})
    return {"date": day.isoformat(),
            "metrics": [{"key": m, "label": dm.METRICS[m][0], "unit": dm.METRICS[m][1]}
                        for m in metrics],
            "samples": samples}
