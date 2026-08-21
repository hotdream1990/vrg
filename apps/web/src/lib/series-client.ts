/* Client cho họ API `/api/series/*` — chuỗi số liệu THEO NGÀY dựng từ báo cáo đơn vị thành viên
   (thu mua · tồn kho · tiêu thụ). Mọi chuỗi trả cùng một khuôn để dùng chung biểu đồ cột chồng. */

import { apiFetch } from "./http";

const req = <T>(path: string, params: Record<string, string | undefined>): Promise<T> => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) p.set(k, v);
  return apiFetch<T>(`${path}?${p}`);
};

/* ── Khuôn chung: chuỗi cột chồng theo ngày ─────────────────────────────────── */

export type SeriesKey = { key: string; label: string };

export type StackedRow = {
  as_of: string;
  total: number | null;
  values: Record<string, number>;      // theo khoá của `series`
};

/* ── Thu mua: đơn giá + sản lượng ───────────────────────────────────────────── */

/** Rổ tính dải giá: `steady` = chỉ đơn vị khai đều (các ngày so được với nhau) · `all` = mọi đơn vị. */
export type PriceBasket = "steady" | "all";
export type Material = "latex" | "cup";

export type PurchaseDayStat = {
  min: number | null;
  max: number | null;
  avg: number | null;
  units: number;          // số đơn vị có GIÁ trong ngày
  qty: number | null;     // sản lượng thu mua trong ngày (tấn)
  qty_units: number;      // số đơn vị đã khai SẢN LƯỢNG
};

export type PurchaseSeries = {
  date_from: string;
  date_to: string;
  basket: PriceBasket;
  basket_units: Record<Material, number>;    // số đơn vị trong rổ giá
  rows: { as_of: string; latex: PurchaseDayStat; cup: PurchaseDayStat }[];   // ngày TĂNG dần
};

export type PurchaseVolumeGroup = "region" | "company";

export type PurchaseVolumeSeries = {
  material: Material;
  group_by: PurchaseVolumeGroup;
  series: SeriesKey[];
  rows: StackedRow[];
};

export const fetchPurchaseSeries = (dateFrom?: string, dateTo?: string, basket?: PriceBasket) =>
  req<PurchaseSeries>("/api/series/purchase", { date_from: dateFrom, date_to: dateTo, basket });

export const fetchPurchaseVolume = (
  material: Material, groupBy: PurchaseVolumeGroup, dateFrom?: string, dateTo?: string,
) => req<PurchaseVolumeSeries>("/api/series/purchase-volume",
  { material, group_by: groupBy, date_from: dateFrom, date_to: dateTo });

/* ── Tồn kho ────────────────────────────────────────────────────────────────── */

export type StockGroupBy = "structure" | "grade" | "region" | "free_grade";

export type StockSeries = {
  group_by: StockGroupBy;
  start_floor: string;                  // ngày đầu tiên đơn vị nhập đủ để cộng thành số Tập đoàn
  series: SeriesKey[];
  rows: (StackedRow & { units_counted: number })[];   // số đơn vị CÓ tồn thành phẩm hôm đó
  /** Ngày cuối chuỗi đang nhập dở nên chưa vẽ (số đơn vị còn quá thấp so với các ngày trước). */
  pending: { as_of: string; units_counted: number }[];
};

export const fetchStockSeries = (groupBy: StockGroupBy, dateFrom?: string, dateTo?: string) =>
  req<StockSeries>("/api/series/stock", { group_by: groupBy, date_from: dateFrom, date_to: dateTo });

/* ── Tiêu thụ ───────────────────────────────────────────────────────────────── */

export type ConsumptionGroupBy = "region" | "company" | "grade" | "contract" | "channel";

export type ConsumptionSeries = {
  group_by: ConsumptionGroupBy;
  series: SeriesKey[];
  rows: (StackedRow & {
    revenue_vnd: number | null;
    revenue_missing_lines: number;      // dòng bán USD thiếu tỷ giá → không tính doanh thu
  })[];
};

export const fetchConsumptionSeries = (
  groupBy: ConsumptionGroupBy, dateFrom?: string, dateTo?: string,
) => req<ConsumptionSeries>("/api/series/consumption",
  { group_by: groupBy, date_from: dateFrom, date_to: dateTo });
