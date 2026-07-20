/* Form nhập biểu TIÊU THỤ – TỒN KHO.
   - TIÊU THỤ = bảng nhiều dòng (loại HĐ · hình thức · loại mủ · SL · giá bán → doanh thu tự tính).
   - TỒN KHO (số THỜI ĐIỂM cuối ngày, đơn vị TẤN — mẫu tuần mục 11–14): chưa HĐ = bảng (chủng loại ·
     SL tấn); đã HĐ = bảng (chủng loại · tấn · đơn giá · lịch giao · file HĐ); mục 14 = tồn kho nguyên
     liệu chưa có HĐ (tấn), chỉ đơn vị CHƯA có nhà máy chế biến.
   - Giá bán (tiêu thụ) và đơn giá (tồn kho đã HĐ) cho CHỌN VND hay USD; chọn USD thì nhập tỷ giá
     USD→VND (nút lấy VCB) — tỷ giá dùng chung cho cả 2 khối. Tiền lưu BASE = đồng.
   - Tồn kho KHÔNG cộng dồn giữa các ngày; có nút "Lấy tồn ngày trước" để chép sang rồi sửa. */

import { DeleteOutlined, PlusOutlined, UploadOutlined } from "@ant-design/icons";
import { Select, Tabs, Upload, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { fetchVcbRate } from "../../../lib/market-quote-client";
import {
  type PriceDraft, type Role, fetchPrevStock, openContractFile, uploadContractFile,
} from "../../../lib/unit-daily-client";
import {
  CCYS, CHANNELS, CONTRACTS, GRADES, type Ccy, type ConsumptionData, type SaleLine,
  type StockContractLine, type StockNoContractLine, lineRevenueVnd, priceUnitOf, stockTonnesTotal,
  toTyDong, totals,
} from "../../../lib/unit-daily-consumption";
import { type Values, fmtNum } from "../../../lib/unit-daily-fields";
import { fieldLabel, numInput, readOnlyBox } from "./unit-daily-inputs";

const NO_PRICES: PriceDraft = { latex: null, cup: null };
const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);

/** Tab của biểu Tiêu thụ–Tồn kho (menu "Báo cáo tiêu thụ" / "Báo cáo tồn kho" mở sẵn tab tương ứng). */
export type ConsumptionTab = "sales" | "stock";

type Props = {
  values: Values;
  readOnly?: boolean;
  formKey: string;
  currency?: string;                       // VND/LAK/KHR — ≠VND ⇒ mặc định giá bán theo USD
  hasFactory?: boolean;                    // false ⇒ hiện tồn kho nguyên liệu (mục 14)
  role?: Role;                             // để upload file HĐ + lấy tồn ngày trước đúng endpoint
  company?: string;                        // đơn vị đang nhập (lấy tồn ngày trước)
  day?: string;                            // ngày đang nhập  (lấy tồn ngày trước)
  defaultTab?: ConsumptionTab;             // tab mở sẵn (mặc định "sales")
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values, prices: PriceDraft) => React.ReactNode;
};

/** Loại tiền mặc định khi bản ghi chưa lưu lựa chọn: đơn vị nước ngoài bán bằng USD, trong nước VND. */
const defaultCcy = (currency?: string): Ccy => ((currency ?? "VND") === "VND" ? "VND" : "USD");

function initData(values: Values, currency?: string): ConsumptionData {
  const v = values as unknown as ConsumptionData;
  const dc = defaultCcy(currency);
  return {
    sales: Array.isArray(v.sales) ? v.sales.map((l) => ({ ...l })) : [],
    sales_ccy: v.sales_ccy ?? dc,
    stock_ccy: v.stock_ccy ?? dc,
    fx_revenue: v.fx_revenue ?? null,
    stock_no_contract: Array.isArray(v.stock_no_contract) ? v.stock_no_contract.map((r) => ({ ...r })) : [],
    stock_contract: Array.isArray(v.stock_contract) ? v.stock_contract.map((r) => ({ ...r })) : [],
    stock_material: v.stock_material ?? null,
  };
}

