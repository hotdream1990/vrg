/* Hàng thẻ SỐ LŨY KẾ thời gian thực: điện năng · nước · số bành tới lúc đọc. Tự hỏi lại server mỗi
   `POLL_MS` (server cache ngắn dùng chung — SCADA không bị hỏi dồn); tab ẩn thì tạm dừng. Lỗi thì giữ
   số lần trước (mờ) và thử lại ở nhịp sau — số lũy kế cũ vẫn đúng tới thời điểm ghi bên dưới. */

import { useEffect, useState } from "react";

import { type LiveMeters, fetchLiveMeters } from "../../../../lib/smart-factory-client";
import { fmtReading } from "./smart-factory-format";

const POLL_MS = 10_000;

/** `YYYY-MM-DDTHH:MM:SS` → "21:51:30 30/09" (giờ nhà máy, cắt chuỗi). */
const stamp = (ts: string | null) => (ts ? `${ts.slice(11, 19)} ${ts.slice(8, 10)}/${ts.slice(5, 7)}` : "—");

export default function FactoryLiveKpis({ factoryId, count }: { factoryId: number; count: number }) {
  const [live, setLive] = useState<LiveMeters | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    // Lần đầu luôn đọc (mở ở tab nền vẫn có số); các nhịp sau bỏ qua khi tab đang ẩn.
    const poll = (force = false) => {
      if (document.hidden && !force) return;
      fetchLiveMeters(factoryId)
        .then((d) => { if (alive) { setLive(d); setFailed(false); } })
        .catch(() => { if (alive) setFailed(true); });
    };
    setLive(null);
    poll(true);
    const timer = window.setInterval(() => poll(), POLL_MS);
    const onShow = () => { if (!document.hidden) poll(); };
    document.addEventListener("visibilitychange", onShow);
    return () => {
      alive = false;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onShow);
    };
  }, [factoryId]);

  const shown = live?.factory.id === factoryId ? live : null;
  return (
    <div className="kpi-row sf-kpi-row">
      {shown ? shown.metrics.map((m) => {
        const v = shown.values[m.key];
        return (
          <div key={m.key} className={`kpi${failed ? " sf-live-stale" : ""}`}>
            <div className="label">{m.label} — số lũy kế</div>
            <div className="value">{fmtReading(v?.value, m.key)} <small>{m.unit}</small></div>
            <div className="sf-kpi-line">
              <span className={`sf-live-dot${failed ? " off" : ""}`} />
              {failed ? "Mất kết nối — đang thử lại" : `lúc ${stamp(v?.at ?? null)}`}
            </div>
          </div>
        );
      }) : Array.from({ length: count }, (_, i) => (
        <div key={i} className="kpi"><div className="label">Đang đọc SCADA…</div>
          <div className="value">—</div></div>
      ))}
    </div>
  );
}
