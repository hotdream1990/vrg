import { CheckCircleFilled } from "@ant-design/icons";

import type { LockSummary } from "../../../lib/data-lock-client";

type Unit = Omit<LockSummary, "round" | "merged_units">;
type Merged = NonNullable<LockSummary["merged_units"]>[number];

const dmy = (iso?: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const n3 = (v: number | null | undefined) =>
  (typeof v === "number" && Number.isFinite(v) && Math.abs(v) > 1e-9
    ? v.toLocaleString("vi-VN", { maximumFractionDigits: 3 })
    : "—");
const R = { textAlign: "right" as const, fontVariantNumeric: "tabular-nums" as const };

/** Bốn chỉ tiêu CỘNG ĐƯỢC giữa các pháp nhân. Tồn kho là số thời điểm — kho của đơn vị cũ đã nằm
 *  trong số khai của đơn vị nhận kể từ ngày sáp nhập — nên KHÔNG đưa vào bảng cộng này. */
function figures(u: Unit) {
  const num = (v: unknown) => (typeof v === "number" ? v : null);
  return {
    purchase: u.has_purchase_plan ? num(u.purchase.total_purchase) : null,
    consumption: num(u.consumption.total_consumption),
    revenue: num(u.consumption.revenue_ty),
    signed: num(u.stock.stock_finished_hd),
  };
}

/** Cộng từng cột; doanh thu có tiêu thụ mà không có tiền (lần giao thiếu tỷ giá) là KHÔNG BIẾT →
 *  cả ô tổng để trống chứ không cộng phần còn lại rồi coi như đủ. */
function sumAll(rows: ReturnType<typeof figures>[]) {
  const add = (k: keyof ReturnType<typeof figures>) => rows.reduce((s, r) => s + (r[k] ?? 0), 0);
  const revenueUnknown = rows.some((r) => (r.consumption ?? 0) > 0 && r.revenue == null);
  return {
    purchase: add("purchase"), consumption: add("consumption"),
    revenue: revenueUnknown ? null : add("revenue"), signed: add("signed"),
  };
}

/**
 * Bảng CHỐT KÈM các đơn vị đã sáp nhập vào đơn vị đang chốt (phản ánh của Chư prông 29/09/2026).
 *
 * Hợp đồng ký trước sáp nhập vẫn đứng tên đơn vị cũ nhưng do đơn vị nhận giao nốt — bảng chốt cũ chỉ
 * bày số của đơn vị nhận nên lần giao đó "biến mất" khỏi con số đơn vị xác nhận. Mỗi đơn vị giữ KỲ
 * CHỐT RIÊNG (đầu kỳ nối tiếp lần chốt trước của chính nó), dòng cuối là số GỘP — khớp Báo cáo tổng hợp.
 */
export default function DataLockMergedUnits({ own, merged, readOnly }: {
  own: Unit; merged: Merged[]; readOnly?: boolean;
}) {
  if (!merged.length) return null;
  const rows = [{ u: own, f: figures(own), label: "đơn vị mình" as string | null, done: false },
    ...merged.map((m) => ({ u: m as Unit, f: figures(m), label: "đã sáp nhập", done: m.confirmed }))];
  const total = sumAll(rows.map((r) => r.f));

  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 6px" }}>Đơn vị đã sáp nhập — chốt kèm</h4>
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>
        Hợp đồng ký trước khi sáp nhập vẫn đứng tên đơn vị cũ nên số của đơn vị đó tính riêng, theo kỳ
        chốt của chính nó.{!readOnly && " Bấm xác nhận là chốt luôn cả phần này."}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead><tr>
            <th>Đơn vị</th><th>Kỳ chốt</th>
            <th style={R}>Thu mua (tấn)</th><th style={R}>Tiêu thụ (tấn)</th>
            <th style={R}>Doanh thu (tỷ đồng)</th><th style={R}>Đã ký HĐ chưa giao (tấn quy khô)</th>
          </tr></thead>
          <tbody>
            {rows.map(({ u, f, label, done }) => (
              <tr key={u.company}>
                <td>
                  {u.company}
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    {label}
                    {done && <> · <CheckCircleFilled style={{ color: "var(--ok, #389e0d)" }} /> đã chốt</>}
                  </div>
                </td>
                <td style={{ whiteSpace: "nowrap" }}>{dmy(u.date_from)} – {dmy(u.lock_date)}</td>
                <td style={R}>{n3(f.purchase)}</td>
                <td style={R}>{n3(f.consumption)}</td>
                <td style={R}>{n3(f.revenue)}</td>
                <td style={R}>{n3(f.signed)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ fontWeight: 600 }}>
              <td colSpan={2}>Cộng (gộp như Báo cáo tổng hợp)</td>
              <td style={R}>{n3(total.purchase)}</td>
              <td style={R}>{n3(total.consumption)}</td>
              <td style={R}>{n3(total.revenue)}</td>
              <td style={R}>{n3(total.signed)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