export default function ConsumptionForm({ values, readOnly, formKey, currency, hasFactory = true, role = "member", company, day, defaultTab, onDirty, footer }: Props) {
  const [data, setData] = useState<ConsumptionData>(() => initData(values, currency));
  const [fxLoading, setFxLoading] = useState(false);
  const [prevLoading, setPrevLoading] = useState(false);
  const [uploading, setUploading] = useState<number | null>(null);
  useEffect(() => { setData(initData(values, currency)); }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const salesCcy: Ccy = data.sales_ccy ?? defaultCcy(currency);
  const stockCcy: Ccy = data.stock_ccy ?? defaultCcy(currency);
  const needFx = salesCcy === "USD" || stockCcy === "USD";

  const sales = (data.sales ?? []) as SaleLine[];
  const noHd = (data.stock_no_contract ?? []) as StockNoContractLine[];
  const hd = (data.stock_contract ?? []) as StockContractLine[];

  const setSales = (next: SaleLine[]) => setData((d) => ({ ...d, sales: next }));
  const setNoHd = (next: StockNoContractLine[]) => setData((d) => ({ ...d, stock_no_contract: next }));
  const setHd = (next: StockContractLine[]) => setData((d) => ({ ...d, stock_contract: next }));

  const agg = totals(sales, salesCcy, data.fx_revenue);

  const current = useMemo<Values>(() => {
    const p: ConsumptionData = {
      sales, revenue: agg.revenueVnd, stock_no_contract: noHd, stock_contract: hd,
      sales_ccy: salesCcy, stock_ccy: stockCcy,
    };
    if (needFx) p.fx_revenue = data.fx_revenue ?? null;
    if (!hasFactory) p.stock_material = data.stock_material ?? null;
    return p as unknown as Values;
  }, [sales, agg.revenueVnd, noHd, hd, salesCcy, stockCcy, needFx, hasFactory, data]);

  const orig = useMemo(() => initData(values, currency), [values, currency]);
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
    } catch (e) { message.error((e as Error).message || "Không lấy được tỷ giá VCB."); }
    finally { setFxLoading(false); }
  };

  /** Chép TỒN KHO của ngày gần nhất trước ngày đang nhập (tồn kho là số thời điểm, ít đổi). */
  const loadPrevStock = async () => {
    if (!company || !day) return;
    setPrevLoading(true);
    try {
      const r = await fetchPrevStock(role, company, day);
      if (!r.found) { message.info("Chưa có số tồn kho nào trước ngày này."); return; }
      setData((d) => ({
        ...d,
        stock_no_contract: (r.stock_no_contract ?? []).map((x) => ({ ...x })),
        stock_contract: (r.stock_contract ?? []).map((x) => ({ ...x })),
        stock_material: r.stock_material ?? null,
        stock_ccy: r.stock_ccy ?? d.stock_ccy,
      }));
      message.success(`Đã chép tồn kho ngày ${r.as_of} — kiểm tra và sửa lại trước khi lưu.`);
    } catch (e) { message.error((e as Error).message || "Không lấy được tồn kho ngày trước."); }
    finally { setPrevLoading(false); }
  };

  const doUpload = async (i: number, file: File) => {
    setUploading(i);
    try {
      const r = await uploadContractFile(role, file);
      setHd(hd.map((l, j) => (j === i ? { ...l, file: r.file, filename: r.filename } : l)));
      message.success("Đã tải lên file hợp đồng.");
    } catch (e) { message.error((e as Error).message || "Upload thất bại."); }
    finally { setUploading(null); }
  };

  const head = (t: string, first?: boolean) => (
    <div style={{ fontWeight: 600, fontSize: 12.5, opacity: 0.85, marginTop: first ? 0 : 18, marginBottom: 6, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)" }}>{t}</div>
  );
  const sel = { minWidth: 96, width: "100%" } as const;

  /** Ô chọn loại tiền cho 1 khối giá (giá bán tiêu thụ · đơn giá tồn kho). */
  const ccySel = (label: string, value: Ccy, on: (v: Ccy) => void) => (
    <label style={{ display: "block", maxWidth: 190 }}>
      {fieldLabel(label, undefined)}
      <Select size="small" style={{ width: "100%" }} value={value} disabled={readOnly}
              onChange={on} options={CCYS} />
    </label>
  );
  /** Ô tỷ giá USD→VND — dùng CHUNG cho giá bán và đơn giá tồn kho (cùng 1 ngày, cùng 1 tỷ giá). */
  const fxBox = (
    <label style={{ display: "block", maxWidth: 260 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, marginBottom: 2, minHeight: 18 }}>
        <span style={{ fontSize: 12, opacity: 0.75 }}>Tỷ giá <span style={{ opacity: 0.6 }}>(1 USD = ? VND)</span></span>
        {!readOnly && <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 7px", lineHeight: "18px", whiteSpace: "nowrap" }} onClick={fetchFx} disabled={fxLoading}>{fxLoading ? "Đang lấy…" : "Lấy tỷ giá hiện tại"}</button>}
      </div>
      {numInput(num(data.fx_revenue), (v) => setData((d) => ({ ...d, fx_revenue: v })), readOnly)}
    </label>
  );
  const gridStyle = { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 10, alignItems: "end" } as const;
  const box = (label: string, unit: string, value: number | null, digits = 2) => (
    <label style={{ display: "block" }}>{fieldLabel(label, unit)}{readOnlyBox(fmtNum(value, digits), "tự tính")}</label>
  );
  const gradeSel = (val: string, on: (v: string) => void) => (
    <Select size="small" style={sel} value={val || undefined} placeholder="Loại mủ" disabled={readOnly} showSearch
      onChange={on} options={GRADES.map((g) => ({ value: g, label: g }))} />
  );

  const salesTab = (
    <div>
      {head("Tiêu thụ mủ thu mua", true)}
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: 116 }}>Loại HĐ</th><th style={{ width: 122 }}>Hình thức</th><th style={{ width: 150 }}>Loại mủ</th>
            <th style={{ width: 100 }} className="r">SL (tấn)</th><th style={{ width: 120 }} className="r">Giá bán ({priceUnitOf(salesCcy)})</th>
            <th style={{ width: 120 }} className="r">Doanh thu (triệu đ)</th>{!readOnly && <th style={{ width: 34 }} />}
          </tr></thead>
          <tbody>
            {sales.map((ln, i) => (
              <tr key={i}>
                <td><Select size="small" style={sel} value={ln.contract} disabled={readOnly} onChange={(v) => setSales(sales.map((l, j) => j === i ? { ...l, contract: v } : l))} options={CONTRACTS} /></td>
                <td><Select size="small" style={sel} value={ln.channel} disabled={readOnly} onChange={(v) => setSales(sales.map((l, j) => j === i ? { ...l, channel: v } : l))} options={CHANNELS} /></td>
                <td>{gradeSel(ln.grade, (v) => setSales(sales.map((l, j) => j === i ? { ...l, grade: v } : l)))}</td>
                <td>{numInput(num(ln.qty), (v) => setSales(sales.map((l, j) => j === i ? { ...l, qty: v } : l)), readOnly)}</td>
                <td>{numInput(num(ln.price), (v) => setSales(sales.map((l, j) => j === i ? { ...l, price: v } : l)), readOnly)}</td>
                <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                  {(() => { const rv = lineRevenueVnd(ln, salesCcy, data.fx_revenue); return fmtNum(rv == null ? null : rv / 1_000_000, 1); })()}
                </td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} title="Xoá dòng" onClick={() => setSales(sales.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {sales.length === 0 && <tr><td colSpan={readOnly ? 6 : 7} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng tiêu thụ nào.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setSales([...sales, { contract: "long_term", channel: "export", grade: GRADES[0], qty: null, price: null }])}><PlusOutlined /> Thêm dòng</button>}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
        {ccySel("Giá bán nhập bằng", salesCcy, (v) => setData((d) => ({ ...d, sales_ccy: v })))}
        {salesCcy === "USD" && fxBox}
      </div>

      {head("Tổng hợp tiêu thụ")}
      <div style={gridStyle}>
        {box("Tổng tiêu thụ", "tấn", agg.qty || null)}
        {box("Tổng XK / UTXK", "tấn", agg.qtyExport || null)}
        {box("Tổng nội tiêu", "tấn", agg.qtyDomestic || null)}
        {box("HĐ Dài hạn", "tấn", agg.qtyLongTerm || null)}
        {box("HĐ Chuyến", "tấn", agg.qtySpot || null)}
        {box("Tổng doanh thu", "tỷ đồng", toTyDong(agg.revenueVnd || null), 3)}
        {box("Giá bán bình quân", "triệu đ/tấn", agg.avgPriceTrieu)}
      </div>
    </div>
  );

  const stockTab = (
    <div>
      {/* Tồn kho = số THỜI ĐIỂM cuối ngày (không cộng dồn) → cho chép nhanh từ ngày gần nhất rồi sửa. */}
      {!readOnly && company && day && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
          <button type="button" className="btn" style={{ fontSize: 12 }} onClick={loadPrevStock} disabled={prevLoading}>
            {prevLoading ? "Đang lấy…" : "Lấy tồn ngày trước"}
          </button>
          <span style={{ fontSize: 11.5, color: "var(--muted)" }}>
            Tồn kho là số tại thời điểm cuối ngày — chép sang rồi sửa cho đúng ngày này.
          </span>
        </div>
      )}

      {/* ── TỒN KHO CHƯA HĐ ── */}
      {head("Tồn kho thành phẩm — CHƯA có hợp đồng", true)}
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: 220 }}>Chủng loại</th>
            <th style={{ width: 130 }} className="r">Số lượng (tấn)</th>{!readOnly && <th style={{ width: 34 }} />}
          </tr></thead>
          <tbody>
            {noHd.map((r, i) => (
              <tr key={i}>
                <td>{gradeSel(r.grade, (v) => setNoHd(noHd.map((x, j) => j === i ? { ...x, grade: v } : x)))}</td>
                <td>{numInput(num(r.qty), (v) => setNoHd(noHd.map((x, j) => j === i ? { ...x, qty: v } : x)), readOnly)}</td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} onClick={() => setNoHd(noHd.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {noHd.length === 0 && <tr><td colSpan={readOnly ? 2 : 3} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setNoHd([...noHd, { grade: GRADES[0], qty: null }])}><PlusOutlined /> Thêm dòng</button>}

      {/* ── TỒN KHO ĐÃ HĐ ── */}
      {head("Tồn kho thành phẩm — ĐÃ có hợp đồng")}
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: 160 }}>Chủng loại</th><th style={{ width: 110 }} className="r">SL (tấn)</th>
            <th style={{ width: 130 }} className="r">Đơn giá ({priceUnitOf(stockCcy)})</th><th style={{ width: 140 }}>Lịch giao</th>
            <th style={{ width: 150 }}>File HĐ</th>{!readOnly && <th style={{ width: 34 }} />}
          </tr></thead>
          <tbody>
            {hd.map((r, i) => (
              <tr key={i}>
                <td>{gradeSel(r.grade, (v) => setHd(hd.map((x, j) => j === i ? { ...x, grade: v } : x)))}</td>
                <td>{numInput(num(r.qty), (v) => setHd(hd.map((x, j) => j === i ? { ...x, qty: v } : x)), readOnly)}</td>
                <td>{numInput(num(r.price), (v) => setHd(hd.map((x, j) => j === i ? { ...x, price: v } : x)), readOnly)}</td>
                <td><input type="date" className="blt-cell-input" style={{ width: "100%" }} value={r.delivery_date ?? ""} disabled={readOnly}
                  onChange={(e) => setHd(hd.map((x, j) => j === i ? { ...x, delivery_date: e.target.value || null } : x))} /></td>
                <td>
                  {r.file
                    ? <a onClick={() => openContractFile(role, r.file!)} style={{ cursor: "pointer", fontSize: 12 }} title={r.filename ?? ""}>📎 {(r.filename ?? "file").slice(0, 14)}</a>
                    : <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>}
                  {!readOnly && (
                    <Upload showUploadList={false} accept=".pdf,image/jpeg,image/png" disabled={uploading === i}
                      beforeUpload={(f) => { doUpload(i, f as File); return false; }}>
                      <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 6px", marginLeft: 6 }}>
                        <UploadOutlined /> {uploading === i ? "…" : (r.file ? "Đổi" : "Chọn")}
                      </button>
                    </Upload>
                  )}
                </td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} onClick={() => setHd(hd.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {hd.length === 0 && <tr><td colSpan={readOnly ? 5 : 6} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setHd([...hd, { grade: GRADES[0], qty: null, price: null, delivery_date: null, file: null, filename: null }])}><PlusOutlined /> Thêm dòng</button>}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12 }}>
        {ccySel("Đơn giá nhập bằng", stockCcy, (v) => setData((d) => ({ ...d, stock_ccy: v })))}
        {stockCcy === "USD" && salesCcy !== "USD" && fxBox}
      </div>

      {/* ── Tổng hợp tồn kho ── */}
      {head("Tổng hợp tồn kho")}
      <div style={gridStyle}>
        {box("Tồn kho chưa HĐ", "tấn", stockTonnesTotal(noHd) || null)}
        {box("Tồn kho đã HĐ", "tấn", stockTonnesTotal(hd) || null)}
        {box("Tồn kho thành phẩm", "tấn", (stockTonnesTotal(noHd) + stockTonnesTotal(hd)) || null)}
        {/* Mục 14 mẫu tuần — chỉ đơn vị CHƯA có nhà máy chế biến (cấu hình ở Đơn vị thành viên). */}
        {!hasFactory && (
          <label style={{ display: "block" }}>
            {fieldLabel("Tồn kho nguyên liệu chưa có HĐ", "tấn")}
            {numInput(num(data.stock_material), (v) => setData((d) => ({ ...d, stock_material: v })), readOnly)}
          </label>
        )}
      </div>
    </div>
  );

  return (
    <div>
      <Tabs defaultActiveKey={defaultTab ?? "sales"} items={[
        { key: "sales", label: "Tiêu thụ", children: salesTab },
        { key: "stock", label: "Tồn kho", children: stockTab },
      ]} />
      {!readOnly && footer?.(dirty, current, NO_PRICES)}
    </div>
  );
}
