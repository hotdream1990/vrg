/* Form nhập biểu THU MUA (1 đơn vị / 1 ngày): mủ nước · mủ chén · MỦ DÂY · THÀNH PHẨM (mua lại mủ
   đã chế biến).
   - Cả 3 loại mủ nguyên liệu khai GIỐNG NHAU: một ô sản lượng theo TẤN QUY KHÔ + một ô đơn giá.
     (Cặp "chưa quy khô / quy khô" chỉ có ở DÒNG HỢP ĐỒNG BÁN, nơi tiền tính trên số chưa quy khô.)
   - Đơn vị nước ngoài: đơn giá 3 loại mủ nguyên liệu nhập theo NỘI TỆ (LAK/KHR) + tỷ giá nội tệ→VND
     → đơn giá VND tự quy đổi và ghi vào kho "Giá mủ nguyên liệu".
   - Thu mua thành phẩm = BẢNG NHIỀU DÒNG theo CHỦNG LOẠI (mỗi dòng chọn VNĐ hay USD + tỷ giá,
     có nút lấy tỷ giá VCB cho mọi dòng USD) — giống bảng tiêu thụ/tồn kho.
   - Phần TIÊU THỤ mủ thu mua/thành phẩm đã chuyển sang biểu Tiêu thụ (ConsumptionForm). */

