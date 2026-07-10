import { useEffect, useState } from "react";

import { type MqPriceHistory, fetchMarketPriceHistory } from "../../../../lib/market-quote-client";
import HistorySectionChart from "./HistorySectionChart";

/** Lịch sử giá SVR thị trường — 4 box cho 4 mục (NĐ tư nhân · NĐ hàng XK · XK VRG · NĐ VRG),
 *  mỗi box bật/tắt từng chủng loại (chip) + Hiện/Ẩn hết. */
export default function MarketHistoryBlock() {
  const [data, setData] = useState<MqPriceHistory | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetchMarketPriceHistory(180).then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi tải dữ liệu"));
  }, []);

  return (
    <div style={{ marginBottom: 18 }} id="sec-lichsu">
      <h3 style={{ margin: "0 2px 12px", fontSize: 16, color: "var(--text)" }}>
        Lịch sử giá thị trường theo mục
        <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 400, marginLeft: 8 }}>
          4 mục · bấm tên chủng loại để ẩn/hiện đường
        </span>
      </h3>
      {err ? <div className="card"><div className="scan-empty">{err}</div></div>
        : !data ? <div className="card"><div className="scan-empty">Đang tải…</div></div>
        : (
          <div className="grid-2">
            {data.sections.map((s) => <HistorySectionChart key={s.key} section={s} />)}
          </div>
        )}
    </div>
  );
}
