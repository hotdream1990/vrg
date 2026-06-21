import { useState } from "react";

import DateRangeBar from "../sections/DateRangeBar";
import PriceSheetGrid from "../sections/PriceSheetGrid";
import "../../bulletin/bulletin.css";

/** Quản lý số liệu → Tỷ giá (USD/JPY·CNY·MYR·THB·VND theo ngày). */
export default function FxRatePage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2>⇄ Tỷ giá (Exchange Rate)</h2>
          <p>Tỷ giá USD theo ngày (JPY · CNY · MYR · THB · VND) dùng quy đổi giá sàn — bấm ô để sửa.</p>
        </div>
      </div>

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} />

      <PriceSheetGrid view="fx" dateFrom={from || undefined} dateTo={to || undefined} />
    </div>
  );
}
