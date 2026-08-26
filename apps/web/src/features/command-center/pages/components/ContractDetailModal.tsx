import {
  CheckCircleOutlined,
  EditOutlined,
  PlusOutlined,
  SplitCellsOutlined,
  UndoOutlined,
} from "@ant-design/icons";
import { Modal, Tabs } from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  type Contract,
  type ContractDetail,
  type ContractMeta,
  deleteContract,
  fetchContract,
  setContractCompletion,
  setContractDeliveryType,
} from "../../../../lib/sales-contract-client";
import { dmy } from "../../../../lib/date";
import { useEditWindow } from "../../../../lib/edit-window";
import ContractBatchTable, { Docs } from "./ContractBatchTable";
import ContractCompleteModal from "./ContractCompleteModal";
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
/** Thành tiền quy VNĐ, hiện theo TRIỆU ĐỒNG — thống nhất với ô "Thành tiền" ở form nhập.
 *  null = có dòng ngoại tệ thiếu tỷ giá → "—", KHÔNG hiển thị 0. */
const money = (n: number | null) =>
  (n == null ? "—" : (n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 3 }));

/** Lũy kế bảng dòng chi tiết hợp đồng — CHỈ cộng sản lượng: thành tiền của mỗi dòng theo nguyên tệ
 *  của chính nó, cộng chung nhiều loại tiền lại thành một số là số vô nghĩa. Một dòng thì khỏi cộng. */
function LinesTotal({ lines }: { lines: Contract["lines"] }) {
  if (lines.length < 2) return null;
  const qty = lines.reduce((s, ln) => s + (ln.qty ?? 0), 0);
  const dry = lines.reduce((s, ln) => s + (ln.qty_dry ?? 0), 0);
  return (
    <tfoot>
      <tr style={{ fontWeight: 600 }}>
        <td>Lũy kế {lines.length} dòng</td>
        <td className="r">{t3(qty)}</td>
        {/* Chủng loại không có quy khô → "—" như từng dòng, hiện 0 sẽ bị đọc là khai thiếu. */}
        <td className="r">{dry > 0 ? t3(dry) : "—"}</td>
        <td colSpan={3} />
      </tr>
    </tfoot>
  );
}

/** Chi tiết HỢP ĐỒNG + danh sách ĐỢT GIAO (mỗi đợt = 1 lần giao). */

/** Chip chứng chỉ + khoản premium — hiện ở màn chi tiết của cả hợp đồng gốc lẫn hợp đồng bán. */
function CertBadges({ certs, premium, ccy }: {
  certs?: string[]; premium?: number | null; ccy?: string | null;
}) {
  if (!certs?.length && premium == null) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Hàng có chứng chỉ</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {(certs ?? []).map((c) => (
          <span key={c} className="tag" style={{ padding: "2px 10px", borderRadius: 999,
            border: "1px solid var(--line)", background: "var(--panel-2)", fontSize: 12.5 }}>{c}</span>
        ))}
        {premium != null && (
          <span style={{ fontSize: 13 }}>
            Premium: <b>{premium.toLocaleString("vi-VN", { maximumFractionDigits: 3 })} {ccy ?? ""}</b>
            {ccy === "USD" ? "/tấn" : ""}
          </span>
        )}
        {!certs?.length && premium != null && (
          <span style={{ fontSize: 12, color: "var(--muted)" }}>(chưa chọn chứng chỉ)</span>
        )}
      </div>
    </div>
  );
}