import { Checkbox, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { PRICE_CUP, PRICE_LACE, PRICE_LATEX, TONNES_DAILY } from "../../../lib/entry-bounds";
import {
  CUP_PRICE_UNIT, DRY_BASIS_HINT, LACE_PRICE_UNIT, LATEX_PRICE_UNIT,
} from "../../../lib/purchase-price-unit";
import { fetchVcbRate } from "../../../lib/market-quote-client";
import { HINT_DAILY_EVENT } from "../../../lib/unit-daily-entry-hints";
import type { PriceDraft, UnitPurchasePrice } from "../../../lib/unit-daily-client";
import { type Values, fmtNum } from "../../../lib/unit-daily-fields";
import { type FinishedLine, finishedTotals } from "../../../lib/unit-daily-purchase";
import { type PurchaseValues, purchaseWarnings } from "../../../lib/unit-daily-warnings";
import EntryWarnBanner from "../sections/EntryWarnBanner";
import FinishedPurchaseTable from "./FinishedPurchaseTable";
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

/** Các dòng thu mua thành phẩm đã lưu (bảng nhiều dòng — nằm ngoài các ô số phẳng). */
const initFinished = (values: Values): FinishedLine[] => {
  const rows = (values as unknown as { finished?: FinishedLine[] }).finished;
  return Array.isArray(rows) ? rows.map((r) => ({ ...r })) : [];
};

/** Dựng nháp ban đầu từ payload đã lưu + đơn giá VND (đơn vị VN prefill đơn giá VND, nước ngoài prefill nội tệ). */
function initDraft(values: Values, linked: UnitPurchasePrice | null | undefined, foreign: boolean): Values {
  const base: Values = {
    latex_wet: values.latex_wet, coagulum: values.coagulum, lace: values.lace,
  };
  if (foreign) {
    return {
      ...base,
      price_latex_local: values.price_latex_local, price_cup_local: values.price_cup_local,
      price_lace_local: values.price_lace_local,
      fx_purchase: values.fx_purchase,
    };
  }
  return {
    ...base,
    price_latex_vnd: linked?.latex ?? undefined, price_cup_vnd: linked?.cup ?? undefined,
    price_lace_vnd: linked?.lace ?? undefined,
  };
}

export default function PurchaseForm({
  values, readOnly, formKey, currency, linkedPrice, onDirty, footer,
}: Props) {
  const foreign = (currency ?? "VND") !== "VND";
  const origNoPurchase = (values as Record<string, unknown>).no_purchase === true;
  const [draft, setDraft] = useState<Values>(() => initDraft(values, linkedPrice, foreign));
  // Thu mua thành phẩm: bảng nhiều dòng theo chủng loại (giữ state riêng với các ô số phẳng).
  const [finished, setFinished] = useState<FinishedLine[]>(() => initFinished(values));
  // Hôm nay KHÔNG tổ chức thu mua — khác hẳn "có tổ chức, có công bố giá nhưng mua được 0 tấn".
  const [noPurchase, setNoPurchase] = useState(origNoPurchase);
  const [fxLoading, setFxLoading] = useState(false);
  useEffect(() => {
    setDraft(initDraft(values, linkedPrice, foreign));
    setFinished(initFinished(values));
    setNoPurchase((values as Record<string, unknown>).no_purchase === true);
  }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: string, v: number | null) => setDraft((d) => ({ ...d, [key]: v ?? undefined }));

  // Quy đổi về VND (base đồng).
  const priceLatexVnd = foreign ? mul(draft.price_latex_local, draft.fx_purchase) : num(draft.price_latex_vnd);
  const priceCupVnd = foreign ? mul(draft.price_cup_local, draft.fx_purchase) : num(draft.price_cup_vnd);
  const priceLaceVnd = foreign ? mul(draft.price_lace_local, draft.fx_purchase) : num(draft.price_lace_vnd);

  const fin = finishedTotals(finished);

  // Payload lưu (đồng) + đơn giá VND ghi kho giá.
  const current = useMemo<Values>(() => {
    const p: Values = {
      latex_wet: draft.latex_wet, coagulum: draft.coagulum, lace: draft.lace,
    };
    if (foreign) {
      Object.assign(p, {
        price_latex_local: draft.price_latex_local, price_cup_local: draft.price_cup_local,
        price_lace_local: draft.price_lace_local,
        fx_purchase: draft.fx_purchase,
      });
    }
    (p as Record<string, unknown>).finished = finished;
    if (noPurchase) (p as Record<string, unknown>).no_purchase = true;
    return p;
  }, [draft, finished, foreign, noPurchase]);
  const prices: PriceDraft = { latex: priceLatexVnd, cup: priceCupVnd, lace: priceLaceVnd };

  const dirty = useMemo(() => {
    const orig = initDraft(values, linkedPrice, foreign);
    const keys = new Set([...Object.keys(orig), ...Object.keys(draft)]);
    return noPurchase !== origNoPurchase
      || JSON.stringify(finished) !== JSON.stringify(initFinished(values))
      || [...keys].some((k) => (num(draft[k]) ?? null) !== (num(orig[k]) ?? null));
  }, [draft, finished, values, linkedPrice, foreign, noPurchase, origNoPurchase]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Lấy tỷ giá VCB rồi điền cho MỌI dòng thành phẩm đang chọn USD — khỏi gõ lại từng dòng. */
  const fetchFx = async () => {
    setFxLoading(true);
    try {
      const r = await fetchVcbRate();
      const rate = r.mua_ck ?? r.ban ?? r.mua_tm;
      if (rate == null) throw new Error("VCB không có tỷ giá USD");
      setFinished((rows) => rows.map((l) => ((l.ccy ?? "VND") === "USD" ? { ...l, fx: rate } : l)));
      message.success(`Đã điền tỷ giá USD/VND (VCB ${r.date}): ${fmtNum(rate, 0)} cho các dòng USD.`);
    } catch (e) {
      message.error((e as Error).message || "Không lấy được tỷ giá VCB — nhập tay giúp anh.");
    } finally {
      setFxLoading(false);
    }
  };

  const gridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 10, alignItems: "end" } as const;
  const head = (t: string, first?: boolean, hint?: string) => (
    <div style={{
      gridColumn: "1 / -1", fontWeight: 600, fontSize: 12.5, opacity: 0.85,
      marginTop: first ? 0 : 8, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)",
    }}>
      {t}
      {hint && <span style={{ fontWeight: 400, opacity: 0.7 }}> ({hint})</span>}
    </div>
  );
  const field = (label: React.ReactNode, unit: string | undefined, node: React.ReactNode) => (
    <label style={{ display: "block" }}>{fieldLabel(label, unit)}{node}</label>
  );

  // Gom cảnh báo về đầu form. Ngày không tổ chức thu mua thì mọi ô để trống → không nhắc gì.
  const warnings = useMemo(
    () => (readOnly || noPurchase ? [] : purchaseWarnings({ ...draft, finished } as PurchaseValues)),
    [draft, finished, readOnly, noPurchase],
  );

  return (
    <div>
      <EntryWarnBanner items={warnings} />
      <div style={{ marginBottom: 12, padding: "10px 12px", borderRadius: 8,
                    background: "rgba(125,125,125,.08)", border: "1px solid rgba(125,125,125,.2)" }}>
        <Checkbox checked={noPurchase} disabled={readOnly}
                  onChange={(e) => setNoPurchase(e.target.checked)}>
          <b>Hôm nay đơn vị KHÔNG tổ chức thu mua</b>
        </Checkbox>
        <div className="form-note" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.55 }}>
          Chỉ tích khi <b>không tổ chức thu mua</b>. Nếu có công bố giá và có tổ chức mua nhưng
          <b> không mua được</b> thì <b>đừng tích</b> — hãy nhập <b>sản lượng 0</b> kèm{" "}
          <b>đúng mức giá đã công bố</b>{" "}
          (không mua được ở mọi mức thì nhập 0 với <b>mức giá thấp nhất</b> đang công bố).
          Hai trường hợp này khác nhau khi tổng hợp báo cáo.
        </div>
      </div>

      <div style={{ ...gridStyle, opacity: noPurchase ? 0.5 : 1 }}>
        <div className="form-note" style={{ gridColumn: "1 / -1", fontSize: 11.5 }}>
          Sản lượng của <b>cả 3 loại mủ nguyên liệu</b> dưới đây nhập theo <b>tấn quy khô</b>{" "}
          (<b>{DRY_BASIS_HINT}</b>), không phải khối lượng mủ tươi cân được. Đơn giá: mủ nước theo{" "}
          <b>độ TSC</b>, mủ chén và mủ dây theo <b>độ DRC</b>. Riêng <b>Thu mua thành phẩm</b> là số
          lượng thực mua (hàng đã chế biến, không quy đổi).
        </div>
        {head("Mủ nước", true, HINT_DAILY_EVENT)}
        {field("Sản lượng thu mua", "tấn quy khô", numInput(num(draft.latex_wet), (v) => set("latex_wet", v), readOnly, undefined, TONNES_DAILY))}
        {foreign ? (
          <>
            {field("Đơn giá thu mua", `${currency}/độ TSC`, numInput(num(draft.price_latex_local), (v) => set("price_latex_local", v), readOnly))}
            {field("Đơn giá thu mua", LATEX_PRICE_UNIT, readOnlyBox(fmtNum(priceLatexVnd, 0), "tự quy đổi"))}
          </>
        ) : (
          field("Đơn giá thu mua", LATEX_PRICE_UNIT, numInput(num(draft.price_latex_vnd), (v) => set("price_latex_vnd", v), readOnly, undefined, PRICE_LATEX))
        )}

        {head("Mủ chén", false, HINT_DAILY_EVENT)}
        {field("Sản lượng thu mua", "tấn quy khô", numInput(num(draft.coagulum), (v) => set("coagulum", v), readOnly, undefined, TONNES_DAILY))}
        {foreign ? (
          <>
            {field("Đơn giá thu mua", `${currency}/độ DRC`, numInput(num(draft.price_cup_local), (v) => set("price_cup_local", v), readOnly))}
            {field("Đơn giá thu mua", CUP_PRICE_UNIT, readOnlyBox(fmtNum(priceCupVnd, 0), "tự quy đổi"))}
          </>
        ) : (
          field("Đơn giá thu mua", CUP_PRICE_UNIT, numInput(num(draft.price_cup_vnd), (v) => set("price_cup_vnd", v), readOnly, undefined, PRICE_CUP))
        )}

        {/* MỦ DÂY (chốt 28/08/2026) — đặt CUỐI, sau mủ nước và mủ chén, theo đúng thứ tự khách chốt. */}
        {head("Mủ dây", false, HINT_DAILY_EVENT)}
        {field("Sản lượng thu mua", "tấn quy khô", numInput(num(draft.lace), (v) => set("lace", v), readOnly, undefined, TONNES_DAILY))}
        {foreign ? (
          <>
            {field("Đơn giá thu mua", `${currency}/độ DRC`, numInput(num(draft.price_lace_local), (v) => set("price_lace_local", v), readOnly))}
            {field("Đơn giá thu mua", LACE_PRICE_UNIT, readOnlyBox(fmtNum(priceLaceVnd, 0), "tự quy đổi"))}
          </>
        ) : (
          field("Đơn giá thu mua", LACE_PRICE_UNIT, numInput(num(draft.price_lace_vnd), (v) => set("price_lace_vnd", v), readOnly, undefined, PRICE_LACE))
        )}
        <div className="form-note" style={{ gridColumn: "1 / -1", fontSize: 11.5 }}>
          Đơn giá <b>để trống</b> hoặc <b>bằng 0</b> = ngày đó <b>không có giá thu mua</b>: hệ thống
          không lưu mức giá 0 (mở lại ô sẽ trống), và ngày đó không được tính vào giá bình quân
          hay khoảng giá khu vực trong bản tin. Sản lượng vẫn lưu bình thường.
        </div>

        {foreign && (
          <>
            {head("Tỷ giá thu mua")}
            {field(<>Tỷ giá <span style={{ opacity: 0.6 }}>(1 {currency} = ? VND)</span></>, undefined,
              numInput(num(draft.fx_purchase), (v) => set("fx_purchase", v), readOnly))}
          </>
        )}

      </div>

      {/* Thu mua THÀNH PHẨM — mua lại mủ đã chế biến; mỗi CHỦNG LOẠI 1 dòng, đơn giá theo VNĐ hay USD. */}
      <div style={{ opacity: noPurchase ? 0.5 : 1, marginTop: 14 }}>
        {head("Thu mua thành phẩm", true, HINT_DAILY_EVENT)}
        <FinishedPurchaseTable rows={finished} setRows={setFinished} readOnly={readOnly} />
        {!readOnly && (
          <div style={{ marginTop: 8 }}>
            <button type="button" className="btn" style={{ fontSize: 12 }} onClick={fetchFx} disabled={fxLoading}>
              {fxLoading ? "Đang lấy…" : "Lấy tỷ giá VCB cho các dòng USD"}
            </button>
          </div>
        )}
        <div className="form-note" style={{ fontSize: 11.5, marginTop: 8 }}>
          Mỗi chủng loại mua trong ngày là <b>một dòng riêng</b>. Đơn giá nhập theo loại tiền chọn ở
          cột <b>Tiền</b>: VNĐ thì <b>triệu đ/tấn</b>, USD thì <b>USD/tấn</b> — dòng nào chọn USD thì
          nhập <b>tỷ giá</b> ngay ở dòng đó{!readOnly && " (nút trên điền tỷ giá Vietcombank cho mọi dòng USD)"}.
        </div>

        {fin.qty > 0 && (
          <div style={{ ...gridStyle, marginTop: 10 }}>
            {field("Tổng SL thành phẩm", "tấn", readOnlyBox(fmtNum(fin.qty, 3), "tự tính"))}
            {field("Tổng giá trị", "triệu đồng", readOnlyBox(fmtNum(fin.valueVnd / 1_000_000, 1), "tự tính"))}
            {field("Đơn giá bình quân", "triệu đ/tấn", readOnlyBox(fmtNum(fin.avgPriceTrieu, 2), "tự tính"))}
          </div>
        )}
      </div>

      {!readOnly && footer?.(dirty, current, prices)}
    </div>
  );
}
