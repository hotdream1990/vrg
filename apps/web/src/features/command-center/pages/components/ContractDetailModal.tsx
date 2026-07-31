import { PlusOutlined } from "@ant-design/icons";
import { Modal } from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  type Contract,
  type ContractDetail,
  type ContractMeta,
  deleteContract,
  fetchContract,
} from "../../../../lib/sales-contract-client";
import ContractFormModal from "./ContractFormModal";

type Props = {
  contractId: number;
  meta: ContractMeta;
  canEdit: boolean;
  onClose: () => void;
  onChanged: () => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const money = (n: number | null) => (n == null ? "—" : (n / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

/** Chi tiết HỢP ĐỒNG MẸ + danh sách PHỤ LỤC (mỗi phụ lục = 1 lần giao). */
export default function ContractDetailModal({ contractId, meta, canEdit, onClose, onChanged }: Props) {
  const [d, setD] = useState<ContractDetail | null>(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<{ initial: Contract | null } | null>(null);

  const load = useCallback(() => {
    fetchContract(contractId).then(setD).catch((e) => setErr(e.message));
  }, [contractId]);
  useEffect(() => { load(); }, [load]);

  const remove = async (id: number, label: string) => {
    if (!confirm(`Xoá ${label}?`)) return;
    try { await deleteContract(id); load(); onChanged(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };

  const c = d?.contract;
  const multi = c?.delivery_type === "multi";
  const customer = meta.customers.find((x) => x.id === c?.customer_id);

  return (
    <>
      <Modal open width={1080} title={c ? `Hợp đồng ${c.code} — ${c.company}` : "Đang tải…"}
        onCancel={onClose} footer={null} destroyOnHidden>
        {err && <div className="blt-error">{err}</div>}
        {c && d && (
          <>
            <div className="kpi-row" style={{ marginBottom: 12 }}>
              <div className="kpi"><div className="label">Khách hàng</div><div className="value">{customer?.name ?? "—"}</div></div>
              <div className="kpi"><div className="label">Loại giao</div><div className="value">{meta.delivery_types[c.delivery_type]}</div></div>
              <div className="kpi"><div className="label">Cam kết (tấn)</div><div className="value">{t3(c.qty)}</div></div>
              <div className="kpi"><div className="label">Đã giao (tấn)</div><div className="value">{t3(d.delivered_qty)}</div></div>
              <div className="kpi"><div className="label">Chưa giao (tấn)</div><div className="value">{t3(d.remaining_qty)}</div></div>
              <div className="kpi"><div className="label">Ngày ký</div><div className="value">{c.sign_date ?? "—"}</div></div>
            </div>

            <h4 style={{ margin: "8px 0 6px" }}>Dòng chi tiết hợp đồng</h4>
            <div className="card" style={{ padding: 0, overflow: "auto" }}>
              <table>
                <thead><tr>
                  <th>Chủng loại</th><th className="r">SL (tấn)</th><th className="r">Quy khô</th>
                  <th className="r">Đơn giá</th><th>Loại tiền</th><th className="r">Chi phí (tr.đ)</th>
                </tr></thead>
                <tbody>
                  {c.lines.map((ln, i) => (
                    <tr key={i}>
                      <td>{ln.grade}</td>
                      <td className="r">{t3(ln.qty ?? 0)}</td>
                      <td className="r">{ln.qty_dry == null ? "—" : t3(ln.qty_dry)}</td>
                      <td className="r">{ln.price == null ? "—" : t3(ln.price)}</td>
                      <td>{ln.ccy}</td>
                      <td className="r">{ln.cost == null ? "—" : t3(ln.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {multi && (
              <>
                <div className="blt-toolbar" style={{ marginTop: 14 }}>
                  <b>Phụ lục ({d.children.length})</b>
                  {canEdit && (
                    <button className="btn btn-primary" onClick={() => setForm({ initial: null })}
                      disabled={d.remaining_qty <= 0}>
                      <PlusOutlined /> Thêm phụ lục
                    </button>
                  )}
                  {d.remaining_qty <= 0 && (
                    <span style={{ color: "var(--muted)", fontSize: 12 }}>Đã giao đủ sản lượng cam kết.</span>
                  )}
                </div>
                <div className="card" style={{ padding: 0, overflow: "auto" }}>
                  <table>
                    <thead><tr>
                      <th>Số phụ lục</th><th>Ngày giao</th><th>Hình thức</th><th>Đơn vị nhận</th>
                      <th className="r">SL (tấn)</th><th className="r">Quy khô</th>
                      <th className="r">Doanh thu (tỷ đ)</th><th className="r">Chi phí (tr.đ)</th>
                      <th>Thanh toán</th>{canEdit && <th className="r" style={{ width: 150 }}>Thao tác</th>}
                    </tr></thead>
                    <tbody>
                      {d.children.map((k) => (
                        <tr key={k.id}>
                          <td style={{ fontWeight: 500 }}>{k.code}</td>
                          <td>{k.delivered_at ?? "—"}</td>
                          <td>{k.channel ? meta.channels[k.channel] : "—"}</td>
                          <td>{k.to_company ?? "—"}</td>
                          <td className="r">{t3(k.qty)}</td>
                          <td className="r">{t3(k.qty_dry)}</td>
                          <td className="r">{money(k.revenue)}</td>
                          <td className="r">{t3(k.cost)}</td>
                          <td>{k.payment_date ?? "—"}</td>
                          {canEdit && (
                            <td className="r" style={{ whiteSpace: "nowrap" }}>
                              <button className="btn" onClick={() => setForm({ initial: k })}>Sửa</button>{" "}
                              <button className="btn" onClick={() => remove(k.id as number, `phụ lục ${k.code}`)}>Xoá</button>
                            </td>
                          )}
                        </tr>
                      ))}
                      {d.children.length === 0 && (
                        <tr><td colSpan={canEdit ? 10 : 9} style={{ textAlign: "center", color: "var(--muted)", padding: 18 }}>
                          Chưa có phụ lục nào — hợp đồng chưa giao lần nào.
                        </td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {!multi && (
              <div className="form-note" style={{ fontSize: 11.5, marginTop: 10 }}>
                Hợp đồng <b>giao 1 lần</b>: {c.delivered
                  ? `đã giao ngày ${c.delivered_at ?? "(chưa ghi ngày)"}.`
                  : "chưa giao — toàn bộ sản lượng đang nằm ở mục “đã ký HĐ chưa giao”."}
              </div>
            )}
          </>
        )}
      </Modal>

      {form && c && (
        <ContractFormModal meta={meta} parent={c} remaining={d?.remaining_qty ?? 0}
          initial={form.initial} onClose={() => setForm(null)}
          onSaved={() => { load(); onChanged(); }} />
      )}
    </>
  );
}
