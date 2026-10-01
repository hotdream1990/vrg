/* Hàng 6 thẻ KPI đầu trang — đọc thẳng `totals` của 3 khối thu mua · tiêu thụ · tồn kho (không tự
   cộng lại số). Mỗi thẻ theo trạng thái tải của khối nguồn: đang tải "…", lỗi/chưa có số "—". */

import { dmy } from "../../../../lib/date";
import type {
  ConsumptionBlock, PurchaseBlock, StockBlock,
} from "../../../../lib/unit-dashboard-client";
import { fmtPrice, fmtTon, fmtTy, isPositive, rangeEndLabel, withUnit } from "./dashboard-format";
import type { BlockState } from "./use-dashboard-block";

type Props = {
  purchase: BlockState<PurchaseBlock>;
  consumption: BlockState<ConsumptionBlock>;
  stock: BlockState<StockBlock>;
};

const PRICE_TRIEU = "triệu đ/tấn";

type Kpi = { label: string; value: string; sub: string; negative?: boolean; warn?: boolean };

/** 3 loại mủ nguyên liệu (giá mủ nước theo độ TSC, mủ chén/mủ dây theo độ DRC — `price_units`). */
const RAW = [
  { name: "mủ nước", qty: "qty_latex", price: "price_latex_avg", unit: "latex" },
  { name: "mủ chén", qty: "qty_cup", price: "price_cup_avg", unit: "cup" },
  { name: "mủ dây", qty: "qty_lace", price: "price_lace_avg", unit: "lace" },
] as const;

/** Loại mủ có thu mua trong kỳ, SẢN LƯỢNG lớn nhất trước. Thẻ giá đi theo loại đứng đầu: cố định
 *  mủ nước thì Chư sê (100% mủ chén) luôn "—", Campuchia (99% mủ chén) hiện giá của vài chục tấn. */
function rawByQty(d: PurchaseBlock) {
  return RAW.map((r) => ({ name: r.name, qty: d.totals[r.qty] ?? 0, price: d.totals[r.price],
                           unit: d.price_units[r.unit] }))
    .filter((r) => r.qty > 0)
    .sort((a, b) => b.qty - a.qty);
}

function rawPriceKpi(d: PurchaseBlock): Omit<Kpi, "label"> {
  const [main, ...rest] = rawByQty(d);
  if (!main) return { value: "—", sub: "Chưa thu mua mủ nguyên liệu trong kỳ" };
  const share = Math.round((main.qty / (d.totals.qty_material || main.qty)) * 100);
  return {
    value: fmtPrice(main.price, main.unit),
    sub: rest.length
      ? `${main.unit} · ${share}% sản lượng · `
        + rest.map((r) => `${r.name} ${withUnit(fmtPrice(r.price, r.unit), r.unit)}`).join(" · ")
      : `${main.unit} · bình quân gia quyền theo sản lượng`,
  };
}

/** Dòng phụ của thẻ tồn kho: ngày chốt + độ phủ (Tập đoàn/khu vực) hoặc số cũ (một đơn vị). */
function stockWhen(d: StockBlock): { sub: string; warn: boolean } {
  const at = `tại ${dmy(d.as_of)}`;
  const age = d.totals.age_days ?? 0;
  if (d.scope.scope === "unit") {
    return age > 0
      ? { sub: `${at} · số cũ ${age} ngày (khai ${dmy(d.totals.dates[0] ?? d.as_of)})`, warn: true }
      : { sub: at, warn: false };
  }
  const c = d.coverage;
  if (!c) return { sub: at, warn: false };
  // Mẫu số trừ đơn vị khai "không phát sinh tồn kho" — cùng cách đếm với dải độ phủ bên dưới.
  const expected = c.units_expected - (c.no_stock ?? []).length;
  return { sub: `${at} · ${c.units_counted}/${expected} đơn vị có số`, warn: false };
}

/** Thẻ lấy số từ một khối: tự lo trạng thái đang tải / lỗi, chỉ tính số khi đã có dữ liệu. */
function kpiOf<T>(label: string, state: BlockState<T>, make: (d: T) => Omit<Kpi, "label">): Kpi {
  if (state.loading) return { label, value: "…", sub: "Đang tải" };
  if (state.error) return { label, value: "—", sub: "Chưa tải được" };
  if (!state.data) return { label, value: "—", sub: "" };
  return { label, ...make(state.data) };
}

export default function DashboardKpiRow({ purchase, consumption, stock }: Props) {
  const mainRaw = purchase.data ? rawByQty(purchase.data)[0] : undefined;
  const cards: Kpi[] = [
    kpiOf("Thu mua mủ nguyên liệu", purchase, (d) => ({
      value: withUnit(fmtTon(d.totals.qty_material), "tấn"),
      sub: `Mủ nước · chén · dây, ${dmy(d.date_from)} → ${rangeEndLabel(d.date_to)}`,
    })),
    kpiOf(mainRaw ? `Giá ${mainRaw.name} BQ` : "Giá mủ nguyên liệu BQ", purchase, rawPriceKpi),
    kpiOf("Tiêu thụ", consumption, ({ totals: t }) => ({
      value: withUnit(fmtTon(t.qty), "tấn"),
      sub: `Chuyến ${fmtTon(t.qty_spot)} · HĐNT ${fmtTon(t.qty_principle)} · dài hạn ${fmtTon(t.qty_long_term)}`
        + (isPositive(t.qty_unknown_type) ? ` · chưa khai loại ${fmtTon(t.qty_unknown_type)}` : "") + " (tấn)",
    })),
    kpiOf("Doanh thu", consumption, (d) => {
      const missing = d.totals.no_revenue_lines;
      const bad = d.totals.bad_price_lines ?? 0;
      const n = (v: number) => v.toLocaleString("vi-VN");
      // Hai lỗi kéo số NGƯỢC chiều: nghi sai đơn vị tính → ĐỘI lên (nặng hơn, nói trước); thiếu
      // tỷ giá / đơn giá → THẤP hơn thực tế. Có lỗi nào cũng phải nói ngay trên thẻ.
      const sub = bad > 0
        ? `${n(bad)} dòng bán nghi sai đơn vị tính — doanh thu đang bị đội lên`
          + (missing > 0 ? ` · chưa gồm ${n(missing)} lần giao thiếu tỷ giá` : "")
        : missing > 0 ? `Chưa gồm ${n(missing)} lần giao thiếu tỷ giá / đơn giá` : "";
      return {
        value: withUnit(fmtTy(d.totals.revenue_ty), "tỷ đồng"),
        sub: sub || `Giá bán BQ ${withUnit(fmtPrice(d.totals.avg_price_trieu, PRICE_TRIEU), PRICE_TRIEU)}`,
        warn: !!sub,
      };
    }),
    kpiOf("Tồn kho thành phẩm", stock, (d) => ({
      value: withUnit(fmtTon(d.totals.total), "tấn"), ...stockWhen(d),
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
