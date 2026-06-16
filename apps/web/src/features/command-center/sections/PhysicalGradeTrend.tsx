import { useEffect, useState } from "react";

import { fetchHistory } from "../../../lib/api-client";
import HistoryLineChart from "../charts/HistoryLineChart";

type Point = { as_of: string; price: number };
type Row = { source: string; grade: string; price: number; unit: string };

/** Trend từng grade physical (SMR20/SIR20/SMR10…). Physical là nguồn snapshot → lịch sử
    tích lũy dần qua cron daily-scan; <2 phiên thì hiện giá hiện tại + ghi chú đang tích lũy. */
export default function PhysicalGradeTrend({ rows }: { rows: Row[] }) {
  const [key, setKey] = useState("");
  const [points, setPoints] = useState<Point[]>([]);

  useEffect(() => {
    if (!key && rows.length) setKey(`${rows[0].source}:${rows[0].grade}`);
  }, [key, rows]);

  useEffect(() => {
    if (!key) return;
    const [s, g] = key.split(":");
    fetchHistory(s, g, 120).then((r) => setPoints(r.points)).catch(() => setPoints([]));
  }, [key]);

  const cur = rows.find((r) => `${r.source}:${r.grade}` === key);

  return (
    <div className="card" style={{ marginBottom: 18 }}>
      <div className="card-head">
        <div>
          <h3>Physical theo grade · diễn biến</h3>
          <div className="sub">Nguồn snapshot → tích lũy mỗi ngày (cron 18:00) · {points.length} phiên</div>
        </div>
        <select className="grade-select" value={key} onChange={(e) => setKey(e.target.value)}>
          {rows.map((r) => (
            <option key={`${r.source}:${r.grade}`} value={`${r.source}:${r.grade}`}>
              {r.source.toUpperCase()} · {r.grade}
            </option>
          ))}
        </select>
      </div>
      <div className="chart-wrap">
        {points.length >= 2 ? (
          <HistoryLineChart points={points} label={`${cur?.source.toUpperCase()} ${cur?.grade} (${cur?.unit ?? ""})`} color="#16a34a" />
        ) : (
          <div className="scan-empty">
            {cur ? (
              <>Hiện <b style={{ color: "#86efac" }}>{cur.price.toLocaleString()} {cur.unit}</b> · đang tích lũy lịch sử ({points.length} phiên) — chart đầy dần mỗi ngày scan.</>
            ) : (
              "Chưa có data physical"
            )}
          </div>
        )}
      </div>
    </div>
  );
}
