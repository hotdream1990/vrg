/* 6 ô chỉ số tồn kho tại ngày chốt. "Đã ký HĐ chưa giao" NẰM TRONG tồn thành phẩm (không cộng thêm);
   "Có thể giao dịch" = tồn − đã ký, có thể ÂM (đã ký giao nhiều hơn hàng đang có) → tô đỏ. */

import type { StockBlock } from "../../../../lib/unit-dashboard-client";
import { fmtTon } from "./dashboard-format";

type Totals = StockBlock["totals"];

type Stat = { label: string; value: number | null; unit: string; sub?: string; main?: boolean };

export default function StockStats({ totals: t }: { totals: Totals }) {
  const tradableNeg = t.tradable != null && t.tradable < 0;
  const stats: Stat[] = [
    { label: "Chưa nhập kho", value: t.not_warehoused, unit: "tấn" },
    { label: "Đã nhập kho", value: t.warehoused, unit: "tấn" },
    { label: "Tổng tồn thành phẩm", value: t.total, unit: "tấn", sub: "= chưa nhập + đã nhập kho", main: true },
    { label: "Đã ký HĐ chưa giao", value: t.signed_undelivered, unit: "tấn", sub: "nằm trong tồn kho" },
    { label: "Có thể giao dịch", value: t.tradable, unit: "tấn",
      sub: tradableNeg ? "thiếu hàng để giao" : "= tổng tồn − đã ký chưa giao" },
    { label: "Tồn nguyên liệu", value: t.material, unit: "tấn quy khô" },
  ];
  return (
    <div className="ud-stat-grid">
      {stats.map((s) => {
        const neg = s.value != null && s.value < 0;
        return (
          <div key={s.label} className={`ud-stat${s.main ? " is-main" : ""}`}>
            <div className="ud-stat-label">{s.label}</div>
            <div className={`ud-stat-value${neg ? " ud-neg" : ""}`}>
              {fmtTon(s.value)}{s.value != null && <small> {s.unit}</small>}
            </div>
            {s.sub && <div className={`ud-stat-sub${neg ? " ud-neg" : ""}`}>{s.sub}</div>}
          </div>
        );
      })}
    </div>
  );
}
