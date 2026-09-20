/* Form nhập biểu THU MUA (1 đơn vị / 1 ngày): mủ nước · mủ chén · MỦ DÂY · THÀNH PHẨM (mua lại mủ
   đã chế biến).
   - Cả 3 loại mủ nguyên liệu khai GIỐNG NHAU (cấu hình chung ở `lib/unit-daily-purchase.MATERIALS`):
     sản lượng theo TẤN QUY KHÔ + một ô đơn giá. Sản lượng có thể TÁCH THEO CHỦNG LOẠI (bảng nhiều
     dòng, chốt 20/09/2026) — có dòng thì ô tổng là số TỰ CỘNG, chưa tách thì gõ thẳng ô tổng như cũ.
     (Cặp "chưa quy khô / quy khô" chỉ có ở DÒNG HỢP ĐỒNG BÁN, nơi tiền tính trên số chưa quy khô.)
   - ĐƠN GIÁ KHÔNG đi theo chủng loại: vẫn MỘT giá cho cả loại mủ trong ngày, vì đơn giá ghi vào
     kho "Giá mủ nguyên liệu" vốn không có chiều chủng loại.
   - Đơn vị nước ngoài: đơn giá 3 loại mủ nguyên liệu nhập theo NỘI TỆ (LAK/KHR) + tỷ giá nội tệ→VND
     → đơn giá VND tự quy đổi và ghi vào kho "Giá mủ nguyên liệu".
   - Thu mua thành phẩm = BẢNG NHIỀU DÒNG theo CHỦNG LOẠI (mỗi dòng chọn VNĐ hay USD + tỷ giá,
     có nút lấy tỷ giá VCB cho mọi dòng USD) — giống bảng tiêu thụ/tồn kho.
   - Phần TIÊU THỤ mủ thu mua/thành phẩm đã chuyển sang biểu Tiêu thụ (ConsumptionForm). */

import { Checkbox } from "antd";
import { Fragment, useEffect, useMemo, useState } from "react";

import { TONNES_DAILY } from "../../../lib/entry-bounds";
import { DRY_BASIS_HINT } from "../../../lib/purchase-price-unit";
import { HINT_DAILY_EVENT } from "../../../lib/unit-daily-entry-hints";
import type { PriceDraft, UnitPurchasePrice } from "../../../lib/unit-daily-client";
import { type Values, fmtNum } from "../../../lib/unit-daily-fields";
import {
  type FinishedLine, type Material, type MaterialGradeLine,
  MATERIALS, countedGradeRows, gradeQtyTotal,
} from "../../../lib/unit-daily-purchase";
import { type PurchaseValues, purchaseWarnings } from "../../../lib/unit-daily-warnings";
import EntryWarnBanner from "../sections/EntryWarnBanner";
import FinishedPurchaseSection from "./FinishedPurchaseSection";
import MaterialGradeTable from "./MaterialGradeTable";
import { ENTRY_GRID, entryField, numInput, readOnlyBox, sectionHead } from "./unit-daily-inputs";

type Props = {
  values: Values;
  readOnly?: boolean;
  formKey: string;
  currency?: string;                       // VND/LAK/KHR — ≠VND ⇒ đơn vị nước ngoài
  linkedPrice?: UnitPurchasePrice | null;  // đơn giá VND đúng ngày (từ kho "Giá mủ nguyên liệu")
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values, prices: PriceDraft) => React.ReactNode;
};

/** Các bảng chủng loại của 3 loại mủ nguyên liệu: {khoá bảng: các dòng}. */
type GradeRows = Record<string, MaterialGradeLine[]>;

const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const mul = (a?: number | null, b?: number | null): number | null =>
  num(a) == null || num(b) == null ? null : (a as number) * (b as number);
const rowsOf = (v: Values, key: string): MaterialGradeLine[] => {
  const rows = (v as unknown as Record<string, unknown>)[key];
  return Array.isArray(rows) ? (rows as MaterialGradeLine[]).map((r) => ({ ...r })) : [];
};

/** Các dòng thu mua thành phẩm đã lưu (bảng nhiều dòng — nằm ngoài các ô số phẳng). */
const initFinished = (values: Values): FinishedLine[] => {
  const rows = (values as unknown as { finished?: FinishedLine[] }).finished;
  return Array.isArray(rows) ? rows.map((r) => ({ ...r })) : [];
};

/** Bảng chủng loại đã lưu của cả 3 loại mủ (bản ghi cũ chưa tách chủng loại → bảng rỗng). */
const initGrades = (values: Values): GradeRows =>
  Object.fromEntries(MATERIALS.map((m) => [m.table, rowsOf(values, m.table)]));

