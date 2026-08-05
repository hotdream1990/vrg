import { PaperClipOutlined } from "@ant-design/icons";

import type { Contract, ContractDoc, ContractMeta } from "../../../../lib/sales-contract-client";
import { openContractFile } from "../../../../lib/sales-contract-client";
import { dmy } from "../../../../lib/date";

type Props = {
  rows: Contract[];
  meta: ContractMeta;
  canEdit: boolean;
  /** Đợt đã giao quá cửa sổ sửa → chỉ xem (server cũng chặn). */
  locked: (deliveredAt: string | null) => boolean;
  onEdit: (batch: Contract) => void;
  onDelete: (batch: Contract) => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
/** Thành tiền quy VNĐ, hiện theo TRIỆU ĐỒNG. null = có dòng ngoại tệ thiếu tỷ giá → "—". */
const money = (n: number | null) =>
  (n == null ? "—" : (n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

/** Danh sách file đính kèm — mở bằng fetch kèm token (endpoint đòi Bearer). */
export function Docs({ docs }: { docs: ContractDoc[] }) {
  if (!docs.length) return <span style={{ color: "var(--muted)" }}>—</span>;
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {docs.map((d) => (
        <a key={d.file} href="#" title={d.filename ?? d.file} style={{ fontSize: 12 }}
          onClick={(e) => { e.preventDefault(); openContractFile(d).catch(() => undefined); }}>
          <PaperClipOutlined /> {(d.filename ?? d.file).slice(0, 22)}
        </a>
      ))}
    </div>
  );
}

/** Số chứng từ + file scan của nó trong một ô (hoá đơn). */
function DocCell({ no, docs }: { no: string | null; docs: ContractDoc[] }) {
  if (!no && !docs.length) return <span style={{ color: "var(--muted)" }}>—</span>;
  return (
    <div style={{ fontSize: 12.5 }}>
      {no && <div style={{ fontWeight: 500 }}>{no}</div>}
      {docs.length > 0 && <Docs docs={docs} />}
    </div>
  );
}

/** Bảng ĐỢT GIAO của một hợp đồng — mỗi dòng là một lần giao (hoá đơn · ngày giao · chi tiết
 *  hàng). Đợt chưa điền ngày giao là đang chờ giao, chưa tính vào tiêu thụ. */
export default function ContractBatchTable({ rows, meta, canEdit, locked, onEdit, onDelete }: Props) {
  return (
    <div className="card" style={{ padding: 0, overflow: "auto" }}>
      <table>
        <thead><tr>
          <th>Số đợt</th><th>Ngày giao</th><th>Hoá đơn</th>
          <th>Hình thức</th><th>Đơn vị nhận</th>
          <th className="r">SL (tấn)</th><th className="r">Quy khô</th>
          <th className="r">Thành tiền (tr.đ)</th>
          <th>Thanh toán</th><th>Đính kèm khác</th>
          {canEdit && <th className="r" style={{ width: 150 }}>Thao tác</th>}
        </tr></thead>
        <tbody>
          {rows.map((k) => (
            <tr key={k.id}>
              <td style={{ fontWeight: 500 }}>{k.code}</td>
              <td>
                {k.delivered_at ? dmy(k.delivered_at) : <span className="chip warn">Đang chờ giao</span>}
              </td>
              <td><DocCell no={k.invoice_no} docs={k.invoice_docs} /></td>
              <td>{k.channel ? meta.channels[k.channel] : "—"}</td>
              <td>{k.to_company ?? "—"}</td>
              <td className="r">{t3(k.qty)}</td>
              {/* Chủng loại thành phẩm không có quy khô → để "—". Hiện số 0 làm người đọc tưởng
                  đợt này khai thiếu quy khô. */}
              <td className="r">{k.qty_dry > 0 ? t3(k.qty_dry) : "—"}</td>
              <td className="r">{money(k.revenue)}</td>
              <td style={{ whiteSpace: "nowrap", fontSize: 12.5 }}>
                {dmy(k.payment_date) || "—"}
                {k.payment_qty != null && (
                  <div style={{ color: "var(--muted)" }}>{t3(k.payment_qty)} tấn</div>
                )}
                <Docs docs={k.payment_docs} />
              </td>
              <td><Docs docs={k.files} /></td>
              {canEdit && (
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  {/* Lần giao quá cửa sổ sửa → chỉ xem. Server cũng chặn (403), nhưng báo trước ở
                      đây để người dùng khỏi điền xong mới biết không lưu được. */}
                  {locked(k.delivered_at) ? (
                    <span style={{ color: "var(--muted)", fontSize: 11 }}>(chỉ xem)</span>
                  ) : (
                    <>
                      <button className="btn" onClick={() => onEdit(k)}>Sửa</button>{" "}
                      <button className="btn" onClick={() => onDelete(k)}>Xoá</button>
                    </>
                  )}
                </td>
              )}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr><td colSpan={canEdit ? 11 : 10} style={{ textAlign: "center", color: "var(--muted)", padding: 18 }}>
              Chưa có đợt giao nào — hợp đồng chưa giao lần nào.
            </td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
