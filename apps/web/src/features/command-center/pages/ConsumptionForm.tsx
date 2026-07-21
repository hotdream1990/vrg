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
  type StockQtyLine, type StockSignedLine, lineRevenueVnd, stockTonnesTotal,
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
    stock_not_warehoused: Array.isArray(v.stock_not_warehoused) ? v.stock_not_warehoused.map((r) => ({ ...r })) : [],
    stock_warehoused: Array.isArray(v.stock_warehoused) ? v.stock_warehoused.map((r) => ({ ...r })) : [],
    stock_signed_undelivered: Array.isArray(v.stock_signed_undelivered) ? v.stock_signed_undelivered.map((r) => ({ ...r })) : [],
    stock_material: v.stock_material ?? null,
  };
}

export default function ConsumptionForm({ values, readOnly, formKey, currency, role = "member", company, day, defaultTab, onDirty, footer }: Props) {
  const [data, setData] = useState<ConsumptionData>(() => initData(values, currency));
  const [fxLoading, setFxLoading] = useState(false);
  const [prevLoading, setPrevLoading] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);  // "sales:0" | "signed:0"
  useEffect(() => { setData(initData(values, currency)); }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const salesCcy: Ccy = data.sales_ccy ?? defaultCcy(currency);
  const stockCcy: Ccy = data.stock_ccy ?? defaultCcy(currency);
  const needFx = salesCcy === "USD" || stockCcy === "USD";

  const sales = (data.sales ?? []) as SaleLine[];
  const notWh = (data.stock_not_warehoused ?? []) as StockQtyLine[];      // 1 chế biến chưa nhập kho
  const wh = (data.stock_warehoused ?? []) as StockQtyLine[];             // 2 đã nhập kho
  const signed = (data.stock_signed_undelivered ?? []) as StockSignedLine[]; // 3 đã ký HĐ chưa giao

  const setSales = (next: SaleLine[]) => setData((d) => ({ ...d, sales: next }));
  const setNotWh = (next: StockQtyLine[]) => setData((d) => ({ ...d, stock_not_warehoused: next }));
  const setWh = (next: StockQtyLine[]) => setData((d) => ({ ...d, stock_warehoused: next }));
  const setSigned = (next: StockSignedLine[]) => setData((d) => ({ ...d, stock_signed_undelivered: next }));

  const agg = totals(sales);

  /** 2 dòng của khối "Tiêu thụ mủ thu mua & mủ thành phẩm" — khoá lưu tương ứng trong payload. */
  const SOLD_ROWS = [
    { label: "Mủ thu mua", qtyKey: "purchased_sold_qty", rawKey: "purchased_sold_raw",
      ccyKey: "purchased_sold_ccy", fxKey: "purchased_sold_fx", outKey: "purchased_sold_revenue" },
    { label: "Mủ thành phẩm", qtyKey: "finished_sold_qty", rawKey: "finished_sold_raw",
      ccyKey: "finished_sold_ccy", fxKey: "finished_sold_fx", outKey: "finished_sold_revenue" },
  ] as const;

  /** Doanh thu 1 dòng về BASE = đồng. VND: nhập tỷ đồng (×1e9). USD: × tỷ giá (thiếu tỷ giá → null). */
  const soldRevenueVnd = (r: (typeof SOLD_ROWS)[number]): number | null => {
    const raw = num(data[r.rawKey] as number | null);
    if (raw == null) return null;
    if (((data[r.ccyKey] as Ccy) ?? "VND") !== "USD") return raw * 1_000_000_000;
    const fx = num(data[r.fxKey] as number | null);
    return fx == null ? null : raw * fx;
  };

  /** Giá trị 1 dòng tồn kho đã có HĐ, quy về đồng (USD cần tỷ giá; thiếu tỷ giá → null, không đoán). */
  const stockLineVnd = (r: StockSignedLine): number | null => lineRevenueVnd(r);
  const stockValueVnd = signed.reduce((a, r) => a + (stockLineVnd(r) ?? 0), 0);

  const current = useMemo<Values>(() => {
    const p: ConsumptionData = {
      sales, revenue: agg.revenueVnd, sales_ccy: salesCcy, stock_ccy: stockCcy,
      stock_not_warehoused: notWh, stock_warehoused: wh, stock_signed_undelivered: signed,
    };
    if (needFx) p.fx_revenue = data.fx_revenue ?? null;
    p.stock_material = data.stock_material ?? null;   // khối 4 — mọi đơn vị đều nhập được
    return p as unknown as Values;
  }, [sales, agg.revenueVnd, notWh, wh, signed, salesCcy, stockCcy, needFx, data]);

  const orig = useMemo(() => initData(values, currency), [values, currency]);
  const dirty = useMemo(() => JSON.stringify(data) !== JSON.stringify(orig), [data, orig]);
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Lấy tỷ giá VCB rồi điền cho MỌI dòng đang chọn USD (2 bảng) — khỏi gõ lại từng dòng. */
  const fetchFx = async () => {
    setFxLoading(true);
    try {
      const r = await fetchVcbRate();
      const rate = r.mua_ck ?? r.ban ?? r.mua_tm;
      if (rate == null) throw new Error("VCB không có tỷ giá USD");
      const fill = <T extends { ccy?: Ccy; fx?: number | null }>(rows: T[]) =>
        rows.map((l) => ((l.ccy ?? "VND") === "USD" ? { ...l, fx: rate } : l));
      setData((d) => ({
        ...d,
        sales: fill((d.sales ?? []) as SaleLine[]),
        stock_signed_undelivered: fill((d.stock_signed_undelivered ?? []) as StockSignedLine[]),
      }));
      message.success(`Đã điền tỷ giá USD/VND (VCB ${r.date}): ${fmtNum(rate, 0)} cho các dòng USD.`);
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
        stock_not_warehoused: (r.stock_not_warehoused ?? []).map((x) => ({ ...x })),
        stock_warehoused: (r.stock_warehoused ?? []).map((x) => ({ ...x })),
        stock_signed_undelivered: (r.stock_signed_undelivered ?? []).map((x) => ({ ...x })),
        stock_material: r.stock_material ?? null,
        stock_ccy: r.stock_ccy ?? d.stock_ccy,
      }));
      message.success(`Đã chép tồn kho ngày ${r.as_of} — kiểm tra và sửa lại trước khi lưu.`);
    } catch (e) { message.error((e as Error).message || "Không lấy được tồn kho ngày trước."); }
    finally { setPrevLoading(false); }
  };

  /** Upload file HĐ cho 1 dòng — dùng chung bảng Tiêu thụ ("sales") và Tồn kho đã ký HĐ ("signed"). */
  const doUpload = async (which: "sales" | "signed", i: number, file: File) => {
    setUploading(`${which}:${i}`);
    try {
      const r = await uploadContractFile(role, file);
      if (which === "sales") setSales(sales.map((l, j) => (j === i ? { ...l, file: r.file, filename: r.filename } : l)));
      else setSigned(signed.map((l, j) => (j === i ? { ...l, file: r.file, filename: r.filename } : l)));
      message.success("Đã tải lên file hợp đồng.");
    } catch (e) { message.error((e as Error).message || "Upload thất bại."); }
    finally { setUploading(null); }
  };

  /** Ô đính kèm file HĐ của 1 dòng (mở lại file đã có + nút đổi/chọn). */
  const fileCell = (which: "sales" | "signed", i: number, r: { file?: string | null; filename?: string | null }) => (
    <>
      {r.file
        ? <a onClick={() => openContractFile(role, r.file!)} style={{ cursor: "pointer", fontSize: 12 }} title={r.filename ?? ""}>{(r.filename ?? "file").slice(0, 14)}</a>
        : <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>}
      {!readOnly && (
        <Upload showUploadList={false} accept=".pdf,image/jpeg,image/png" disabled={uploading === `${which}:${i}`}
          beforeUpload={(fl) => { doUpload(which, i, fl as File); return false; }}>
          <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 6px", marginLeft: 6 }}>
            <UploadOutlined /> {uploading === `${which}:${i}` ? "…" : (r.file ? "Đổi" : "Chọn")}
          </button>
        </Upload>
      )}
    </>
  );

  const head = (t: string, first?: boolean) => (
    <div style={{ fontWeight: 600, fontSize: 12.5, opacity: 0.85, marginTop: first ? 0 : 18, marginBottom: 6, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)" }}>{t}</div>
  );
  const sel = { minWidth: 96, width: "100%" } as const;

  /** Ô chọn loại tiền NGAY TRONG DÒNG + ô tỷ giá đi kèm (chỉ hiện khi dòng đó chọn USD). */
  const rowCcy = (v: Ccy | undefined, on: (c: Ccy) => void) => (
    <Select size="small" style={{ minWidth: 78, width: "100%" }} value={v ?? "VND"} disabled={readOnly}
            onChange={on} options={CCYS} />
  );
  const rowFx = (line: { ccy?: Ccy; fx?: number | null }, on: (v: number | null) => void) =>
    (line.ccy ?? "VND") === "USD"
      ? numInput(num(line.fx), on, readOnly)
      : <span style={{ fontSize: 11.5, color: "var(--muted)" }}>—</span>;

  /** Ô chọn loại tiền cho 1 khối giá (giá bán tiêu thụ · đơn giá tồn kho). */
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
            <th style={{ width: 92 }} className="r">SL (tấn)</th><th style={{ width: 110 }} className="r">Giá bán</th>
            <th style={{ width: 86 }}>Tiền</th><th style={{ width: 104 }} className="r">Tỷ giá</th>
            <th style={{ width: 120 }} className="r">Doanh thu (triệu đ)</th>
            <th style={{ width: 140 }}>Ngày xuất hoá đơn</th><th style={{ width: 170 }}>Bộ Hợp đồng</th>{!readOnly && <th style={{ width: 34 }} />}
          </tr></thead>
          <tbody>
            {sales.map((ln, i) => (
              <tr key={i}>
                <td><Select size="small" style={sel} value={ln.contract} disabled={readOnly} onChange={(v) => setSales(sales.map((l, j) => j === i ? { ...l, contract: v } : l))} options={CONTRACTS} /></td>
                <td><Select size="small" style={sel} value={ln.channel} disabled={readOnly} onChange={(v) => setSales(sales.map((l, j) => j === i ? { ...l, channel: v } : l))} options={CHANNELS} /></td>
                <td>{gradeSel(ln.grade, (v) => setSales(sales.map((l, j) => j === i ? { ...l, grade: v } : l)))}</td>
                <td>{numInput(num(ln.qty), (v) => setSales(sales.map((l, j) => j === i ? { ...l, qty: v } : l)), readOnly)}</td>
                <td>{numInput(num(ln.price), (v) => setSales(sales.map((l, j) => j === i ? { ...l, price: v } : l)), readOnly)}</td>
                <td>{rowCcy(ln.ccy, (v) => setSales(sales.map((l, j) => j === i ? { ...l, ccy: v } : l)))}</td>
                <td>{rowFx(ln, (v) => setSales(sales.map((l, j) => j === i ? { ...l, fx: v } : l)))}</td>
                <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                  {(() => { const rv = lineRevenueVnd(ln); return fmtNum(rv == null ? null : rv / 1_000_000, 1); })()}
                </td>
                <td><input type="date" className="blt-cell-input" style={{ width: "100%" }} value={ln.invoice_date ?? ""} disabled={readOnly}
                  onChange={(e) => setSales(sales.map((l, j) => j === i ? { ...l, invoice_date: e.target.value || null } : l))} /></td>
                <td>{fileCell("sales", i, ln)}</td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} title="Xoá dòng" onClick={() => setSales(sales.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {sales.length === 0 && <tr><td colSpan={readOnly ? 10 : 11} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng tiêu thụ nào.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setSales([...sales, { contract: "long_term", channel: "export", grade: GRADES[0], qty: null, price: null, invoice_date: null, file: null, filename: null }])}><PlusOutlined /> Thêm dòng</button>}

      {!readOnly && (
        <button type="button" className="btn" style={{ marginTop: 10, marginLeft: 8, fontSize: 12 }}
                onClick={fetchFx} disabled={fxLoading}>
          {fxLoading ? "Đang lấy…" : "Lấy tỷ giá VCB cho các dòng USD"}
        </button>
      )}
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 10 }}>
        Mỗi dòng chọn loại tiền riêng — trong ngày vừa bán USD vừa bán VNĐ vẫn nhập chung một phiếu.
        Dòng nào chọn USD thì nhập tỷ giá ngay ở dòng đó{!readOnly && " (nút bên dưới lấy tỷ giá Vietcombank)"}.
      </div>

      {/* Chuyển từ biểu Thu mua sang: tiêu thụ mủ THU MUA và mủ THÀNH PHẨM.
          Mỗi loại có loại tiền + tỷ giá riêng; giá bình quân tự tính = doanh thu ÷ sản lượng. */}
      {head("Tiêu thụ mủ thu mua & mủ thành phẩm")}
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: 180 }}>Loại</th>
            <th style={{ width: 110 }} className="r">SL tiêu thụ (tấn)</th>
            <th style={{ width: 130 }} className="r">Doanh thu</th>
            <th style={{ width: 100 }}>Loại tiền</th>
            <th style={{ width: 130 }} className="r">Tỷ giá (1 USD = ? VND)</th>
            <th style={{ width: 130 }} className="r">Giá BQ (triệu đ/tấn)</th>
          </tr></thead>
          <tbody>
            {SOLD_ROWS.map((r) => {
              const ccy = (data[r.ccyKey] as Ccy) ?? "VND";
              const qty = num(data[r.qtyKey] as number | null);
              const vnd = soldRevenueVnd(r);
              return (
                <tr key={r.qtyKey}>
                  <td style={{ fontWeight: 600 }}>{r.label}</td>
                  <td>{numInput(qty, (v) => setData((d) => ({ ...d, [r.qtyKey]: v })), readOnly)}</td>
                  <td>{numInput(num(data[r.rawKey] as number | null), (v) => setData((d) => ({ ...d, [r.rawKey]: v })), readOnly)}</td>
                  <td>
                    <Select size="small" style={sel} value={ccy} disabled={readOnly}
                            onChange={(v) => setData((d) => ({ ...d, [r.ccyKey]: v }))} options={CCYS} />
                  </td>
                  <td>{ccy === "USD"
                    ? numInput(num(data[r.fxKey] as number | null), (v) => setData((d) => ({ ...d, [r.fxKey]: v })), readOnly)
                    : <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>}</td>
                  <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                    {fmtNum(vnd != null && qty ? vnd / qty / 1_000_000 : null, 2)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 6 }}>
        Doanh thu nhập theo <b>tỷ đồng</b> khi chọn VND, theo <b>USD</b> khi chọn USD (cần tỷ giá để quy đổi).
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

  // ── TỒN KHO: 4 khối theo yêu cầu nghiệp vụ (số THỜI ĐIỂM cuối ngày, đơn vị TẤN) ──
  /** Bảng chỉ có Chủng loại + Số lượng (khối 1 & 2). */
  const qtyTable = (
    rows: StockQtyLine[], setRows: (n: StockQtyLine[]) => void, addLabel: string,
  ) => (
    <>
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: 240 }}>Chủng loại</th>
            <th style={{ width: 130 }} className="r">Số lượng (tấn)</th>{!readOnly && <th style={{ width: 34 }} />}
          </tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td>{gradeSel(r.grade, (v) => setRows(rows.map((x, j) => j === i ? { ...x, grade: v } : x)))}</td>
                <td>{numInput(num(r.qty), (v) => setRows(rows.map((x, j) => j === i ? { ...x, qty: v } : x)), readOnly)}</td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} onClick={() => setRows(rows.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={readOnly ? 2 : 3} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }}
        onClick={() => setRows([...rows, { grade: GRADES[0], qty: null }])}><PlusOutlined /> {addLabel}</button>}
    </>
  );

  const stockTab = (
    <div>
      {/* Tồn kho là số thời điểm, ngày mới thường gần giống ngày trước → cho chép sang rồi sửa. */}
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

      {head("1. Tồn kho thành phẩm chế biến chưa nhập kho", true)}
      {qtyTable(notWh, setNotWh, "Thêm dòng")}

      {head("2. Tồn kho thành phẩm đã nhập kho")}
      {qtyTable(wh, setWh, "Thêm dòng")}

      {head("3. Số lượng đã ký hợp đồng")}
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>
        Đính kèm bản Hợp đồng đã ký scan có đóng dấu cho từng dòng (PDF hoặc ảnh).
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="ud-sales">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: 160 }}>Chủng loại</th><th style={{ width: 110 }} className="r">SL (tấn)</th>
            <th style={{ width: 110 }} className="r">Đơn giá</th>
            <th style={{ width: 86 }}>Tiền</th><th style={{ width: 104 }} className="r">Tỷ giá</th>
            <th style={{ width: 120 }} className="r">Thành tiền (triệu đ)</th><th style={{ width: 140 }}>Lịch giao</th>
            <th style={{ width: 170 }}>HĐ đã ký (scan)</th>{!readOnly && <th style={{ width: 34 }} />}
          </tr></thead>
          <tbody>
            {signed.map((r, i) => (
              <tr key={i}>
                <td>{gradeSel(r.grade, (v) => setSigned(signed.map((x, j) => j === i ? { ...x, grade: v } : x)))}</td>
                <td>{numInput(num(r.qty), (v) => setSigned(signed.map((x, j) => j === i ? { ...x, qty: v } : x)), readOnly)}</td>
                <td>{numInput(num(r.price), (v) => setSigned(signed.map((x, j) => j === i ? { ...x, price: v } : x)), readOnly)}</td>
                <td>{rowCcy(r.ccy, (v) => setSigned(signed.map((x, j) => j === i ? { ...x, ccy: v } : x)))}</td>
                <td>{rowFx(r, (v) => setSigned(signed.map((x, j) => j === i ? { ...x, fx: v } : x)))}</td>
                <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                  {(() => { const vnd = stockLineVnd(r); return fmtNum(vnd == null ? null : vnd / 1_000_000, 1); })()}
                </td>
                <td><input type="date" className="blt-cell-input" style={{ width: "100%" }} value={r.delivery_date ?? ""} disabled={readOnly}
                  onChange={(e) => setSigned(signed.map((x, j) => j === i ? { ...x, delivery_date: e.target.value || null } : x))} /></td>
                <td>{fileCell("signed", i, r)}</td>
                {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} onClick={() => setSigned(signed.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
              </tr>
            ))}
            {signed.length === 0 && <tr><td colSpan={readOnly ? 8 : 9} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng.</td></tr>}
          </tbody>
        </table>
      </div>
      {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }}
        onClick={() => setSigned([...signed, { grade: GRADES[0], qty: null, price: null, delivery_date: null, file: null, filename: null }])}><PlusOutlined /> Thêm dòng</button>}


      {/* Khối 4 — hiện cho MỌI đơn vị; câu "chưa có nhà máy" là ghi chú của biểu mẫu, không phải
          điều kiện ẩn. Đơn vị nào không có số thì để trống. */}
      {head("4. Tồn kho nguyên liệu chưa sản xuất (quy khô)")}
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>
        Đối với các đơn vị chưa có nhà máy chế biến — đơn vị đã có nhà máy để trống ô này.
      </div>
      <label style={{ display: "block", maxWidth: 260 }}>
        {fieldLabel("Số lượng", "tấn")}
        {numInput(num(data.stock_material), (v) => setData((d) => ({ ...d, stock_material: v })), readOnly)}
      </label>

      {head("Tổng hợp tồn kho")}
      <div style={gridStyle}>
        {box("Tồn kho thành phẩm", "tấn", (stockTonnesTotal(notWh) + stockTonnesTotal(wh)) || null)}
        {box("Đã ký hợp đồng", "tấn", stockTonnesTotal(signed) || null)}
        {stockValueVnd > 0 && box("Giá trị đã ký HĐ", "tỷ đồng", toTyDong(stockValueVnd), 3)}
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