export default function ContractDetailModal({ contractId, meta, canEdit, onClose, onChanged }: Props) {
  const [d, setD] = useState<ContractDetail | null>(null);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<{ initial: Contract | null } | null>(null);
  const [editSelf, setEditSelf] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    fetchContract(contractId).then(setD).catch((e) => setErr(e.message));
  }, [contractId]);
  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); onChanged(); };
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr("");
    try { await fn(); refresh(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const remove = async (id: number, label: string) => {
    if (!confirm(`Xoá ${label}?`)) return;
    await run(() => deleteContract(id));
  };

  const c = d?.contract;
  const multi = c?.delivery_type === "multi";
  const done = !!c?.completed_at;
  // Cửa sổ sửa CHỈ áp cho lần giao, mốc là ngày giao — hợp đồng sửa được suốt vòng đời.
  const { isEditable } = useEditWindow();
  const locked = (deliveredAt: string | null) => !!deliveredAt && !isEditable(deliveredAt);

  /** Đổi loại giao tại chỗ: lần giao đang nằm trên hợp đồng được dời xuống đợt giao đầu tiên. */
  const switchType = async () => {
    if (!c) return;
    const to = multi ? "single" : "multi";
    const msg = multi
      ? `Chuyển hợp đồng ${c.code} về GIAO 1 LẦN?`
      : `Chuyển hợp đồng ${c.code} sang GIAO NHIỀU LẦN?\n\n`
        + (c.delivered_at
          ? "Lần giao đã nhập sẽ tự chuyển thành ĐỢT GIAO đầu tiên (giữ nguyên ngày giao, hoá "
            + "đơn, thanh toán, chi tiết hàng). Hợp đồng giữ lại sản lượng đã ký."
          : "Sau đó nhập từng đợt giao cho tới khi hết sản lượng hợp đồng.");
    if (!confirm(msg)) return;
    await run(() => setContractDeliveryType(c.id as number, to));
  };

  return (
    <>
      <Modal open width="min(1280px, 94vw)" title={c ? `Hợp đồng ${c.code} — ${c.company}` : "Đang tải…"}
        onCancel={onClose} footer={null} destroyOnHidden>
        {err && <div className="blt-error">{err}</div>}
        {c && d && (
          <>
            {/* Hàng số liệu để NGOÀI tab: đây là thứ người dùng mở hợp đồng ra để xem đầu tiên,
                cần thấy ngay cả khi đang ở tab đợt giao. */}
            <div className="kpi-row ct-kpi">
              {/* Hợp đồng có nối hồ sơ mẹ thì ghi ra để tra cứu — số liệu vẫn của chính hợp
                  đồng này, hồ sơ mẹ không góp gì vào. */}
              {d.master && (
                <div className="kpi"><div className="label">Hợp đồng mẹ</div>
                  <div className="value" title={meta.master_types[d.master.master_type]}>
                    {d.master.code}
                  </div></div>
              )}
              <div className="kpi"><div className="label">Khách hàng</div><div className="value">{d.customer_name ?? "—"}</div></div>
              <div className="kpi"><div className="label">Loại hợp đồng</div>
                <div className="value">{meta.contract_types[c.contract_type ?? ""] ?? "(chưa khai)"}</div></div>
              <div className="kpi"><div className="label">Loại giao</div>
                <div className="value" title={meta.delivery_types[c.delivery_type]}>
                  {multi ? "Giao nhiều lần" : "Giao 1 lần"}
                </div></div>
              <div className="kpi"><div className="label">Sản lượng HĐ (tấn)</div><div className="value">{t3(c.qty)}</div></div>
              <div className="kpi"><div className="label">Thành tiền (tr.đ)</div><div className="value">{money(c.revenue)}</div></div>
              {/* Tiền của HÀNG THỰC GIAO: đơn giá/sản lượng chốt ở từng đợt nên lệch với tiền hợp
                  đồng đã ký là bình thường — phải hiện cả hai mới đối chiếu được. */}
              <div className="kpi"><div className="label">TT đã giao (tr.đ)</div>
                <div className="value">{money(d.delivered_revenue)}</div></div>
              <div className="kpi"><div className="label">Đã giao (tấn)</div><div className="value">{t3(d.delivered_qty)}</div></div>
              {/* Còn phải giao = sản lượng hợp đồng − đã giao (tính trên HỢP ĐỒNG, không theo đợt). */}
              <div className="kpi"><div className="label">Còn phải giao (tấn)</div>
                <div className="value">{t3(d.remaining_qty)}</div></div>
              {d.over_qty > 1e-9 && (
                <div className="kpi"><div className="label">Giao vượt (tấn)</div>
                  <div className="value" style={{ color: "var(--warn, #d48806)" }}>{t3(d.over_qty)}</div></div>
              )}
              {/* 3 trạng thái — giao đủ hàng rồi mà vẫn ghi "đang thực hiện" thì bị đọc nhầm là
                  còn nợ hàng; nhưng cũng chưa phải "hoàn thành" vì đơn vị chưa chốt. */}
              <div className="kpi"><div className="label">Trạng thái</div>
                <div className="value">
                  {done ? `Hoàn thành ${dmy(c.completed_at)}`
                    : d.remaining_qty <= 1e-9 ? "Đã giao đủ" : "Đang thực hiện"}
                </div></div>
              <div className="kpi"><div className="label">Ngày ký</div><div className="value">{dmy(c.sign_date) || "—"}</div></div>
              <div className="kpi"><div className="label">Thời hạn</div><div className="value">{dmy(c.expiry_date) || "—"}</div></div>
            </div>

            <CertBadges certs={c.certs} premium={c.premium} ccy={c.premium_ccy} />

            {canEdit && (
              <div className="blt-toolbar" style={{ marginTop: 10 }}>
                {done ? (
                  <button className="btn" disabled={busy} onClick={() => run(
                    () => setContractCompletion(c.id as number, null))}>
                    <UndoOutlined /> Mở lại hợp đồng
                  </button>
                ) : (
                  <>
                    <button className="btn" disabled={busy} onClick={switchType}>
                      <SplitCellsOutlined />{" "}
                      {multi ? "Chuyển về giao 1 lần" : "Chuyển sang giao nhiều lần"}
                    </button>
                    <button className="btn btn-primary" disabled={busy} onClick={() => setCompleting(true)}>
                      <CheckCircleOutlined /> Hoàn thành hợp đồng
                    </button>
                  </>
                )}
                {done && (
                  <span style={{ color: "var(--muted)", fontSize: 12 }}>
                    Hợp đồng đã chốt — phần chưa giao không còn nằm ở “đã ký HĐ chưa giao”.
                    Mở lại nếu cần sửa tiếp.
                  </span>
                )}
              </div>
            )}

            {/* Chia tab để bớt cuộn: hợp đồng nhiều đợt giao trước đây phải cuộn rất sâu mới tới
                bảng đợt giao — phần người dùng thao tác nhiều nhất. */}
            <Tabs
              defaultActiveKey={multi ? "batch" : "info"}
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
                            <button className="btn" disabled={done} onClick={() => setEditSelf(true)}>
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
                        {!multi && (
                          <>
                            <div>
                              <div style={{ color: "var(--muted)", fontSize: 12 }}>Hoá đơn</div>
                              {c.invoice_no ?? "—"} <Docs docs={c.invoice_docs} />
                            </div>
                          </>
                        )}
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
                          <LinesTotal lines={c.lines} />
                        </table>
                      </div>
                    </>
                  ),
                },
                ...(multi ? [{
                  key: "batch",
                  label: `Đợt giao (${d.children.length})`,
                  children: (
                    <>
                      <div className="blt-toolbar" style={{ marginTop: 14 }}>
                        <b>Đợt giao ({d.children.length})</b>
                        {canEdit && !done && (
                          <button className="btn btn-primary" onClick={() => setForm({ initial: null })}>
                            <PlusOutlined /> Thêm đợt giao
                          </button>
                        )}
                        {d.remaining_qty <= 1e-9 && (
                          <span style={{ color: "var(--muted)", fontSize: 12 }}>
                            Đã giao đủ sản lượng hợp đồng
                            {!done && " — bấm “Hoàn thành hợp đồng” để chốt."}
                          </span>
                        )}
                        {d.pending_qty > 1e-9 && (
                          <span className="chip warn">
                            {t3(d.pending_qty)} tấn đang chờ giao (chưa điền ngày giao)
                          </span>
                        )}
                      </div>
                      <ContractBatchTable rows={d.children} meta={meta} canEdit={canEdit && !done}
                        locked={locked} onEdit={(k) => setForm({ initial: k })}
                        onDelete={(k) => remove(k.id as number, `đợt giao ${k.code}`)} />
                    </>
                  ),
                }] : []),
              ]}
            />

            {!multi && (
              <div className="form-note" style={{ fontSize: 11.5, marginTop: 4 }}>
                Hợp đồng <b>giao 1 lần</b>:{" "}
                {c.delivered_at
                  ? <>đã giao ngày <b>{dmy(c.delivered_at)}</b>.</>
                  : "chưa giao — toàn bộ sản lượng đang nằm ở mục “đã ký HĐ chưa giao”."}
                {" "}Thực tế giao làm nhiều lần thì bấm <b>Chuyển sang giao nhiều lần</b>.
              </div>
            )}
          </>
        )}
      </Modal>

      {/* Sửa CHÍNH hợp đồng: không truyền `parent` → form mở ở chế độ hợp đồng, không phải đợt giao. */}
      {editSelf && c && (
        <ContractFormModal meta={meta} initial={c} onClose={() => setEditSelf(false)}
          onSaved={refresh} />
      )}
      {form && c && d && (
        <ContractFormModal meta={meta} parent={c}
          otherQty={d.children.reduce(
            (s, k) => s + (k.id === form.initial?.id ? 0 : k.qty), 0)}
          initial={form.initial} onClose={() => setForm(null)} onSaved={refresh} />
      )}
      {completing && d && (
        <ContractCompleteModal d={d} onClose={() => setCompleting(false)} onDone={refresh} />
      )}
    </>
  );
}
