/* Form nhập biểu THU MUA (1 đơn vị / 1 ngày): mủ nước · mủ chén · THÀNH PHẨM (mua lại mủ đã chế biến).
   - Đơn vị nước ngoài: đơn giá mủ nước/mủ chén nhập theo NỘI TỆ (LAK/KHR) + tỷ giá nội tệ→VND
     → đơn giá VND tự quy đổi và ghi vào kho "Giá mủ nguyên liệu".
   - Thu mua thành phẩm nhập được CẢ đơn giá VNĐ lẫn ngoại tệ (kèm tỷ giá, có nút lấy VCB).
   - Phần TIÊU THỤ mủ thu mua/thành phẩm đã chuyển sang biểu Tiêu thụ (ConsumptionForm). */

import { Checkbox, Select, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { fetchVcbRate } from "../../../lib/market-quote-client";
import type { CupBasis, PriceDraft, UnitPurchasePrice } from "../../../lib/unit-daily-client";
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

const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const mul = (a?: number | null, b?: number | null): number | null =>
  num(a) == null || num(b) == null ? null : (a as number) * (b as number);

/** Cách tính độ của mủ chén — đổi nhãn đơn giá + đơn vị ghi kèm khi ghi vào kho "Giá mủ nguyên liệu". */
const CUP_BASES: { value: CupBasis; label: string }[] = [
  { value: "tsc", label: "Độ TSC" },
  { value: "drc", label: "Độ DRC" },
];

/** Dựng nháp ban đầu từ payload đã lưu + đơn giá VND (đơn vị VN prefill đơn giá VND, nước ngoài prefill nội tệ). */
function initDraft(values: Values, linked: UnitPurchasePrice | null | undefined, foreign: boolean): Values {
  const base: Values = {
    latex_wet: values.latex_wet, coagulum: values.coagulum,
    // Thu mua thành phẩm — nhập được cả đơn giá VNĐ lẫn ngoại tệ.
    finished_qty: values.finished_qty, price_finished_vnd: values.price_finished_vnd,
    price_finished_fx: values.price_finished_fx, fx_finished: values.fx_finished,
  };
  if (foreign) {
    return {
      ...base,
      price_latex_local: values.price_latex_local, price_cup_local: values.price_cup_local,
      fx_purchase: values.fx_purchase,
    };
  }
  return {
    ...base,
    price_latex_vnd: linked?.latex ?? undefined, price_cup_vnd: linked?.cup ?? undefined,
  };
}

export default function PurchaseForm({
  values, readOnly, formKey, currency, linkedPrice, onDirty, footer,
}: Props) {
  const foreign = (currency ?? "VND") !== "VND";
  const origBasis = ((values as Record<string, unknown>).cup_basis as CupBasis) ?? "tsc";
  const origNoPurchase = (values as Record<string, unknown>).no_purchase === true;
  const [draft, setDraft] = useState<Values>(() => initDraft(values, linkedPrice, foreign));
  const [cupBasis, setCupBasis] = useState<CupBasis>(origBasis);
  // Hôm nay KHÔNG tổ chức thu mua — khác hẳn "có tổ chức, có công bố giá nhưng mua được 0 tấn".
  const [noPurchase, setNoPurchase] = useState(origNoPurchase);
  const [fxLoading, setFxLoading] = useState(false);
  useEffect(() => {
    setDraft(initDraft(values, linkedPrice, foreign));
    setCupBasis(((values as Record<string, unknown>).cup_basis as CupBasis) ?? "tsc");
    setNoPurchase((values as Record<string, unknown>).no_purchase === true);
  }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const cupUnit = cupBasis === "drc" ? "độ DRC" : "độ TSC";

  const set = (key: string, v: number | null) => setDraft((d) => ({ ...d, [key]: v ?? undefined }));

  // Quy đổi về VND (base đồng).
  const priceLatexVnd = foreign ? mul(draft.price_latex_local, draft.fx_purchase) : num(draft.price_latex_vnd);
  const priceCupVnd = foreign ? mul(draft.price_cup_local, draft.fx_purchase) : num(draft.price_cup_vnd);

  // Payload lưu (đồng) + đơn giá VND ghi kho giá.
  const current = useMemo<Values>(() => {
    const p: Values = {
      latex_wet: draft.latex_wet, coagulum: draft.coagulum,
      finished_qty: draft.finished_qty, price_finished_vnd: draft.price_finished_vnd,
      price_finished_fx: draft.price_finished_fx, fx_finished: draft.fx_finished,
    };
    if (foreign) {
      Object.assign(p, {
        price_latex_local: draft.price_latex_local, price_cup_local: draft.price_cup_local,
        fx_purchase: draft.fx_purchase,
      });
    }
    (p as Record<string, unknown>).cup_basis = cupBasis;
    if (noPurchase) (p as Record<string, unknown>).no_purchase = true;
    return p;
  }, [draft, foreign, cupBasis, noPurchase]);
  const prices: PriceDraft = { latex: priceLatexVnd, cup: priceCupVnd, cupBasis };

  const dirty = useMemo(() => {
    const orig = initDraft(values, linkedPrice, foreign);
    const keys = new Set([...Object.keys(orig), ...Object.keys(draft)]);
    return cupBasis !== origBasis || noPurchase !== origNoPurchase
      || [...keys].some((k) => (num(draft[k]) ?? null) !== (num(orig[k]) ?? null));
  }, [draft, values, linkedPrice, foreign, cupBasis, origBasis, noPurchase, origNoPurchase]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchFx = async () => {
    setFxLoading(true);
    try {
      const r = await fetchVcbRate();
      const rate = r.mua_ck ?? r.ban ?? r.mua_tm;
      if (rate == null) throw new Error("VCB không có tỷ giá USD");
      set("fx_finished", rate);
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
      <div style={{ marginBottom: 12, padding: "10px 12px", borderRadius: 8,
                    background: "rgba(125,125,125,.08)", border: "1px solid rgba(125,125,125,.2)" }}>
        <Checkbox checked={noPurchase} disabled={readOnly}
                  onChange={(e) => setNoPurchase(e.target.checked)}>
          <b>Hôm nay đơn vị KHÔNG tổ chức thu mua</b>
        </Checkbox>
        <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 6, lineHeight: 1.55 }}>
          Chỉ tích khi <b>không tổ chức thu mua</b>. Nếu có công bố giá và có tổ chức mua nhưng
          <b> không mua được</b> thì <b>đừng tích</b> — hãy nhập <b>sản lượng 0</b> kèm{" "}
          <b>đúng mức giá đã công bố</b>{" "}
          (không mua được ở mọi mức thì nhập 0 với <b>mức giá thấp nhất</b> đang công bố).
          Hai trường hợp này khác nhau khi tổng hợp báo cáo.
        </div>
      </div>

      <div style={{ ...gridStyle, opacity: noPurchase ? 0.5 : 1 }}>
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
        {/* Mủ chén tính theo độ TSC hoặc độ DRC — đơn vị tự chọn, đổi luôn nhãn các ô đơn giá bên dưới. */}
        {field("Đơn giá tính theo", undefined, (
          <Select size="small" style={{ width: "100%" }} value={cupBasis} disabled={readOnly}
                  onChange={(v) => setCupBasis(v)} options={CUP_BASES} />
        ))}
        {foreign ? (
          <>
            {field("Đơn giá thu mua", `${currency}/${cupUnit}`, numInput(num(draft.price_cup_local), (v) => set("price_cup_local", v), readOnly))}
            {field("Đơn giá thu mua", `đồng/${cupUnit}`, readOnlyBox(fmtNum(priceCupVnd, 0), "tự quy đổi"))}
          </>
        ) : (
          field("Đơn giá thu mua", `đồng/${cupUnit}`, numInput(num(draft.price_cup_vnd), (v) => set("price_cup_vnd", v), readOnly))
        )}

        {foreign && (
          <>
            {head("Tỷ giá thu mua")}
            {field(<>Tỷ giá <span style={{ opacity: 0.6 }}>(1 {currency} = ? VND)</span></>, undefined,
              numInput(num(draft.fx_purchase), (v) => set("fx_purchase", v), readOnly))}
          </>
        )}

        {/* Thu mua THÀNH PHẨM — mua lại mủ đã chế biến; cho nhập cả đơn giá VNĐ lẫn ngoại tệ. */}
        {head("Thu mua thành phẩm")}
        {field("Sản lượng thu mua", "tấn", numInput(num(draft.finished_qty), (v) => set("finished_qty", v), readOnly))}
        {field("Đơn giá (VNĐ)", "triệu đ/tấn", numInput(num(draft.price_finished_vnd), (v) => set("price_finished_vnd", v), readOnly))}
        {field("Đơn giá (ngoại tệ)", "USD/tấn", numInput(num(draft.price_finished_fx), (v) => set("price_finished_fx", v), readOnly))}
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
          {numInput(num(draft.fx_finished), (v) => set("fx_finished", v), readOnly)}
        </label>
      </div>

      {!readOnly && footer?.(dirty, current, prices)}
    </div>
  );
}
