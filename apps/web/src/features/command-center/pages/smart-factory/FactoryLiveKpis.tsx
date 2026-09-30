/* Hàng thẻ SỐ LŨY KẾ thời gian thực: điện năng · nước · số bành tới lúc đọc. Tự hỏi lại server mỗi
   `POLL_MS` (server cache ngắn dùng chung — SCADA không bị hỏi dồn); tab ẩn thì tạm dừng. Lỗi thì giữ
   số lần trước (mờ) và thử lại ở nhịp sau — số lũy kế cũ vẫn đúng tới thời điểm ghi bên dưới. */

import { useState } from "react";

import { type LiveMeters, fetchLiveMeters } from "../../../../lib/smart-factory-client";
import { fmtReading, hms } from "./smart-factory-format";
import { useVisiblePoll } from "./use-visible-poll";

const POLL_MS = 10_000;

/** `YYYY-MM-DDTHH:MM:SS` → "21:51:30 30/09" (giờ nhà máy, cắt chuỗi). */
const stamp = (ts: string | null) => (ts ? `${hms(ts)} ${ts.slice(8, 10)}/${ts.slice(5, 7)}` : "—");

export default function FactoryLiveKpis({ factoryId, count }: { factoryId: number; count: number }) {
  const [live, setLive] = useState<LiveMeters | null>(null);
  // Lỗi gắn với nhà máy đã lỗi → đổi nhà máy thì thôi báo lỗi cũ.
  const [failedId, setFailedId] = useState<number | null>(null);

  useVisiblePoll(async (alive) => {
    try {
      const d = await fetchLiveMeters(factoryId);
      if (!alive()) return undefined;
      setLive(d);
      setFailedId(null);
    } catch {
      if (alive()) setFailedId(factoryId);
    }
    return undefined;
  }, POLL_MS, String(factoryId));

  const shown = live?.factory.id === factoryId ? live : null;
  const failed = failedId === factoryId;
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
