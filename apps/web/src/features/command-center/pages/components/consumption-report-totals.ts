/* Báo cáo tiêu thụ — định dạng số + cộng TỔNG từ các dòng đơn vị server trả.
   Web chỉ CỘNG các số server đã tính cho từng đơn vị, không tự suy ra số nào khác. */

import type { Backlog, ConsumptionReport } from "../../../../lib/sales-contract-client";

export const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
/** Cột "SL chưa quy khô": chỉ chủng loại còn nước (latex · mủ nguyên liệu · mủ dây) mới có;
    0 = hàng khô → hiện "—" chứ không hiện "0" (số 0 bị đọc thành "bán 0 tấn", trong khi thật ra
    chủng loại đó không có khái niệm quy khô). */
export const wet = (n: number) => (n ? t3(n) : "—");
export const ty = (n: number | null) =>
  (n == null ? "—" : (n / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));
export const pct1 = (v: number | null) =>
  (v == null ? "—" : `${v.toLocaleString("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`);


/** Đơn vị có dòng: có lần giao trong kỳ, còn hợp đồng chưa giao, hoặc còn HĐ mẹ / hàng phải giao
 *  (đơn vị chưa giao lần nào trong kỳ vẫn phải hiện phần phải giao của mình). */
export function reportCompanies(rep: ConsumptionReport | null): string[] {
  if (!rep) return [];
  const keys = new Set([...Object.keys(rep.by_company), ...Object.keys(rep.undelivered)]);
  for (const [c, b] of Object.entries(rep.backlog ?? {})) {
    if (b.masters > 0 || b.to_deliver > 0) keys.add(c);
  }
  return Array.from(keys).sort();
}

export type ConsumptionTotals = {
  qty: number; qty_wet: number; revenue: number | null; deliveries: number;
  remaining: number;                 // khối 3 cũ — chỉ dùng khi API chưa trả `backlog`
  channels: Record<string, number>;
  /** Nguồn tiêu thụ: exploit (khai thác) · purchase (thu mua). */
  sources: Record<string, number>;
};

export function sumConsumption(rep: ConsumptionReport | null, companies: string[]): ConsumptionTotals {
  const acc: ConsumptionTotals = {
    qty: 0, qty_wet: 0, revenue: 0, deliveries: 0, remaining: 0,
    // Hình thức tiêu thụ chỉ có ở dòng từng đơn vị — không cộng thì cả bảng thiếu tổng XK /
    // trong nước / nội bộ, đúng 3 con số hay bị hỏi nhất.
    channels: { export: 0, domestic: 0, internal: 0 },
    sources: { exploit: 0, purchase: 0 },
  };
  if (!rep) return acc;
  for (const c of companies) {
    const r = rep.by_company[c];
    if (r) {
      acc.qty += r.qty; acc.qty_wet += r.qty_wet; acc.deliveries += r.deliveries;
      for (const k of Object.keys(acc.channels)) acc.channels[k] += r.by_channel?.[k] ?? 0;
      for (const k of Object.keys(acc.sources)) acc.sources[k] += r.by_source?.[k] ?? 0;
      if (r.revenue == null) acc.revenue = null;
      else if (acc.revenue != null) acc.revenue += r.revenue;
    }
    acc.remaining += rep.undelivered[c]?.qty ?? 0;
  }
  return acc;
}

export type BacklogTotals = {
  spot: number; principle: number; unknown: number; lt: number; toDeliver: number;
  committed: number; delivered: number; masterRemaining: number; expiredShort: number;
  masters: number;
  pct: number | null;                // Σ đã giao / Σ cam kết — null khi chưa có cam kết nào
};

/** null = API cũ chưa trả `backlog` → trang giữ cột "Chưa giao" cũ. */
export function sumBacklog(backlog?: Record<string, Backlog>): BacklogTotals | null {
  if (!backlog) return null;
  const acc: BacklogTotals = {
    spot: 0, principle: 0, unknown: 0, lt: 0, toDeliver: 0,
    committed: 0, delivered: 0, masterRemaining: 0, expiredShort: 0, masters: 0, pct: null,
  };
  for (const b of Object.values(backlog)) {
    acc.spot += b.spot_undelivered; acc.principle += b.principle_undelivered ?? 0;
    acc.unknown += b.unknown_undelivered;
    acc.lt += b.lt_remaining; acc.toDeliver += b.to_deliver;
    acc.committed += b.master_committed; acc.delivered += b.master_delivered;
    acc.masterRemaining += b.master_remaining; acc.expiredShort += b.master_expired_short;
    acc.masters += b.masters;
  }
  acc.pct = acc.committed > 0 ? (acc.delivered / acc.committed) * 100 : null;
  return acc;
}
