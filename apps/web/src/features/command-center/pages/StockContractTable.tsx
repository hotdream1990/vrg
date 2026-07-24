/* Khối 3 — TỒN KHO ĐÃ KÝ HỢP ĐỒNG. Khác 3 khối còn lại: KHÔNG nhập lại mỗi ngày.
   Mỗi hợp đồng là 1 bản ghi có vòng đời riêng: nhập một lần kèm HĐ scan, hệ thống tự tính vào tồn
   kho từ NGÀY BẮT ĐẦU đến HẾT NGÀY TRƯỚC NGÀY GIAO. Khi xuất kho chỉ cần điền Ngày giao.
   Lưu/xoá đi thẳng API riêng (không đi kèm nút "Lưu số liệu" của biểu ngày). */

import { DeleteOutlined, PlusOutlined, SaveOutlined, UploadOutlined } from "@ant-design/icons";
import { Input, Select, Upload, message } from "antd";
import { Fragment, useCallback, useEffect, useState } from "react";

import {
  type Role, type StockContract, deleteStockContract, fetchStockContracts, openContractFile,
  saveStockContract, uploadContractFile,
} from "../../../lib/unit-daily-client";
import { CONTRACT_ACCEPT } from "../../../lib/contract-upload";
import { CCYS, GRADES, type Ccy, lineRevenueVnd } from "../../../lib/unit-daily-consumption";
import { fmtNum } from "../../../lib/unit-daily-fields";
import { numInput } from "./unit-daily-inputs";

type Row = StockContract & { _key: number; _dirty?: boolean };

type Props = {
  role: Role;
  company?: string;
  day?: string;                       // ngày báo cáo đang xem
  readOnly?: boolean;
  fallback?: StockContract[];         // khi không có company/day: chỉ hiển thị số server đã tính
  onRows?: (rows: StockContract[]) => void;   // báo lên form để tính Tổng hợp tồn kho
};

const num = (x: number | null | undefined): number | null => (x == null || Number.isNaN(x) ? null : x);
const cell = { width: "100%" } as const;
let seq = 0;
const withKey = (r: StockContract): Row => ({ ...r, _key: ++seq });

