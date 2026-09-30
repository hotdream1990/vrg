/* Ô "Tiêu thụ trong ngày" trên trang — chỉ dùng cho khu KHÔNG khai `usage_box` (khu có thì bảng nằm trong
   khung sơ đồ, xem PlantUsageBox). Số lấy từ usePlantDailyUsage. `memo`: trang vẽ lại mỗi nhịp số sơ đồ
   (5 s) — ô này không cần theo. */

import { memo } from "react";

import type { MetricKey } from "../../../../../lib/smart-factory-client";
import { fmtUsed } from "../smart-factory-format";
import { usePlantDailyUsage } from "./use-plant-daily-usage";

const HEAD: Record<MetricKey, string> = { energy: "Điện (kWh)", water: "Nước (m³)", bales: "Bành" };

type Props = { factoryId: number; metrics: MetricKey[] };

function PlantDailyUsage({ factoryId, metrics }: Props) {
  const { cols, rows, failed } = usePlantDailyUsage(factoryId, metrics);
  return (
    <div className={`card pl-usage${failed ? " pl-stale" : ""}`}>
      <div className="pl-usage-title">Tiêu thụ trong ngày</div>
      <table className="pl-usage-table">
        <thead>
          <tr><th />{cols.map((k) => <th key={k}>{HEAD[k]}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map(({ label, row }) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              {cols.map((k) => <td key={k} className="pl-num-cell">{fmtUsed(row?.[k]?.used, k)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default memo(PlantDailyUsage);
