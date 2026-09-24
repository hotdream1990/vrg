/* Hàng 6 thẻ KPI đầu trang — đọc thẳng `totals` của 3 khối thu mua · tiêu thụ · tồn kho (không tự
   cộng lại số). Mỗi thẻ theo trạng thái tải của khối nguồn: đang tải "…", lỗi/chưa có số "—". */

import { dmy } from "../../../../lib/date";
import type {
  ConsumptionBlock, PurchaseBlock, StockBlock,
} from "../../../../lib/unit-dashboard-client";
import { fmtPrice, fmtTon, fmtTy, withUnit } from "./dashboard-format";
import type { BlockState } from "./use-dashboard-block";

type Props = {
  purchase: BlockState<PurchaseBlock>;
  consumption: BlockState<ConsumptionBlock>;
  stock: BlockState<StockBlock>;
};

const PRICE_TRIEU = "triệu đ/tấn";

type Kpi = { label: string; value: string; sub: string; negative?: boolean; warn?: boolean };

/** Thẻ lấy số từ một khối: tự lo trạng thái đang tải / lỗi, chỉ tính số khi đã có dữ liệu. */
function kpiOf<T>(label: string, state: BlockState<T>, make: (d: T) => Omit<Kpi, "label">): Kpi {
  if (state.loading) return { label, value: "…", sub: "Đang tải" };
  if (state.error) return { label, value: "—", sub: "Chưa tải được" };
  if (!state.data) return { label, value: "—", sub: "" };
  return { label, ...make(state.data) };
}

export default function DashboardKpiRow({ purchase, consumption, stock }: Props) {
  const cards: Kpi[] = [
    kpiOf("Thu mua mủ nguyên liệu", purchase, (d) => ({
      value: withUnit(fmtTon(d.totals.qty_material), "tấn"),
      sub: `Mủ nước · chén · dây, ${dmy(d.date_from)} → ${dmy(d.date_to)}`,
    })),
    kpiOf("Giá mủ nước BQ", purchase, (d) => ({
      value: fmtPrice(d.totals.price_latex_avg, d.price_units.latex),
      sub: `${d.price_units.latex} · bình quân gia quyền theo sản lượng`,
    })),
    kpiOf("Tiêu thụ", consumption, (d) => ({
      value: withUnit(fmtTon(d.totals.qty), "tấn"),
      sub: `Dài hạn ${fmtTon(d.totals.qty_long_term)} · chuyến ${fmtTon(d.totals.qty_spot)} (tấn)`,
    })),
    kpiOf("Doanh thu", consumption, (d) => {
      const missing = d.totals.missing_fx_lines;
      return {
        value: withUnit(fmtTy(d.totals.revenue_ty), "tỷ đồng"),
        // Đang thiếu phần bán USD chưa có tỷ giá → số trên thẻ THẤP hơn thực tế, phải nói ngay tại đây.
        sub: missing > 0
          ? `Chưa gồm ${missing.toLocaleString("vi-VN")} lần giao thiếu tỷ giá`
          : `Giá bán BQ ${withUnit(fmtPrice(d.totals.avg_price_trieu, PRICE_TRIEU), PRICE_TRIEU)}`,
        warn: missing > 0,
      };
    }),
    kpiOf("Tồn kho thành phẩm", stock, (d) => ({
      value: withUnit(fmtTon(d.totals.total), "tấn"),
      sub: `tại ${dmy(d.as_of)}`,
    })),
    kpiOf("Tồn có thể giao dịch", stock, (d) => {
      const v = d.totals.tradable;
      const negative = v != null && v < 0;
      return {
        value: withUnit(fmtTon(v), "tấn"),
        sub: negative ? "Thiếu hàng để giao cho hợp đồng đã ký"
                      : "= tồn thành phẩm − đã ký HĐ chưa giao",
        negative,
      };
    }),
  ];

  return (
    <div className="kpi-row ud-kpi-row">
      {cards.map((k) => (
        <div className="kpi" key={k.label}>
          <div className="label">{k.label}</div>
          <div className={`value${k.negative ? " ud-neg" : ""}`}>{k.value}</div>
          <div className={`sub${k.warn ? " ud-warn" : ""}`}>{k.sub}</div>
        </div>
      ))}
    </div>
  );
}