/** Dựng nháp ban đầu từ payload đã lưu + đơn giá VND (đơn vị VN prefill đơn giá VND, nước ngoài prefill nội tệ). */
function initDraft(values: Values, linked: UnitPurchasePrice | null | undefined, foreign: boolean): Values {
  const v = values as unknown as Record<string, unknown>;
  const out: Values = {};
  for (const m of MATERIALS) {
    out[m.total] = values[m.total];
    if (foreign) { out[m.localKey] = values[m.localKey]; continue; }
    // Kho giá KHÔNG lưu số 0 (0 = không có giá), nên đơn vị đã khai 0 mà mở lại thấy ô trắng thì
    // tưởng hệ thống nuốt mất số. Cờ `no_price_*` giữ đúng lời khai → hiện lại đúng số 0.
    const saved = linked?.[m.key];
    out[m.vndKey] = saved != null ? saved : (v[m.noPriceFlag] === true ? 0 : undefined);
  }
  if (foreign) out.fx_purchase = values.fx_purchase;
  return out;
}

export default function PurchaseForm({
  values, readOnly, formKey, currency, linkedPrice, onDirty, footer,
}: Props) {
  const foreign = (currency ?? "VND") !== "VND";
  const origNoPurchase = (values as Record<string, unknown>).no_purchase === true;
  const [draft, setDraft] = useState<Values>(() => initDraft(values, linkedPrice, foreign));
  // Mủ nguyên liệu tách theo chủng loại + thu mua thành phẩm: bảng nhiều dòng, state riêng với ô số phẳng.
  const [grades, setGradeRows] = useState<GradeRows>(() => initGrades(values));
  const [finished, setFinished] = useState<FinishedLine[]>(() => initFinished(values));
  // Hôm nay KHÔNG tổ chức thu mua — khác hẳn "có tổ chức, có công bố giá nhưng mua được 0 tấn".
  const [noPurchase, setNoPurchase] = useState(origNoPurchase);
  useEffect(() => {
    setDraft(initDraft(values, linkedPrice, foreign));
    setGradeRows(initGrades(values));
    setFinished(initFinished(values));
    setNoPurchase((values as Record<string, unknown>).no_purchase === true);
  }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: string, v: number | null) => setDraft((d) => ({ ...d, [key]: v ?? undefined }));

  /** Đổi bảng chủng loại của 1 loại mủ. Xoá tới dòng CUỐI CÙNG mà trước đó có dòng ĐƯỢC TÍNH thì
      chép số vừa cộng được xuống ô tổng: ô tổng mở lại cho gõ tay và người nhập không mất trắng
      số vừa khai. Xoá dòng còn trống thì KHÔNG đụng vào ô tổng (giữ số cũ của ngày đó). */
  const setGrades = (m: Material, next: MaterialGradeLine[]) => {
    const prev = grades[m.table] ?? [];
    if (!next.length && countedGradeRows(prev).length) set(m.total, gradeQtyTotal(prev));
    setGradeRows((g) => ({ ...g, [m.table]: next }));
  };

  /** Sản lượng thực của 1 loại mủ: có dòng chủng loại ĐƯỢC TÍNH → TỔNG các dòng (giống hệt cách
      server cộng), chưa có → ô tổng gõ tay (dữ liệu cũ + dòng vừa thêm còn trống). */
  const totalOf = (m: Material): number | null => {
    const rows = countedGradeRows(grades[m.table]);
    return rows.length ? gradeQtyTotal(rows) : num(draft[m.total]);
  };

  // Đơn giá quy về VND (base đồng) cho cả 3 loại mủ.
  const prices = useMemo<PriceDraft>(() => {
    const p: PriceDraft = { latex: null, cup: null, lace: null };
    for (const m of MATERIALS) {
      p[m.key] = foreign ? mul(draft[m.localKey], draft.fx_purchase) : num(draft[m.vndKey]);
    }
    return p;
  }, [draft, foreign]);

  // Payload lưu (đồng) + đơn giá VND ghi kho giá.
  const current = useMemo<Values>(() => {
    const p: Values = {};
    const flags = p as Record<string, unknown>;
    for (const m of MATERIALS) {
      // Có bảng chủng loại thì gửi luôn số ĐÃ CỘNG — server cũng tự cộng lại nên hai bên không lệch.
      p[m.total] = totalOf(m);
      flags[m.table] = grades[m.table] ?? [];
      if (foreign) p[m.localKey] = draft[m.localKey];
      // Gõ 0 vào ô đơn giá = "ngày này KHÔNG CÓ GIÁ" (hay gặp ở sản lượng chênh lệch sau chế biến).
      // Số 0 không được lưu thành một mức giá, nên phải ghi lại chính lời khai đó — nếu không, mở
      // phiếu ra lại thấy ô trắng và các bảng soát cứ nhắc "chưa nhập đơn giá".
      if (prices[m.key] === 0) flags[m.noPriceFlag] = true;
    }
    if (foreign) p.fx_purchase = draft.fx_purchase;
    flags.finished = finished;
    if (noPurchase) flags.no_purchase = true;
    return p;
  }, [draft, grades, finished, foreign, noPurchase, prices]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(() => {
    const orig = initDraft(values, linkedPrice, foreign);
    const keys = new Set([...Object.keys(orig), ...Object.keys(draft)]);
    return noPurchase !== origNoPurchase
      || JSON.stringify(finished) !== JSON.stringify(initFinished(values))
      || JSON.stringify(grades) !== JSON.stringify(initGrades(values))
      || [...keys].some((k) => (num(draft[k]) ?? null) !== (num(orig[k]) ?? null));
  }, [draft, grades, finished, values, linkedPrice, foreign, noPurchase, origNoPurchase]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  // Gom cảnh báo về đầu form. Ngày không tổ chức thu mua thì mọi ô để trống → không nhắc gì.
  const warnings = useMemo(() => {
    if (readOnly || noPurchase) return [];
    const v = { ...draft, ...grades, finished } as unknown as Record<string, unknown>;
    for (const m of MATERIALS) v[m.total] = totalOf(m);   // soát số tổng THỰC (đã cộng từ các dòng)
    return purchaseWarnings(v as PurchaseValues);
  }, [draft, grades, finished, readOnly, noPurchase]); // eslint-disable-line react-hooks/exhaustive-deps

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

      <div style={{ ...ENTRY_GRID, opacity: noPurchase ? 0.5 : 1 }}>
        <div className="form-note" style={{ gridColumn: "1 / -1", fontSize: 11.5 }}>
          Sản lượng của <b>cả 3 loại mủ nguyên liệu</b> dưới đây nhập theo <b>tấn quy khô</b>{" "}
          (<b>{DRY_BASIS_HINT}</b>), không phải khối lượng mủ tươi cân được. Đơn giá: mủ nước theo{" "}
          <b>độ TSC</b>, mủ chén và mủ dây theo <b>độ DRC</b> — và <b>đơn giá là một ô chung</b> cho
          cả loại mủ trong ngày, kể cả khi sản lượng đã tách theo chủng loại. Riêng{" "}
          <b>Thu mua thành phẩm</b> là số lượng thực mua (hàng đã chế biến, không quy đổi).
        </div>

        {MATERIALS.map((m, i) => {
          const rows = grades[m.table] ?? [];
          const counted = countedGradeRows(rows).length;   // ô tổng chỉ khoá khi dòng đã có số
          return (
            <Fragment key={m.key}>
              {sectionHead(m.label, i === 0, HINT_DAILY_EVENT)}
              {(rows.length > 0 || !readOnly) && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <MaterialGradeTable label={m.label} rows={rows} readOnly={readOnly}
                    setRows={(next) => setGrades(m, next)} />
                </div>
              )}
              {entryField("Sản lượng thu mua", "tấn quy khô", counted
                ? readOnlyBox(fmtNum(gradeQtyTotal(rows), 3), "tự cộng từ các dòng")
                : numInput(num(draft[m.total]), (v) => set(m.total, v), readOnly, undefined, TONNES_DAILY))}
              {foreign ? (
                <>
                  {entryField("Đơn giá thu mua", `${currency}/${m.degree}`,
                    numInput(num(draft[m.localKey]), (v) => set(m.localKey, v), readOnly))}
                  {entryField("Đơn giá thu mua", m.priceUnit, readOnlyBox(fmtNum(prices[m.key], 0), "tự quy đổi"))}
                </>
              ) : (
                entryField("Đơn giá thu mua", m.priceUnit,
                  numInput(num(draft[m.vndKey]), (v) => set(m.vndKey, v), readOnly, undefined, m.priceBound))
              )}
            </Fragment>
          );
        })}

        <div className="form-note" style={{ gridColumn: "1 / -1", fontSize: 11.5 }}>
          Đơn giá <b>để trống</b> hoặc <b>bằng 0</b> = ngày đó <b>không có giá thu mua</b>: hệ thống
          không lưu mức giá 0 (mở lại ô sẽ trống), và ngày đó không được tính vào giá bình quân
          hay khoảng giá khu vực trong bản tin. Sản lượng vẫn lưu bình thường.
        </div>

        {foreign && (
          <>
            {sectionHead("Tỷ giá thu mua")}
            {entryField(<>Tỷ giá <span style={{ opacity: 0.6 }}>(1 {currency} = ? VND)</span></>, undefined,
              numInput(num(draft.fx_purchase), (v) => set("fx_purchase", v), readOnly))}
          </>
        )}

      </div>

      <FinishedPurchaseSection rows={finished} setRows={setFinished} readOnly={readOnly} dimmed={noPurchase} />

      {!readOnly && footer?.(dirty, current, prices)}
    </div>
  );
}
