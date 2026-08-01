/* Form nhập biểu TỒN KHO (trước 30/07/2026 là biểu "Tiêu thụ – Tồn kho").
   - TIÊU THỤ đã RỜI KHỎI biểu nhập: số tiêu thụ nay TÍNH TỪ các lần giao ghi trên hợp đồng
     (module "Quản lý hợp đồng"). Hai mảng `sales` / `sales_own` cũ vẫn được giữ nguyên trong
     payload để không mất lịch sử — form không hiển thị, chỉ chuyển tiếp khi lưu.
   - TỒN KHO (số THỜI ĐIỂM cuối ngày, đơn vị TẤN) còn 3 khối NHẬP TAY: 1 chế biến chưa nhập kho ·
     2 đã nhập kho · 3 nguyên liệu chưa sản xuất (quy khô).
   - "Đã ký HĐ chưa giao" KHÔNG còn xuất hiện trong form: đây là số hệ thống tự tính từ hợp đồng
     (cam kết − đã giao), xem ở cột cùng tên trên bảng danh sách và ở màn Báo cáo tiêu thụ.
   - Tồn kho KHÔNG cộng dồn giữa các ngày; có nút "Lấy tồn ngày trước" để chép sang rồi sửa. */

import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Select, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { TONNES_STOCK } from "../../../lib/entry-bounds";
import { HINT_STOCK_BALANCE } from "../../../lib/unit-daily-entry-hints";
import { consumptionWarnings } from "../../../lib/unit-daily-warnings";
import { type PriceDraft, type Role, fetchPrevStock } from "../../../lib/unit-daily-client";
import {
  GRADES, type Ccy, type ConsumptionData, type StockQtyLine, stockTonnesTotal,
} from "../../../lib/unit-daily-consumption";
import { type Values, fmtNum } from "../../../lib/unit-daily-fields";
import EntryWarnBanner from "../sections/EntryWarnBanner";
import { fieldLabel, numInput, readOnlyBox } from "./unit-daily-inputs";

const NO_PRICES: PriceDraft = { latex: null, cup: null };
const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

/** Tab cũ của biểu — giữ kiểu để route/menu không phải đổi chữ ký (chỉ còn "stock" có nghĩa). */
export type ConsumptionTab = "sales" | "stock";

type Props = {
  values: Values;
  readOnly?: boolean;
  formKey: string;
  currency?: string;                       // VND/LAK/KHR
  role?: Role;                             // để lấy tồn ngày trước đúng endpoint
  company?: string;                        // đơn vị đang nhập
  day?: string;                            // ngày đang nhập
  defaultTab?: ConsumptionTab;
  isParent?: boolean;                      // đơn vị là CÔNG TY MẸ → hiện ô chi phí tổng
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values, prices: PriceDraft) => React.ReactNode;
};

const defaultCcy = (currency?: string): Ccy => ((currency ?? "VND") === "VND" ? "VND" : "USD");

function initData(values: Values, currency?: string): ConsumptionData {
  const v = values as unknown as ConsumptionData;
  return {
    // Giữ nguyên mảng tiêu thụ CŨ (không hiển thị) để lần lưu sau không xoá mất lịch sử.
    sales: Array.isArray(v.sales) ? v.sales.map((l) => ({ ...l })) : [],
    sales_own: Array.isArray(v.sales_own) ? v.sales_own.map((l) => ({ ...l })) : [],
    revenue: v.revenue ?? null,
    sales_ccy: v.sales_ccy ?? defaultCcy(currency),
    stock_ccy: v.stock_ccy ?? defaultCcy(currency),
    fx_revenue: v.fx_revenue ?? null,
    stock_not_warehoused: Array.isArray(v.stock_not_warehoused) ? v.stock_not_warehoused.map((r) => ({ ...r })) : [],
    stock_warehoused: Array.isArray(v.stock_warehoused) ? v.stock_warehoused.map((r) => ({ ...r })) : [],
    stock_material: v.stock_material ?? null,
    no_stock: v.no_stock === true,
    cost_total: v.cost_total ?? null,
    internal_purchase_cost: v.internal_purchase_cost ?? null,
  };
}

