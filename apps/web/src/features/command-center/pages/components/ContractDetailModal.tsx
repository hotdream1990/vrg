import { EditOutlined, PaperClipOutlined, PlusOutlined } from "@ant-design/icons";
import { Modal, Tabs } from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  type Contract,
  type ContractDetail,
  type ContractDoc,
  type ContractMeta,
  deleteContract,
  fetchContract,
  openContractFile,
} from "../../../../lib/sales-contract-client";
import { dmy } from "../../../../lib/date";
import { useEditWindow } from "../../../../lib/edit-window";
import ContractFormModal from "./ContractFormModal";
import { lineAmount } from "./ContractLinesTable";

type Props = {
  contractId: number;
  meta: ContractMeta;
  canEdit: boolean;
  onClose: () => void;
  onChanged: () => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Danh sách file đính kèm — mở bằng fetch kèm token (endpoint đòi Bearer). */
function Docs({ docs }: { docs: ContractDoc[] }) {
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
/** Thành tiền quy VNĐ, hiện theo TRIỆU ĐỒNG — thống nhất với ô "Thành tiền" ở form nhập.
 *  null = có dòng ngoại tệ thiếu tỷ giá → "—", KHÔNG hiển thị 0. */
const money = (n: number | null) => (n == null ? "—" : (n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

/** Chi tiết HỢP ĐỒNG MẸ + danh sách PHỤ LỤC (mỗi phụ lục = 1 lần giao). */
export default function ContractDetailModal({ contractId, meta, canEdit, onClose, onChanged }: Props) {
  const [d, setD] = useState<ContractDetail | null>(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<{ initial: Contract | null } | null>(null);
  const [editSelf, setEditSelf] = useState(false);

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
  // Cửa sổ sửa CHỈ áp cho lần giao, mốc là ngày giao — hợp đồng mẹ sửa được suốt vòng đời.
  const { isEditable } = useEditWindow();
  const locked = (deliveredAt: string | null) => !!deliveredAt && !isEditable(deliveredAt);
  // Tên khách do server trả kèm chi tiết (danh mục khách không còn nằm trong /meta).

  return (
    <>
      <Modal open width="min(1280px, 94vw)" title={c ? `Hợp đồng ${c.code} — ${c.company}` : "Đang tải…"}
        onCancel={onClose} footer={null} destroyOnHidden>
        {err && <div className="blt-error">{err}</div>}
        {c && d && (
          <>
            {/* Hàng số liệu để NGOÀI tab: đây là thứ người dùng mở hợp đồng ra để xem đầu tiên,
                cần thấy ngay cả khi đang ở tab phụ lục. */}
            <div className="kpi-row ct-kpi">
              <div className="kpi"><div className="label">Khách hàng</div><div className="value">{d.customer_name ?? "—"}</div></div>
              <div className="kpi"><div className="label">Loại hợp đồng</div>
                <div className="value">{meta.contract_types[c.contract_type ?? ""] ?? "(chưa khai)"}</div></div>
              {/* Nhãn đầy đủ "Giao nhiều lần (hợp đồng mẹ – phụ lục)" vắt 3 dòng làm cao vống cả
                  hàng thẻ. Ô này hiện bản ngắn, chữ đầy đủ để ở tooltip — giống bảng danh sách. */}
              <div className="kpi"><div className="label">Loại giao</div>
                <div className="value" title={meta.delivery_types[c.delivery_type]}>
                  {multi ? "Giao nhiều lần" : "Giao 1 lần"}
                </div></div>
              <div className="kpi"><div className="label">Cam kết (tấn)</div><div className="value">{t3(c.qty)}</div></div>
              <div className="kpi"><div className="label">Thành tiền (tr.đ)</div><div className="value">{money(c.revenue)}</div></div>
              <div className="kpi"><div className="label">Đã giao (tấn)</div><div className="value">{t3(d.delivered_qty)}</div></div>
              <div className="kpi"><div className="label">Đang chờ giao (tấn)</div><div className="value">{t3(d.pending_qty)}</div></div>
              <div className="kpi"><div className="label">Chưa mở đợt (tấn)</div><div className="value">{t3(d.remaining_qty)}</div></div>
              <div className="kpi"><div className="label">Ngày ký</div><div className="value">{dmy(c.sign_date) || "—"}</div></div>
              <div className="kpi"><div className="label">Thời hạn</div><div className="value">{dmy(c.expiry_date) || "—"}</div></div>
            </div>

            {/* Chia tab để bớt cuộn: hợp đồng nhiều phụ lục trước đây phải cuộn rất sâu mới tới
                bảng phụ lục — phần người dùng thao tác nhiều nhất. */}
            <Tabs
              defaultActiveKey={multi ? "annex" : "info"}
              items={[
                {
                  key: "info",
                  label: "Thông tin hợp đồng",
                  children: (
                    <>
                      {canEdit && (
                        <div className="blt-toolbar" style={{ marginBottom: 10 }}>
                          {/* HĐ giao-1-lần ĐÃ GIAO chính là một lần giao → cũng nằm trong cửa sổ sửa. */}
                          {locked(c.delivered_at) ? (
                            <span style={{ color: "var(--muted)", fontSize: 12 }}>
                              Đã giao quá hạn sửa — hợp đồng này chỉ còn xem.
                            </span>
                          ) : (
                            <button className="btn" onClick={() => setEditSelf(true)}>
                              <EditOutlined /> Sửa thông tin hợp đồng
                            </button>
                          )}
                        </div>
                      )}

                      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 12, fontSize: 13 }}>
                        <div>
                          <div style={{ color: "var(--muted)", fontSize: 12 }}>Hợp đồng đã ký (scan)</div>
                          <Docs docs={c.files} />
                        </div>
                        {c.note && (
                          <div style={{ flex: 1, minWidth: 240 }}>
                            <div style={{ color: "var(--muted)", fontSize: 12 }}>Ghi chú</div>
                            {c.note}
                          </div>
                        )}
                      </div>

                      <h4 style={{ margin: "8px 0 6px" }}>Dòng chi tiết hợp đồng</h4>
                      <div className="card" style={{ padding: 0, overflow: "auto" }}>
                        <table>
                          <thead><tr>
                            <th>Chủng loại</th><th className="r">SL nước (tấn)</th><th className="r">Quy khô</th>
                            <th className="r">Đơn giá</th><th>Loại tiền</th><th className="r">Thành tiền</th>
                          </tr></thead>
                          <tbody>
                            {c.lines.map((ln, i) => (
                              <tr key={i}>
                                <td>{ln.grade}</td>
                                <td className="r">{t3(ln.qty ?? 0)}</td>
                                <td className="r">{ln.qty_dry == null ? "—" : t3(ln.qty_dry)}</td>
                                <td className="r">{ln.price == null ? "—" : t3(ln.price)}</td>
                                <td>{ln.ccy}</td>
                                {/* Thành tiền của dòng theo NGUYÊN TỆ của dòng (giống form nhập). */}
                                <td className="r">
                                  {lineAmount(ln) == null
                                    ? "—"
                                    : `${t3(lineAmount(ln) as number)} ${ln.ccy === "VND" ? "tr.đ" : ln.ccy}`}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ),
                },
                ...(multi ? [{
                  key: "annex",
                  label: `Phụ lục (${d.children.length})`,
                  children: (
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
                      <th>Số phụ lục</th><th>Bắt đầu</th><th>Ngày giao</th><th>Hình thức</th><th>Đơn vị nhận</th>
                      <th className="r">SL (tấn)</th><th className="r">Quy khô</th>
                      <th className="r">Thành tiền (tr.đ)</th>
                      <th>Thanh toán</th><th>Đính kèm</th>
                      {canEdit && <th className="r" style={{ width: 150 }}>Thao tác</th>}
                    </tr></thead>
                    <tbody>
                      {d.children.map((k) => (
                        <tr key={k.id}>
                          <td style={{ fontWeight: 500 }}>{k.code}</td>
                          <td>{dmy(k.start_date) || "—"}</td>
                          <td>
                            {k.delivered_at
                              ? dmy(k.delivered_at)
                              : <span className="chip warn">Đang chờ giao</span>}
                          </td>
                          <td>{k.channel ? meta.channels[k.channel] : "—"}</td>
                          <td>{k.to_company ?? "—"}</td>
                          <td className="r">{t3(k.qty)}</td>
                          <td className="r">{t3(k.qty_dry)}</td>
                          <td className="r">{money(k.revenue)}</td>
                          <td style={{ whiteSpace: "nowrap", fontSize: 12.5 }}>
                            {dmy(k.payment_date) || "—"}
                            {k.payment_qty != null && (
                              <div style={{ color: "var(--muted)" }}>{t3(k.payment_qty)} tấn</div>
                            )}
                          </td>
                          <td><Docs docs={[...k.files, ...k.payment_docs]} /></td>
                          {canEdit && (
                            <td className="r" style={{ whiteSpace: "nowrap" }}>
                              {/* Lần giao quá cửa sổ sửa → chỉ xem. Server cũng chặn (403), nhưng
                                  báo trước ở đây để người dùng khỏi điền xong mới biết không lưu được. */}
                              {locked(k.delivered_at) ? (
                                <span style={{ color: "var(--muted)", fontSize: 11 }}>(chỉ xem)</span>
                              ) : (
                                <>
                                  <button className="btn" onClick={() => setForm({ initial: k })}>Sửa</button>{" "}
                                  <button className="btn" onClick={() => remove(k.id as number, `phụ lục ${k.code}`)}>Xoá</button>
                                </>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                      {d.children.length === 0 && (
                        <tr><td colSpan={canEdit ? 12 : 11} style={{ textAlign: "center", color: "var(--muted)", padding: 18 }}>
                          Chưa có phụ lục nào — hợp đồng chưa giao lần nào.
                        </td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
                    </>
                  ),
                }] : []),
              ]}
            />

            {!multi && (
              <div className="form-note" style={{ fontSize: 11.5, marginTop: 4 }}>
                Hợp đồng <b>giao 1 lần</b>: mở đợt ngày <b>{dmy(c.start_date)}</b>
                {c.delivered_at
                  ? <> · đã giao ngày <b>{dmy(c.delivered_at)}</b>.</>
                  : " · chưa giao — toàn bộ sản lượng đang nằm ở mục “đã ký HĐ chưa giao”."}
              </div>
            )}
          </>
        )}
      </Modal>

      {/* Sửa CHÍNH hợp đồng mẹ: không truyền `parent` → form mở ở chế độ hợp đồng, không phải phụ lục. */}
      {editSelf && c && (
        <ContractFormModal meta={meta} initial={c} onClose={() => setEditSelf(false)}
          onSaved={() => { load(); onChanged(); }} />
      )}
      {form && c && (
        <ContractFormModal meta={meta} parent={c} remaining={d?.remaining_qty ?? 0}
          initial={form.initial} onClose={() => setForm(null)}
          onSaved={() => { load(); onChanged(); }} />
      )}
    </>
  );
}
