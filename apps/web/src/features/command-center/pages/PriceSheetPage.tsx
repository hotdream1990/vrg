import { useState } from "react";

import DateRangeBar from "../sections/DateRangeBar";
import PriceSheetGrid from "../sections/PriceSheetGrid";
import "../../bulletin/bulletin.css";

/** Quản lý số liệu → Bảng tính giá các sàn (Native·Tỷ giá·USD/T theo ngày, giống file mẫu). */
export default function PriceSheetPage() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2>▦ Bảng tính giá các sàn</h2>
          <p>Giá nội tệ · Tỷ giá · USD/T theo ngày (OSE · SHANGHAI · SGX · MRB) — bấm ô để sửa, ghi đè kho giá.</p>
        </div>
      </div>

      <DateRangeBar from={from} to={to} onFrom={setFrom} onTo={setTo} />

      <PriceSheetGrid view="exchange" dateFrom={from || undefined} dateTo={to || undefined} />
    </div>
  );
}