export default function ConsumptionForm({ values, readOnly, formKey, currency, role = "member", company, day, isParent, onDirty, footer }: Props) {
  const [data, setData] = useState<ConsumptionData>(() => initData(values, currency));
  const [prevLoading, setPrevLoading] = useState(false);
  useEffect(() => { setData(initData(values, currency)); }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const notWh = (data.stock_not_warehoused ?? []) as StockQtyLine[];   // 1 chế biến chưa nhập kho
  const wh = (data.stock_warehoused ?? []) as StockQtyLine[];          // 2 đã nhập kho

  const setNotWh = (next: StockQtyLine[]) => setData((d) => ({ ...d, stock_not_warehoused: next }));
  const setWh = (next: StockQtyLine[]) => setData((d) => ({ ...d, stock_warehoused: next }));

  const current = useMemo<Values>(() => ({ ...data } as unknown as Values), [data]);
  const orig = useMemo(() => initData(values, currency), [values, currency]);
  const dirty = useMemo(() => JSON.stringify(data) !== JSON.stringify(orig), [data, orig]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Chép TỒN KHO của ngày gần nhất trước ngày đang nhập (tồn kho là số thời điểm, ít đổi). */
  const loadPrevStock = async () => {
    if (!company || !day) return;
    setPrevLoading(true);
    try {
      const r = await fetchPrevStock(role, company, day);
      if (!r.found) { message.info("Chưa có số tồn kho nào trước ngày này."); return; }
      setData((d) => ({
        ...d,
        stock_not_warehoused: (r.stock_not_warehoused ?? []).map((x) => ({ ...x })),
        stock_warehoused: (r.stock_warehoused ?? []).map((x) => ({ ...x })),
        stock_material: r.stock_material ?? null,
        stock_ccy: r.stock_ccy ?? d.stock_ccy,
      }));
      message.success(`Đã chép tồn kho ngày ${r.as_of} — kiểm tra và sửa lại trước khi lưu.`);
    } catch (e) { message.error((e as Error).message || "Không lấy được tồn kho ngày trước."); }
    finally { setPrevLoading(false); }
  };

  const head = (t: string, first?: boolean, hint?: string) => (
    <div style={{ fontWeight: 600, fontSize: 12.5, opacity: 0.85, marginTop: first ? 0 : 18, marginBottom: 6, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)" }}>
      {t}
      {hint && <span style={{ fontWeight: 400, opacity: 0.7 }}> ({hint})</span>}
    </div>
  );
  const sel = { width: "100%" } as const;
  const gridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10, alignItems: "end" } as const;
  const box = (label: string, unit: string, value: number | null, digits = 2) => (
    <label style={{ display: "block" }}>{fieldLabel(label, unit)}{readOnlyBox(fmtNum(value, unit === "tấn" ? 3 : digits), "tự tính")}</label>
  );
  const cellNum = (v: number | null, on: (v: number | null) => void) =>
    numInput(v, on, readOnly, "small", TONNES_STOCK);
  const gradeSel = (val: string, on: (v: string) => void) => (
    <Select size="small" style={sel} value={val || undefined} placeholder="Loại mủ" disabled={readOnly} showSearch
      onChange={on} options={GRADES.map((g) => ({ value: g, label: g }))} />
  );

  /** Bảng chỉ có Chủng loại + Số lượng (khối 1 & 2). */
  const qtyTable = (rows: StockQtyLine[], setRows: (n: StockQtyLine[]) => void) => (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales ud-narrow">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: "60%" }}>Chủng loại</th>
            <th style={{ width: "33%" }} className="r">Số lượng (tấn)</th>{!readOnly && <th style={{ width: "7%" }} />}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{gradeSel(r.grade, (v) => setRows(rows.map((x, j) => j === i ? { ...x, grade: v } : x)))}</td>
                <td>{cellNum(num(r.qty), (v) => setRows(rows.map((x, j) => j === i ? { ...x, qty: v } : x)))}</td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} onClick={() => setRows(rows.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={readOnly ? 2 : 3} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }}
        onClick={() => setRows([...rows, { grade: GRADES[0], qty: null }])}><PlusOutlined /> Thêm dòng</button>}
    </>
  );

  const warnings = useMemo(() => (readOnly ? [] : consumptionWarnings(current as ConsumptionData)), [current, readOnly]);

  return (
    <div>
      <EntryWarnBanner items={warnings} />

      {!readOnly && (
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, fontSize: 13 }}>
          <input type="checkbox" checked={data.no_stock === true}
            onChange={(e) => setData((d) => ({ ...d, no_stock: e.target.checked }))} />
          Hôm nay <b>không phát sinh</b> tồn kho để khai
        </label>
      )}

      {!readOnly && company && day && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          <button type="button" className="btn" style={{ fontSize: 12 }} onClick={loadPrevStock} disabled={prevLoading}>
            {prevLoading ? "Đang lấy…" : "Lấy tồn ngày trước"}
          </button>
          <span className="form-note" style={{ fontSize: 11.5 }}>
            Tồn kho là số tại thời điểm cuối ngày — chép sang rồi sửa cho đúng ngày này.
          </span>
        </div>
      )}

      {head("1. Tồn kho thành phẩm chế biến chưa nhập kho", true, HINT_STOCK_BALANCE)}
      {qtyTable(notWh, setNotWh)}

      {head("2. Tồn kho thành phẩm đã nhập kho", false, HINT_STOCK_BALANCE)}
      {qtyTable(wh, setWh)}

      {head("3. Tồn kho nguyên liệu chưa sản xuất (quy khô)", false, HINT_STOCK_BALANCE)}
      <label style={{ display: "block", maxWidth: 260 }}>
        {fieldLabel("Số lượng", "tấn")}
        {numInput(num(data.stock_material), (v) => setData((d) => ({ ...d, stock_material: v })), readOnly, undefined, TONNES_STOCK)}
      </label>

      {isParent && (
        <>
          {head("4. Chi phí cấp công ty mẹ", false, "công ty mẹ tự khai")}
          <div style={gridStyle}>
            <label style={{ display: "block" }}>
              {fieldLabel("Tổng chi phí", "triệu đồng")}
              {numInput(num(data.cost_total), (v) => setData((d) => ({ ...d, cost_total: v })), readOnly)}
            </label>
            <label style={{ display: "block" }}>
              {fieldLabel("Trong đó: mua từ công ty con", "triệu đồng")}
              {numInput(num(data.internal_purchase_cost), (v) => setData((d) => ({ ...d, internal_purchase_cost: v })), readOnly)}
            </label>
          </div>
          <div className="form-note" style={{ fontSize: 11.5, marginTop: 6 }}>
            Ô này do <b>công ty mẹ tự tính và tự chịu trách nhiệm</b> — hệ thống <b>không đối soát</b>
            {" "}với tổng chi phí ghi trên từng dòng bán của các công ty con.
          </div>
        </>
      )}

      {head("Tổng hợp tồn kho")}
      <div style={gridStyle}>
        {box("Tồn kho thành phẩm", "tấn", (stockTonnesTotal(notWh) + stockTonnesTotal(wh)) || null)}
      </div>

      {!readOnly && footer?.(dirty, current, NO_PRICES)}
    </div>
  );
}
