/* Thanh điện tổng nằm DƯỚI khung sơ đồ (như dải đáy màn RELCO): Volt AB/BC/CA · Current A/B/C · Power —
   nhãn + đơn vị lấy từ `layout.power`, số từ lượt đọc gần nhất của nhà máy. Màn hẹp tự xuống dòng. */

import type { PlantLayout, PlantValues } from "../../../../../lib/smart-factory-client";
import { fmtNum } from "../smart-factory-format";
import { valueOf } from "./plant-format";

/** Điện áp/dòng/công suất: 1 số lẻ là đủ (khớp màn SCADA tại nhà máy). */
const POWER_DIGITS = 1;

/** `dim`: mất kết nối / số cũ → giữ số nhưng làm mờ. */
type Props = { items: PlantLayout["power"]; values: PlantValues | null; dim: boolean };

export default function PlantPowerBar({ items, values, dim }: Props) {
  return (
    <div className={`pl-power${dim ? " pl-stale" : ""}`}>
      {items.map((p) => {
        const v = values ? valueOf(values, p.tag) : null;
        return (
          <div key={p.tag} className="pl-power-item">
            <span className="pl-power-label">{p.label}</span>
            <span className={`pl-power-box${v == null ? " empty" : ""}`}>{fmtNum(v, POWER_DIGITS)}</span>
            <span className="pl-power-unit">{p.unit}</span>
          </div>
        );
      })}
    </div>
  );
}
