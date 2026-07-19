/* Form nhập biểu THU MUA (1 đơn vị / 1 ngày). Bố trí theo loại mủ; xử lý ĐƠN VỊ NƯỚC NGOÀI:
   - Đơn giá thu mua nhập theo NỘI TỆ (LAK/KHR) + tỷ giá nội tệ→VND → đơn giá VND tự quy đổi (ghi vào kho giá).
   - Doanh thu nhập theo USD + tỷ giá USD→VND (nút "Lấy tỷ giá hiện tại" từ VCB) → doanh thu VND (cột chính).
   Tiền lưu BASE = đồng (VND). Đơn vị Việt Nam: nhập thẳng đơn giá VND + doanh thu tỷ đồng. */

import { message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { fetchVcbRate } from "../../../lib/market-quote-client";
import type { PriceDraft, UnitPurchasePrice } from "../../../lib/unit-daily-client";
import { type Values, fmtNum } from "../../../lib/unit-daily-fields";
import { fieldLabel, numInput, readOnlyBox } from "./unit-daily-inputs";

type Props = {
  values: Values;
  readOnly?: boolean;
  formKey: string;
  currency?: string;                       // VND/LAK/KHR — ≠VND ⇒ đơn vị nước ngoài
  linkedPrice?: UnitPurchasePrice | null;  // đơn giá VND đúng ngày (từ kho "Giá mủ nguyên liệu")
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values, prices: PriceDraft) => React.ReactNode;
};

const TY = 1_000_000_000; // 1 tỷ đồng = 1e9 đồng
const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const mul = (a?: number | null, b?: number | null): number | null =>
  num(a) == null || num(b) == null ? null : (a as number) * (b as number);

/** Dựng nháp ban đầu từ payload đã lưu + đơn giá VND (đơn vị VN prefill đơn giá VND, nước ngoài prefill nội tệ). */
function initDraft(values: Values, linked: UnitPurchasePrice | null | undefined, foreign: boolean): Values {
  const base: Values = {
    latex_wet: values.latex_wet, coagulum: values.coagulum, consumption: values.consumption,
  };
  if (foreign) {
    return {
      ...base,
      price_latex_local: values.price_latex_local, price_cup_local: values.price_cup_local,
      fx_purchase: values.fx_purchase, revenue_usd: values.revenue_usd, fx_revenue: values.fx_revenue,
    };
  }
  return {
    ...base,
    revenue_ty: values.revenue != null ? (values.revenue as number) / TY : undefined,
    price_latex_vnd: linked?.latex ?? undefined, price_cup_vnd: linked?.cup ?? undefined,
  };
}

