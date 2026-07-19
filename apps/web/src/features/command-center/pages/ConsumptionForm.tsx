/* Form nhập biểu TIÊU THỤ – TỒN KHO. TIÊU THỤ = BẢNG NHIỀU DÒNG (mỗi dòng 1 lần thực hiện HĐ:
   loại HĐ · hình thức · loại mủ · số lượng · giá bán → doanh thu tự tính). Tổng hợp (SL theo hình thức,
   doanh thu, giá BQ) tự cộng. Đơn vị nước ngoài: giá bán USD + tỷ giá USD→VND (nút lấy VCB) → VND.
   TỒN KHO = ô phẳng. Tiền lưu BASE = đồng (VND). */

import { Select, message } from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { useEffect, useMemo, useState } from "react";

import { fetchVcbRate } from "../../../lib/market-quote-client";
import type { PriceDraft } from "../../../lib/unit-daily-client";
import {
  CHANNELS, CONTRACTS, GRADES, type ConsumptionData, type SaleLine,
  lineRevenueVnd, toTyDong, totals,
} from "../../../lib/unit-daily-consumption";
import { STOCK_COLUMNS, type Column, type Values, fmtNum, isDerived, toBase, toDisplay } from "../../../lib/unit-daily-fields";
import { fieldLabel, numInput, readOnlyBox } from "./unit-daily-inputs";

const NO_PRICES: PriceDraft = { latex: null, cup: null };
const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

type Props = {
  values: Values;
  readOnly?: boolean;
  formKey: string;
  currency?: string;                       // VND/LAK/KHR — ≠VND ⇒ nước ngoài (giá bán USD)
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values, prices: PriceDraft) => React.ReactNode;
};

function initData(values: Values): ConsumptionData {
  const v = values as unknown as ConsumptionData;
  const out: ConsumptionData = {
    sales: Array.isArray(v.sales) ? v.sales.map((l) => ({ ...l })) : [],
    fx_revenue: (v.fx_revenue as number | null) ?? null,
  };
  for (const c of STOCK_COLUMNS) if (!isDerived(c)) out[c.key] = (values[c.key] as number | null) ?? null;
  return out;
}

