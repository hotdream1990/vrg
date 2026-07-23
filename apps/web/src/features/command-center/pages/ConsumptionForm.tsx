/* Form nhập biểu TIÊU THỤ – TỒN KHO.
   - TIÊU THỤ = 2 bảng nhiều dòng nhập TÁCH RIÊNG (mủ THU MUA `sales` · mủ KHAI THÁC `sales_own`)
     để lưu trữ riêng, còn phần Tổng hợp thì CỘNG CHUNG cả hai. Mỗi bản ghi trải 2 hàng: hàng trên
     là số liệu bán (mã HĐ/PL · loại HĐ · hình thức · loại mủ · SL · giá bán → doanh thu tự tính),
     hàng dưới là chứng từ (ngày xuất kho · ngày xuất hoá đơn · bộ HĐ · phiếu xuất kho · hoá đơn).
   - TỒN KHO (số THỜI ĐIỂM cuối ngày, đơn vị TẤN — mẫu tuần mục 11–14): chưa HĐ = bảng (chủng loại ·
     SL tấn); đã HĐ = bảng (chủng loại · mã HĐ/PL · tấn · đơn giá · lịch giao · file HĐ); mục 14 =
     tồn kho nguyên liệu chưa có HĐ (tấn), nhập chung cho mọi đơn vị.
   - Giá bán (tiêu thụ) và đơn giá (tồn kho đã HĐ) cho CHỌN VND hay USD; chọn USD thì nhập tỷ giá
     USD→VND (nút lấy VCB) — tỷ giá dùng chung cho cả 2 khối. Tiền lưu BASE = đồng.
   - Tồn kho KHÔNG cộng dồn giữa các ngày; có nút "Lấy tồn ngày trước" để chép sang rồi sửa. */

import { DeleteOutlined, PlusOutlined, UploadOutlined } from "@ant-design/icons";
import { Input, Select, Tabs, Upload, message } from "antd";
import { Fragment, useEffect, useMemo, useState } from "react";