export default function PurchaseForm({
  values, readOnly, formKey, currency, linkedPrice, onDirty, footer,
}: Props) {
  const foreign = (currency ?? "VND") !== "VND";
  const [draft, setDraft] = useState<Values>(() => initDraft(values, linkedPrice, foreign));
  const [fxLoading, setFxLoading] = useState(false);
  useEffect(() => { setDraft(initDraft(values, linkedPrice, foreign)); }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: string, v: number | null) => setDraft((d) => ({ ...d, [key]: v ?? undefined }));

  // Quy đổi về VND (base đồng).
  const priceLatexVnd = foreign ? mul(draft.price_latex_local, draft.fx_purchase) : num(draft.price_latex_vnd);
  const priceCupVnd = foreign ? mul(draft.price_cup_local, draft.fx_purchase) : num(draft.price_cup_vnd);
  const revenueVnd = foreign
    ? mul(draft.revenue_usd, draft.fx_revenue)
    : (num(draft.revenue_ty) != null ? (draft.revenue_ty as number) * TY : null);
  const giaBQ = revenueVnd != null && num(draft.consumption) ? revenueVnd / (draft.consumption as number) / 1_000_000 : null;

  // Payload lưu (đồng) + đơn giá VND ghi kho giá.
  const current = useMemo<Values>(() => {
    const p: Values = {
      latex_wet: draft.latex_wet, coagulum: draft.coagulum, consumption: draft.consumption,
      revenue: revenueVnd ?? undefined,
    };
    if (foreign) {
      Object.assign(p, {
        price_latex_local: draft.price_latex_local, price_cup_local: draft.price_cup_local,
        fx_purchase: draft.fx_purchase, revenue_usd: draft.revenue_usd, fx_revenue: draft.fx_revenue,
      });
    }
    return p;
  }, [draft, revenueVnd, foreign]);
  const prices: PriceDraft = { latex: priceLatexVnd, cup: priceCupVnd };

  const dirty = useMemo(() => {
    const orig = initDraft(values, linkedPrice, foreign);
    const keys = new Set([...Object.keys(orig), ...Object.keys(draft)]);
    return [...keys].some((k) => (num(draft[k]) ?? null) !== (num(orig[k]) ?? null));
  }, [draft, values, linkedPrice, foreign]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchFx = async () => {
    setFxLoading(true);
    try {
      const r = await fetchVcbRate();
      const rate = r.mua_ck ?? r.ban ?? r.mua_tm;
      if (rate == null) throw new Error("VCB không có tỷ giá USD");
      set("fx_revenue", rate);
      message.success(`Đã lấy tỷ giá USD/VND (VCB ${r.date}): ${fmtNum(rate, 0)}`);
    } catch (e) {
      message.error((e as Error).message || "Không lấy được tỷ giá VCB — nhập tay giúp anh.");
    } finally {
      setFxLoading(false);
    }
  };

  const gridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 10, alignItems: "end" } as const;
  const head = (t: string, first?: boolean) => (
    <div style={{
      gridColumn: "1 / -1", fontWeight: 600, fontSize: 12.5, opacity: 0.85,
      marginTop: first ? 0 : 8, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)",
    }}>{t}</div>
  );
  const field = (label: React.ReactNode, unit: string | undefined, node: React.ReactNode) => (
    <label style={{ display: "block" }}>{fieldLabel(label, unit)}{node}</label>
  );

  return (
    <div>
      <div style={gridStyle}>
        {head("Mủ nước", true)}
        {field("Sản lượng thu mua", "tấn", numInput(num(draft.latex_wet), (v) => set("latex_wet", v), readOnly))}
        {foreign ? (
          <>
            {field("Đơn giá thu mua", `${currency}/độ TSC`, numInput(num(draft.price_latex_local), (v) => set("price_latex_local", v), readOnly))}
            {field("Đơn giá thu mua", "đồng/độ TSC", readOnlyBox(fmtNum(priceLatexVnd, 0), "tự quy đổi"))}
          </>
        ) : (
          field("Đơn giá thu mua", "đồng/độ TSC", numInput(num(draft.price_latex_vnd), (v) => set("price_latex_vnd", v), readOnly))
        )}

        {head("Mủ chén")}
        {field("Sản lượng thu mua", "tấn", numInput(num(draft.coagulum), (v) => set("coagulum", v), readOnly))}
        {foreign ? (
          <>
            {field("Đơn giá thu mua", `${currency}/độ TSC`, numInput(num(draft.price_cup_local), (v) => set("price_cup_local", v), readOnly))}
            {field("Đơn giá thu mua", "đồng/độ TSC", readOnlyBox(fmtNum(priceCupVnd, 0), "tự quy đổi"))}
          </>
        ) : (
          field("Đơn giá thu mua", "đồng/độ TSC", numInput(num(draft.price_cup_vnd), (v) => set("price_cup_vnd", v), readOnly))
        )}

        {foreign && (
          <>
            {head("Tỷ giá thu mua")}
            {field(<>Tỷ giá <span style={{ opacity: 0.6 }}>(1 {currency} = ? VND)</span></>, undefined,
              numInput(num(draft.fx_purchase), (v) => set("fx_purchase", v), readOnly))}
          </>
        )}

        {head("Tiêu thụ mủ thu mua")}
        {field("Sản lượng tiêu thụ", "tấn", numInput(num(draft.consumption), (v) => set("consumption", v), readOnly))}
        {foreign ? (
          <>
            {field("Doanh thu", "USD", numInput(num(draft.revenue_usd), (v) => set("revenue_usd", v), readOnly))}
            <label style={{ display: "block" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, marginBottom: 2, minHeight: 18 }}>
                <span style={{ fontSize: 12, opacity: 0.75 }}>Tỷ giá <span style={{ opacity: 0.6 }}>(1 USD = ? VND)</span></span>
                {!readOnly && (
                  <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 7px", lineHeight: "18px", whiteSpace: "nowrap" }}
                          onClick={fetchFx} disabled={fxLoading}>
                    {fxLoading ? "Đang lấy…" : "Lấy tỷ giá hiện tại"}
                  </button>
                )}
              </div>
              {numInput(num(draft.fx_revenue), (v) => set("fx_revenue", v), readOnly)}
            </label>
            {field("Doanh thu", "tỷ đồng", readOnlyBox(fmtNum(revenueVnd != null ? revenueVnd / TY : null, 3), "tự quy đổi"))}
          </>
        ) : (
          field("Doanh thu", "tỷ đồng", numInput(num(draft.revenue_ty), (v) => set("revenue_ty", v), readOnly))
        )}
        {field("Giá bán bình quân", "triệu đ/tấn", readOnlyBox(fmtNum(giaBQ, 2), "tự tính"))}
      </div>

      {!readOnly && footer?.(dirty, current, prices)}
    </div>
  );
}