export default function ConsumptionForm({ values, readOnly, formKey, currency, onDirty, footer }: Props) {
  const foreign = (currency ?? "VND") !== "VND";
  const [data, setData] = useState<ConsumptionData>(() => initData(values));
  const [fxLoading, setFxLoading] = useState(false);
  useEffect(() => { setData(initData(values)); }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const sales = (data.sales ?? []) as SaleLine[];
  const setSales = (next: SaleLine[]) => setData((d) => ({ ...d, sales: next }));
  const updateLine = (i: number, patch: Partial<SaleLine>) => setSales(sales.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const addLine = () => setSales([...sales, { contract: "long_term", channel: "export", grade: GRADES[0], qty: null, price: null }]);
  const delLine = (i: number) => setSales(sales.filter((_, j) => j !== i));
  const setStock = (key: string, v: number | null) => setData((d) => ({ ...d, [key]: v }));

  const agg = totals(sales, foreign, data.fx_revenue);

  const current = useMemo<Values>(() => {
    const p: ConsumptionData = { sales, revenue: agg.revenueVnd };
    if (foreign) p.fx_revenue = data.fx_revenue ?? null;
    for (const c of STOCK_COLUMNS) if (!isDerived(c) && num(data[c.key] as number) != null) p[c.key] = data[c.key];
    return p as unknown as Values;
  }, [sales, agg.revenueVnd, foreign, data]);

  const orig = useMemo(() => initData(values), [values]);
  const dirty = useMemo(() => JSON.stringify(data) !== JSON.stringify(orig), [data, orig]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchFx = async () => {
    setFxLoading(true);
    try {
      const r = await fetchVcbRate();
      const rate = r.mua_ck ?? r.ban ?? r.mua_tm;
      if (rate == null) throw new Error("VCB không có tỷ giá USD");
      setData((d) => ({ ...d, fx_revenue: rate }));
      message.success(`Đã lấy tỷ giá USD/VND (VCB ${r.date}): ${fmtNum(rate, 0)}`);
    } catch (e) {
      message.error((e as Error).message || "Không lấy được tỷ giá VCB — nhập tay giúp anh.");
    } finally {
      setFxLoading(false);
    }
  };

  const head = (t: string, first?: boolean) => (
    <div style={{ fontWeight: 600, fontSize: 12.5, opacity: 0.85, marginTop: first ? 0 : 16, marginBottom: 6, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)" }}>{t}</div>
  );
  const priceUnit = foreign ? "USD/tấn" : "triệu đ/tấn";
  const sel = { minWidth: 96, width: "100%" } as const;

  const gridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10, alignItems: "end" } as const;
  const box = (label: string, unit: string, value: number | null, digits = 2) => (
    <label style={{ display: "block" }}>{fieldLabel(label, unit)}{readOnlyBox(fmtNum(value, digits), "tự tính")}</label>
  );

  return (
    <div>
      {head("Tiêu thụ mủ thu mua", true)}
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead>
            <tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
              <th style={{ width: 120 }}>Loại HĐ</th>
              <th style={{ width: 130 }}>Hình thức</th>
              <th style={{ width: 150 }}>Loại mủ</th>
              <th style={{ width: 110 }} className="r">Số lượng (tấn)</th>
              <th style={{ width: 130 }} className="r">Giá bán ({priceUnit})</th>
              <th style={{ width: 130 }} className="r">Doanh thu (triệu đ)</th>
              {!readOnly && <th style={{ width: 34 }} />}
            </tr>
          </thead>
          <tbody>
            {sales.map((ln, i) => (
              <tr key={i}>
                <td>
                  <Select size="small" style={sel} value={ln.contract} disabled={readOnly}
                    onChange={(v) => updateLine(i, { contract: v })} options={CONTRACTS} />
                </td>
                <td>
                  <Select size="small" style={sel} value={ln.channel} disabled={readOnly}
                    onChange={(v) => updateLine(i, { channel: v })} options={CHANNELS} />
                </td>
                <td>
                  <Select size="small" style={sel} value={ln.grade} disabled={readOnly} showSearch
                    onChange={(v) => updateLine(i, { grade: v })} options={GRADES.map((g) => ({ value: g, label: g }))} />
                </td>
                <td>{numInput(num(ln.qty), (v) => updateLine(i, { qty: v }), readOnly)}</td>
                <td>{numInput(num(ln.price), (v) => updateLine(i, { price: v }), readOnly)}</td>
                <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                  {(() => { const rv = lineRevenueVnd(ln, foreign, data.fx_revenue); return fmtNum(rv == null ? null : rv / 1_000_000, 1); })()}
                </td>
                {!readOnly && (
                  <td className="r">
                    <button type="button" className="btn" style={{ padding: "0 7px" }} title="Xoá dòng"
                      onClick={() => delLine(i)}><DeleteOutlined /></button>
                  </td>
                )}
              </tr>
            ))}
            {sales.length === 0 && (
              <tr><td colSpan={readOnly ? 6 : 7} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>
                Chưa có dòng tiêu thụ nào.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} onClick={addLine}>
          <PlusOutlined /> Thêm dòng
        </button>
      )}

      {foreign && (
        <div style={{ marginTop: 12, maxWidth: 320 }}>
          <label style={{ display: "block" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, marginBottom: 2, minHeight: 18 }}>
              <span style={{ fontSize: 12, opacity: 0.75 }}>Tỷ giá <span style={{ opacity: 0.6 }}>(1 USD = ? VND)</span></span>
              {!readOnly && (
                <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 7px", lineHeight: "18px", whiteSpace: "nowrap" }}
                  onClick={fetchFx} disabled={fxLoading}>{fxLoading ? "Đang lấy…" : "Lấy tỷ giá hiện tại"}</button>
              )}
            </div>
            {numInput(num(data.fx_revenue as number), (v) => setData((d) => ({ ...d, fx_revenue: v })), readOnly)}
          </label>
        </div>
      )}

      {head("Tổng hợp tiêu thụ")}
      <div style={gridStyle}>
        {box("Tổng tiêu thụ", "tấn", agg.qty || null, 2)}
        {box("Tổng XK / UTXK", "tấn", agg.qtyExport || null, 2)}
        {box("Tổng nội tiêu", "tấn", agg.qtyDomestic || null, 2)}
        {box("HĐ Dài hạn", "tấn", agg.qtyLongTerm || null, 2)}
        {box("HĐ Chuyến", "tấn", agg.qtySpot || null, 2)}
        {box("Tổng doanh thu", "tỷ đồng", toTyDong(agg.revenueVnd || null), 3)}
        {box("Giá bán bình quân", "triệu đ/tấn", agg.avgPriceTrieu, 2)}
      </div>

      {head("Tồn kho")}
      <div style={gridStyle}>
        {STOCK_COLUMNS.map((c: Column) => (
          <label key={c.key} style={{ display: "block" }}>
            {fieldLabel(c.label, c.unit)}
            {c.hint && <div style={{ fontSize: 11, opacity: 0.55, marginTop: -2, marginBottom: 2 }}>{c.hint}</div>}
            {isDerived(c)
              ? readOnlyBox(fmtNum(toDisplay(c, c.compute!(data as unknown as Values)), 2), "tự tính")
              : numInput(toDisplay(c, num(data[c.key] as number)), (v) => setStock(c.key, toBase(c, v)), readOnly)}
          </label>
        ))}
      </div>

      {!readOnly && footer?.(dirty, current, NO_PRICES)}
    </div>
  );
}