import { fetchVcbRate } from "../../../lib/market-quote-client";
import {
  type PriceDraft, type Role, type StockContract, fetchPrevStock, openContractFile,
  uploadContractFile,
} from "../../../lib/unit-daily-client";
import {
  CCYS, CHANNELS, CONTRACTS, GRADES, SALE_DATES, SALE_DOCS, type Ccy, type ConsumptionData,
  type SaleLine, type StockQtyLine, emptySaleLine, lineRevenueVnd,
  stockTonnesTotal, toTyDong, totals,
} from "../../../lib/unit-daily-consumption";
import { type Values, fmtNum } from "../../../lib/unit-daily-fields";
import StockContractTable from "./StockContractTable";
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
    sales_own: Array.isArray(v.sales_own) ? v.sales_own.map((l) => ({ ...l })) : [],
    sales_ccy: v.sales_ccy ?? dc,
    stock_ccy: v.stock_ccy ?? dc,
    fx_revenue: v.fx_revenue ?? null,
    stock_not_warehoused: Array.isArray(v.stock_not_warehoused) ? v.stock_not_warehoused.map((r) => ({ ...r })) : [],
    stock_warehoused: Array.isArray(v.stock_warehoused) ? v.stock_warehoused.map((r) => ({ ...r })) : [],
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

  const sales = (data.sales ?? []) as SaleLine[];                         // tiêu thụ mủ THU MUA
  const salesOwn = (data.sales_own ?? []) as SaleLine[];                  // tiêu thụ mủ KHAI THÁC
  const notWh = (data.stock_not_warehoused ?? []) as StockQtyLine[];      // 1 chế biến chưa nhập kho
  const wh = (data.stock_warehoused ?? []) as StockQtyLine[];             // 2 đã nhập kho
  // 3 đã ký HĐ chưa giao — KHÔNG nằm trong payload ngày nữa (bản ghi có vòng đời riêng, lưu qua
  // API hợp đồng). Bảng con báo số lên đây để tính phần Tổng hợp tồn kho.
  const [signed, setSignedRows] = useState<StockContract[]>([]);
  const live = Boolean(company && day && !readOnly);

  const setSales = (next: SaleLine[]) => setData((d) => ({ ...d, sales: next }));
  const setSalesOwn = (next: SaleLine[]) => setData((d) => ({ ...d, sales_own: next }));
  const setNotWh = (next: StockQtyLine[]) => setData((d) => ({ ...d, stock_not_warehoused: next }));
  const setWh = (next: StockQtyLine[]) => setData((d) => ({ ...d, stock_warehoused: next }));

  // Nhập tách riêng 2 bảng nhưng phần Tổng hợp (SL · doanh thu · giá BQ) là số GỘP CHUNG.
  const agg = totals([...sales, ...salesOwn]);

  /** Giá trị hợp đồng đã ký, quy về đồng (USD cần tỷ giá; thiếu tỷ giá → không cộng, không đoán). */
  const stockValueVnd = signed.reduce((a, r) => a + (lineRevenueVnd(r) ?? 0), 0);

  const current = useMemo<Values>(() => {
    const p: ConsumptionData = {
      sales, sales_own: salesOwn, revenue: agg.revenueVnd, sales_ccy: salesCcy, stock_ccy: stockCcy,
      stock_not_warehoused: notWh, stock_warehoused: wh,
    };
    if (needFx) p.fx_revenue = data.fx_revenue ?? null;
    p.stock_material = data.stock_material ?? null;   // khối 4 — mọi đơn vị đều nhập được
    return p as unknown as Values;
  }, [sales, salesOwn, agg.revenueVnd, notWh, wh, salesCcy, stockCcy, needFx, data]);

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
        sales_own: fill((d.sales_own ?? []) as SaleLine[]),
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
        stock_material: r.stock_material ?? null,
        stock_ccy: r.stock_ccy ?? d.stock_ccy,
      }));
      message.success(`Đã chép tồn kho ngày ${r.as_of} — kiểm tra và sửa lại trước khi lưu.`);
    } catch (e) { message.error((e as Error).message || "Không lấy được tồn kho ngày trước."); }
    finally { setPrevLoading(false); }
  };

  /** Ô đính kèm 1 chứng từ (mở lại file đã có + nút đổi/chọn). Dùng chung cho mọi bảng/mọi loại
      chứng từ: `slot` là id duy nhất để biết ô nào đang tải, `set` gán cặp (file, tên gốc) vào dòng. */
  const fileCell = (
    slot: string,
    cur: { file?: string | null; filename?: string | null },
    set: (v: { file: string; filename: string }) => void,
  ) => {
    const busy = uploading === slot;
    const upload = async (file: File) => {
      setUploading(slot);
      try {
        const r = await uploadContractFile(role, file);
        set({ file: r.file, filename: r.filename });
        message.success("Đã tải lên chứng từ.");
      } catch (e) { message.error((e as Error).message || "Upload thất bại."); }
      finally { setUploading(null); }
    };
    return (
      <>
        {cur.file
          ? <a onClick={() => openContractFile(role, cur.file!)} style={{ cursor: "pointer", fontSize: 12 }} title={cur.filename ?? ""}>{(cur.filename ?? "file").slice(0, 14)}</a>
          : <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>}
        {!readOnly && (
          <Upload showUploadList={false} accept=".pdf,image/jpeg,image/png" disabled={busy}
            beforeUpload={(fl) => { upload(fl as File); return false; }}>
            <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 6px", marginLeft: 6 }}>
              <UploadOutlined /> {busy ? "…" : (cur.file ? "Đổi" : "Chọn")}
            </button>
          </Upload>
        )}
      </>
    );
  };

  const head = (t: string, first?: boolean) => (
    <div style={{ fontWeight: 600, fontSize: 12.5, opacity: 0.85, marginTop: first ? 0 : 18, marginBottom: 6, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)" }}>{t}</div>
  );
  // Ô trong bảng để width 100% cho khớp bề rộng cột (cột đã khai báo ở <th>, bảng chạy
  // table-layout: fixed). KHÔNG đặt minWidth — minWidth ép cột phình ra, làm các cột số bị bóp lại.
  const sel = { width: "100%" } as const;

  /** Ô nhập số NẰM TRONG BẢNG — luôn size "small" để cao bằng Select/nút cùng dòng (24px). */
  const cellNum = (v: number | null, on: (v: number | null) => void) => numInput(v, on, readOnly, "small");

  /** Ô nhập CHỮ trong bảng (mã HĐ/PL) — cùng size "small" cho thẳng hàng với các ô khác. */
  const cellText = (v: string | null | undefined, on: (v: string | null) => void, ph: string) => (
    <Input size="small" style={sel} value={v ?? ""} placeholder={ph} disabled={readOnly}
      onChange={(e) => on(e.target.value || null)} />
  );

  /** Ô chọn loại tiền NGAY TRONG DÒNG + ô tỷ giá đi kèm (chỉ hiện khi dòng đó chọn USD). */
  const rowCcy = (v: Ccy | undefined, on: (c: Ccy) => void) => (
    <Select size="small" style={sel} value={v ?? "VND"} disabled={readOnly} onChange={on} options={CCYS} />
  );
  const rowFx = (line: { ccy?: Ccy; fx?: number | null }, on: (v: number | null) => void) =>
    (line.ccy ?? "VND") === "USD"
      ? cellNum(num(line.fx), on)
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

  /** Bảng tiêu thụ — dùng chung cho mủ THU MUA (`sales`) và mủ KHAI THÁC (`sales_own`).
      Mỗi bản ghi trải 2 HÀNG vì số liệu nhiều: hàng 1 = số bán, hàng 2 = chứng từ (2 ngày + 3 file). */
  const salesTable = (id: "sales" | "sales_own", rows: SaleLine[], setRows: (n: SaleLine[]) => void) => {
    const patch = (i: number, p: Partial<SaleLine>) => setRows(rows.map((l, j) => (j === i ? { ...l, ...p } : l)));
    const cols = readOnly ? 9 : 10;
    return (
      <>
        <div style={{ overflowX: "auto" }}>
          <table className="ud-sales ud-sale2">
            {/* Bề rộng cột theo % (bảng chạy table-layout: fixed) — vừa khít mọi khổ màn hình,
                hẹp hơn `min-width` của bảng thì cuộn ngang chứ không bóp méo ô.
                % chọn sao cho ở đúng ngưỡng min-width nhãn dài nhất của từng cột vẫn đủ chỗ
                ("SVR 10 / CSR 20" 96px · "XK / UTXK" 62px — cộng ~44px khung chọn + lề ô). */}
            <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
              <th style={{ width: "13%" }}>Mã HĐ/PL</th>
              <th style={{ width: "10%" }}>Loại HĐ</th><th style={{ width: "11.5%" }}>Hình thức</th><th style={{ width: "14.5%" }}>Loại mủ</th>
              <th style={{ width: "8.5%" }} className="r">SL (tấn)</th><th style={{ width: "9.5%" }} className="r">Giá bán</th>
              <th style={{ width: "7.5%" }}>Tiền</th><th style={{ width: "8.5%" }} className="r">Tỷ giá</th>
              <th style={{ width: "11%" }} className="r">Doanh thu (triệu đ)</th>{!readOnly && <th style={{ width: "6%" }} />}
            </tr></thead>
            <tbody>
              {rows.map((ln, i) => (
                <Fragment key={i}>
                  <tr>
                    <td>{cellText(ln.code, (v) => patch(i, { code: v }), "Số HĐ/PL")}</td>
                    <td><Select size="small" style={sel} value={ln.contract} disabled={readOnly} onChange={(v) => patch(i, { contract: v })} options={CONTRACTS} /></td>
                    <td><Select size="small" style={sel} value={ln.channel} disabled={readOnly} onChange={(v) => patch(i, { channel: v })} options={CHANNELS} /></td>
                    <td>{gradeSel(ln.grade, (v) => patch(i, { grade: v }))}</td>
                    <td>{cellNum(num(ln.qty), (v) => patch(i, { qty: v }))}</td>
                    <td>{cellNum(num(ln.price), (v) => patch(i, { price: v }))}</td>
                    <td>{rowCcy(ln.ccy, (v) => patch(i, { ccy: v }))}</td>
                    <td>{rowFx(ln, (v) => patch(i, { fx: v }))}</td>
                    <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                      {(() => { const rv = lineRevenueVnd(ln); return fmtNum(rv == null ? null : rv / 1_000_000, 1); })()}
                    </td>
                    {!readOnly && <td className="r"><button type="button" className="btn" style={{ padding: "0 7px" }} title="Xoá dòng" onClick={() => setRows(rows.filter((_, j) => j !== i))}><DeleteOutlined /></button></td>}
                  </tr>
                  {/* Hàng 2 — chứng từ của CHÍNH dòng bên trên. */}
                  <tr className="ud-docs-row">
                    <td colSpan={cols}>
                      <div className="ud-docs">
                        {SALE_DATES.map((d) => (
                          <label key={d.key} className="ud-doc">
                            <span className="ud-doc-lb">{d.label}</span>
                            <input type="date" className="blt-cell-input" style={{ width: 150 }} disabled={readOnly}
                              value={(ln[d.key] as string | null) ?? ""}
                              onChange={(e) => patch(i, { [d.key]: e.target.value || null } as Partial<SaleLine>)} />
                          </label>
                        ))}
                        {SALE_DOCS.map((dc) => (
                          <div key={dc.fileKey} className="ud-doc">
                            <span className="ud-doc-lb">{dc.label}</span>
                            <span>{fileCell(
                              `${id}:${i}:${dc.fileKey}`,
                              { file: ln[dc.fileKey] as string | null, filename: ln[dc.nameKey] as string | null },
                              (v) => patch(i, { [dc.fileKey]: v.file, [dc.nameKey]: v.filename } as Partial<SaleLine>),
                            )}</span>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                </Fragment>
              ))}
              {rows.length === 0 && <tr><td colSpan={cols} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>Chưa có dòng tiêu thụ nào.</td></tr>}
            </tbody>
          </table>
        </div>
        {!readOnly && <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} onClick={() => setRows([...rows, emptySaleLine()])}><PlusOutlined /> Thêm dòng</button>}
      </>
    );
  };

  const salesTab = (
    <div>
      {head("Tiêu thụ mủ khai thác", true)}
      {salesTable("sales_own", salesOwn, setSalesOwn)}

      {/* Nhập TÁCH RIÊNG với mủ khai thác để lưu trữ riêng — Tổng hợp bên dưới vẫn cộng chung. */}
      {head("Tiêu thụ mủ thu mua")}
      {salesTable("sales", sales, setSales)}

      {!readOnly && (
        <div style={{ marginTop: 12 }}>
          <button type="button" className="btn" style={{ fontSize: 12 }} onClick={fetchFx} disabled={fxLoading}>
            {fxLoading ? "Đang lấy…" : "Lấy tỷ giá VCB cho các dòng USD"}
          </button>
        </div>
      )}
      <div className="form-note" style={{ fontSize: 11.5, marginTop: 10 }}>
        Mã HĐ/PL là số hợp đồng / phụ lục ghi trên chứng từ của dòng bán đó.
        Mủ thu mua và mủ khai thác nhập ở 2 bảng riêng để lưu trữ tách bạch — phần Tổng hợp bên dưới
        cộng chung cả hai. Mỗi dòng chọn loại tiền riêng: trong ngày vừa bán USD vừa bán VNĐ vẫn nhập
        chung một phiếu; dòng nào chọn USD thì nhập tỷ giá ngay ở dòng đó
        {!readOnly && " (nút trên điền tỷ giá Vietcombank cho mọi dòng USD của cả 2 bảng)"}.
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
        {/* Bảng chỉ 2 cột — chặn bề rộng để ô không bị kéo dài lê thê trên màn rộng. */}
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
          <span className="form-note" style={{ fontSize: 11.5 }}>
            Tồn kho là số tại thời điểm cuối ngày — chép sang rồi sửa cho đúng ngày này.
          </span>
        </div>
      )}

      {head("1. Tồn kho thành phẩm chế biến chưa nhập kho", true)}
      {qtyTable(notWh, setNotWh, "Thêm dòng")}

      {head("2. Tồn kho thành phẩm đã nhập kho")}
      {qtyTable(wh, setWh, "Thêm dòng")}

      {head("3. Số lượng đã ký hợp đồng chưa giao")}
      <div className="form-note" style={{ fontSize: 11.5, marginBottom: 6 }}>
        Đây là số <b>ghi nhận riêng</b> — <b>KHÔNG cộng vào và không trừ khỏi</b> tồn kho thành phẩm.
        Khối này <b>KHÔNG nhập lại mỗi ngày</b>: mỗi hợp đồng nhập <b>một lần</b> kèm bản HĐ đã ký
        scan có đóng dấu (PDF hoặc ảnh), hệ thống tự giữ hợp đồng ở khối này từ{" "}
        <b>ngày bắt đầu tồn kho</b> đến <b>hết ngày trước Ngày giao</b>.
        Khi đã xuất kho thì chỉ cần điền <b>Ngày giao</b>.
        Ngày bắt đầu phải <b>trước Ngày giao (và Lịch giao) ít nhất 1 ngày</b>.
        {live && " Mỗi dòng lưu riêng bằng nút lưu ở cuối dòng, không đi kèm nút Lưu số liệu bên dưới."}
      </div>
      <StockContractTable role={role} company={company} day={day} readOnly={readOnly}
        fallback={(values as unknown as ConsumptionData).stock_signed_undelivered as StockContract[] | undefined}
        onRows={setSignedRows} />


      {/* Khối 4 — nhập chung cho MỌI đơn vị; đơn vị nào không có số thì để trống. */}
      {head("4. Tồn kho nguyên liệu chưa sản xuất (quy khô)")}
      <label style={{ display: "block", maxWidth: 260 }}>
        {fieldLabel("Số lượng", "tấn")}
        {numInput(num(data.stock_material), (v) => setData((d) => ({ ...d, stock_material: v })), readOnly)}
      </label>

      {head("Tổng hợp tồn kho")}
      <div style={gridStyle}>
        {box("Tồn kho thành phẩm", "tấn", (stockTonnesTotal(notWh) + stockTonnesTotal(wh)) || null)}
        {box("Đã ký HĐ chưa giao", "tấn", stockTonnesTotal(signed) || null)}
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