export default function StockContractTable({ role, company, day, readOnly, fallback, onRows }: Props) {
  const live = Boolean(company && day && !readOnly);
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);

  const publish = useCallback((next: Row[]) => { setRows(next); onRows?.(next); }, [onRows]);

  const load = useCallback(async () => {
    if (!company || !day) { publish((fallback ?? []).map(withKey)); return; }
    try {
      const r = await fetchStockContracts(role, day, company);
      publish(r.contracts.map(withKey));
    } catch (e) { message.error((e as Error).message || "Không tải được danh sách hợp đồng."); }
  }, [role, company, day]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);

  const patch = (key: number, p: Partial<Row>) =>
    publish(rows.map((r) => (r._key === key ? { ...r, ...p, _dirty: true } : r)));

  const save = async (row: Row) => {
    if (!company) return;
    setBusy(true);
    try {
      const { _key, _dirty, ...body } = row;   // eslint-disable-line @typescript-eslint/no-unused-vars
      const r = await saveStockContract(role, company, body);
      publish(rows.map((x) => (x._key === row._key ? { ...withKey(r.contract), _key: row._key } : x)));
      message.success("Đã lưu hợp đồng.");
    } catch (e) { message.error((e as Error).message || "Lưu hợp đồng thất bại."); }
    finally { setBusy(false); }
  };

  const remove = async (row: Row) => {
    if (row.id) {
      setBusy(true);
      try { await deleteStockContract(role, row.id); }
      catch (e) { message.error((e as Error).message || "Xoá thất bại."); setBusy(false); return; }
      setBusy(false);
    }
    publish(rows.filter((x) => x._key !== row._key));
  };

  const upload = async (row: Row, file: File) => {
    setBusy(true);
    try {
      const r = await uploadContractFile(role, file);
      patch(row._key, { file: r.file, filename: r.filename });
      message.success("Đã tải lên HĐ scan — bấm Lưu để ghi vào hợp đồng.");
    } catch (e) { message.error((e as Error).message || "Upload thất bại."); }
    finally { setBusy(false); }
  };

  /** 1 mốc ngày ở HÀNG DƯỚI — có nhãn riêng nên không phải nhồi thêm cột vào hàng trên. */
  const dateChip = (label: string, v: string | null | undefined, on: (v: string | null) => void) => (
    <label className="ud-doc">
      <span className="ud-doc-lb">{label}</span>
      <input type="date" className="blt-cell-input" style={{ width: 150 }} value={v ?? ""}
        disabled={readOnly} onChange={(e) => on(e.target.value || null)} />
    </label>
  );

  const cols = readOnly ? 7 : 8;
  return (
    <>
      <div style={{ overflowX: "auto" }}>
        {/* Mỗi hợp đồng trải 2 HÀNG (số liệu nhiều): hàng trên số lượng/giá, hàng dưới các mốc
            ngày + HĐ scan — cùng khuôn với bảng tiêu thụ để đọc cho quen mắt. */}
        <table className="ud-sales ud-sale2 ud-contract">
          <thead><tr style={{ fontSize: 11.5, textAlign: "left", opacity: 0.7 }}>
            <th style={{ width: "20%" }}>Chủng loại</th><th style={{ width: "17%" }}>Số HĐ/PL</th>
            <th style={{ width: "11%" }} className="r">SL (tấn)</th>
            <th style={{ width: "12%" }} className="r">Đơn giá</th>
            <th style={{ width: "10%" }}>Tiền</th><th style={{ width: "11%" }} className="r">Tỷ giá</th>
            <th style={{ width: "13%" }} className="r">Thành tiền (triệu đ)</th>
            {!readOnly && <th style={{ width: "10%" }} />}
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <Fragment key={r._key}>
                <tr>
                  <td>
                    <Select size="small" style={cell} value={r.grade || undefined} placeholder="Chủng loại"
                      disabled={readOnly} showSearch onChange={(v) => patch(r._key, { grade: v })}
                      options={GRADES.map((g) => ({ value: g, label: g }))} />
                  </td>
                  <td>
                    <Input size="small" style={cell} value={r.code ?? ""} placeholder="Số HĐ/PL"
                      disabled={readOnly} onChange={(e) => patch(r._key, { code: e.target.value || null })} />
                  </td>
                  <td>{numInput(num(r.qty), (v) => patch(r._key, { qty: v }), readOnly, "small")}</td>
                  <td>{numInput(num(r.price), (v) => patch(r._key, { price: v }), readOnly, "small")}</td>
                  <td>
                    <Select size="small" style={cell} value={r.ccy ?? "VND"} disabled={readOnly}
                      onChange={(v: Ccy) => patch(r._key, { ccy: v })} options={CCYS} />
                  </td>
                  <td>
                    {(r.ccy ?? "VND") === "USD"
                      ? numInput(num(r.fx), (v) => patch(r._key, { fx: v }), readOnly, "small")
                      : <span style={{ fontSize: 11.5, color: "var(--muted)" }}>—</span>}
                  </td>
                  <td className="r" style={{ paddingRight: 6, fontWeight: 600, whiteSpace: "nowrap" }}>
                    {(() => { const v = lineRevenueVnd(r); return fmtNum(v == null ? null : v / 1_000_000, 1); })()}
                  </td>
                  {!readOnly && (
                    <td className="r" style={{ whiteSpace: "nowrap" }}>
                      <button type="button" className="btn" style={{ padding: "0 7px" }} title="Lưu hợp đồng"
                        disabled={busy || !r._dirty} onClick={() => save(r)}><SaveOutlined /></button>
                      <button type="button" className="btn" style={{ padding: "0 7px", marginLeft: 4 }}
                        title="Xoá hợp đồng" disabled={busy} onClick={() => remove(r)}><DeleteOutlined /></button>
                    </td>
                  )}
                </tr>
                {/* Hàng 2 — các mốc ngày của CHÍNH hợp đồng bên trên + bản HĐ đã ký. */}
                <tr className="ud-docs-row">
                  <td colSpan={cols}>
                    <div className="ud-docs">
                      {dateChip("Bắt đầu tồn kho", r.start_date, (v) => patch(r._key, { start_date: v ?? "" }))}
                      {dateChip("Lịch giao", r.delivery_date, (v) => patch(r._key, { delivery_date: v }))}
                      {dateChip("Ngày giao", r.delivered_date, (v) => patch(r._key, { delivered_date: v }))}
                      <div className="ud-doc">
                        <span className="ud-doc-lb">HĐ đã ký (scan)</span>
                        <span>
                          {r.file
                            ? <a onClick={() => openContractFile(role, r.file!)} style={{ cursor: "pointer", fontSize: 12 }}
                                title={r.filename ?? ""}>{(r.filename ?? "file").slice(0, 18)}</a>
                            : <span style={{ fontSize: 12, color: "var(--muted)" }}>—</span>}
                          {!readOnly && (
                            <Upload showUploadList={false} accept={CONTRACT_ACCEPT} disabled={busy}
                              beforeUpload={(fl) => { upload(r, fl as File); return false; }}>
                              <button type="button" className="btn" style={{ fontSize: 10.5, padding: "0 6px", marginLeft: 6 }}>
                                <UploadOutlined /> {r.file ? "Đổi" : "Chọn"}
                              </button>
                            </Upload>
                          )}
                        </span>
                      </div>
                      {r.delivered_date && (
                        <span style={{ fontSize: 11.5, color: "var(--muted)" }}>
                          Đã giao — tính tồn kho đến hết ngày {new Date(
                            new Date(r.delivered_date).getTime() - 86_400_000).toLocaleDateString("vi-VN")}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              </Fragment>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={cols} style={{ textAlign: "center", color: "var(--muted)", padding: 12, fontSize: 12.5 }}>
                Chưa có hợp đồng nào còn tồn kho tại ngày này.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
      {live && (
        <button type="button" className="btn" style={{ marginTop: 8, fontSize: 12 }} disabled={busy}
          onClick={() => publish([...rows, withKey({
            grade: GRADES[0], code: null, qty: null, price: null, ccy: "VND", fx: null,
            start_date: day as string, delivery_date: null, delivered_date: null,
            file: null, filename: null,
          })])}><PlusOutlined /> Thêm hợp đồng</button>
      )}
    </>
  );
}
