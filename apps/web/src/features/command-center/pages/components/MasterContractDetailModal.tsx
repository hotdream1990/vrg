import { DisconnectOutlined, LinkOutlined, PlusOutlined } from "@ant-design/icons";
import { Modal } from "antd";
import { useCallback, useEffect, useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type MasterDetail,
  fetchMasterContract,
  linkMasterAnnexes,
} from "../../../../lib/master-contract-client";
import type { ContractMeta } from "../../../../lib/sales-contract-client";
import ContractAttach from "./ContractAttach";
import ContractFormModal from "./ContractFormModal";
import MasterAnnexPickerModal from "./MasterAnnexPickerModal";

type Props = {
  masterId: number;
  meta: ContractMeta;
  /** Tài khoản được sửa hồ sơ — không có thì ẩn nút gắn/gỡ phụ lục. */
  canEdit?: boolean;
  onClose: () => void;
  /** Gắn/gỡ phụ lục làm đổi số của bảng ngoài (số phụ lục · SL đã ký) → nạp lại danh sách. */
  onChanged?: () => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const num = (n: number | null | undefined) => (n == null ? "—" : t3(n));

/** Chi tiết HỢP ĐỒNG MẸ + danh sách PHỤ LỤC đã nối về nó.
 *
 *  Sản lượng ở đây chỉ để ĐỐI CHIẾU cam kết với phần đã ký ở phụ lục — tiêu thụ và "đã ký HĐ
 *  chưa giao" vẫn tính trên hợp đồng/đợt giao, hợp đồng mẹ không góp số vào báo cáo nào.
 */


export default function MasterContractDetailModal({ masterId, meta, canEdit, onClose, onChanged }: Props) {
  const [d, setD] = useState<MasterDetail | null>(null);
  const [picking, setPicking] = useState(false);
  // Nhập phụ lục MỚI ngay tại đây (chốt 22/08/2026): trước phải sang màn Hợp đồng & đợt giao rồi
  // gõ lại số hợp đồng mẹ để tìm — đang mở đúng hồ sơ mà vẫn phải đi đường vòng.
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    fetchMasterContract(masterId).then(setD).catch((e) => setErr(e.message));
  }, [masterId]);
  useEffect(() => { load(); }, [load]);

  const refresh = () => { load(); onChanged?.(); };

  /** Gỡ 1 phụ lục khỏi hồ sơ — chỉ bỏ liên kết, hợp đồng còn nguyên vẹn. */
  const detach = async (id: number, code: string) => {
    if (!confirm(`Gỡ “${code}” khỏi hợp đồng mẹ?\n\n`
      + "Hợp đồng vẫn còn nguyên, chỉ thôi là phụ lục của hồ sơ này.")) return;
    setBusy(true); setErr("");
    try { await linkMasterAnnexes(masterId, [id], false); refresh(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const m = d?.master;

  return (
    <Modal open width="min(1100px, 94vw)" destroyOnHidden footer={null} onCancel={onClose}
      title={m ? `Hợp đồng mẹ ${m.code} — ${m.company}` : "Đang tải…"}>
      {err && <div className="blt-error">{err}</div>}
      {m && d && (
        <>
          <div className="kpi-row ct-kpi">
            <div className="kpi"><div className="label">Loại</div>
              <div className="value">{meta.master_types[m.master_type] ?? m.master_type}</div></div>
            <div className="kpi"><div className="label">Khách hàng</div>
              <div className="value">{m.customer_name ?? "—"}</div></div>
            <div className="kpi"><div className="label">SL cam kết (tấn)</div>
              <div className="value">{m.qty > 0 ? t3(m.qty) : "—"}</div></div>
            <div className="kpi"><div className="label">Đã ký phụ lục (tấn)</div>
              <div className="value">{t3(d.annex_qty)}</div></div>
            <div className="kpi"><div className="label">Số phụ lục</div>
              <div className="value">{d.annexes.length}</div></div>
            <div className="kpi"><div className="label">Ngày ký</div>
              <div className="value">{dmy(m.sign_date) || "—"}</div></div>
            <div className="kpi"><div className="label">Thời hạn</div>
              <div className="value">{dmy(m.expiry_date) || "—"}</div></div>
          </div>

          {/* Hồ sơ mẹ chỉ cam kết CHỦNG LOẠI + SẢN LƯỢNG — đơn giá là số của từng chuyến, xem ở
              phụ lục (hoặc ô Công thức giá bên dưới với HĐ dài hạn). */}
          <h4 style={{ margin: "14px 0 6px" }}>Chủng loại &amp; sản lượng cam kết</h4>
          <div className="card table-scroll" style={{ padding: 0 }}>
            <table>
              <thead><tr>
                <th>Chủng loại</th>
                <th className="r" style={{ width: 160 }}>Số lượng (tấn)</th>
                <th className="r" style={{ width: 160 }}>Quy khô (tấn)</th>
              </tr></thead>
              <tbody>
                {m.lines.map((ln, i) => (
                  <tr key={i}>
                    <td>{ln.grade}</td>
                    <td className="r">{num(ln.qty)}</td>
                    <td className="r">{num(ln.qty_dry)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>


          {/* Chỉ HĐ dài hạn mới có công thức giá — HĐ nguyên tắc không có phần này, hiện ra một
              ô trống chỉ làm người đọc tưởng đang khai thiếu. */}
          {m.master_type === "long_term" && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Công thức giá</div>
              <div style={{ whiteSpace: "pre-wrap" }}>
                {m.price_formula || <span style={{ color: "var(--muted)" }}>— (chưa khai)</span>}
              </div>
            </div>
          )}

          <div style={{ marginTop: 12 }}>
            <ContractAttach label="Hợp đồng mẹ đã ký (scan)" docs={m.files} readOnly
              onChange={() => undefined} />
          </div>

          {m.note && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>Ghi chú</div>
              <div>{m.note}</div>
            </div>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "16px 0 6px" }}>
            <h4 style={{ margin: 0 }}>Phụ lục đã nối ({d.annexes.length})</h4>
            {canEdit && (
              <>
                <button className="btn btn-primary" disabled={busy} onClick={() => setAdding(true)}>
                  <PlusOutlined /> Thêm phụ lục
                </button>
                <button className="btn" disabled={busy} onClick={() => setPicking(true)}>
                  <LinkOutlined /> Gắn hợp đồng có sẵn
                </button>
              </>
            )}
          </div>
          <div className="card table-scroll" style={{ padding: 0 }}>
            <table className="mc-annex">
              <thead><tr>
                <th style={{ width: 200 }}>Số phụ lục</th>
                <th style={{ width: 120 }}>Loại HĐ</th>
                <th style={{ width: 110 }}>Ngày ký</th>
                <th className="r" style={{ width: 100 }}>SL (tấn)</th>
                <th style={{ width: 110 }}>Loại giao</th>
                <th style={{ width: 180 }}>Trạng thái</th>
                {canEdit && <th className="r" style={{ width: 90 }}>Thao tác</th>}
              </tr></thead>
              <tbody>
                {d.annexes.map((a) => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 500 }}>{a.code}</td>
                    <td>{meta.contract_types[a.contract_type ?? ""] ?? "—"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>{dmy(a.sign_date) || "—"}</td>
                    <td className="r" style={{ whiteSpace: "nowrap" }}>{t3(a.qty)}</td>
                    <td>{a.delivery_type === "multi" ? "Nhiều lần" : "1 lần"}</td>
                    <td>{a.completed_at
                      ? <span className="chip">Hoàn thành {dmy(a.completed_at)}</span>
                      : <span style={{ color: "var(--muted)" }}>Đang thực hiện</span>}</td>
                    {canEdit && (
                      <td className="r">
                        <button className="btn" disabled={busy} title="Gỡ khỏi hợp đồng mẹ"
                          onClick={() => detach(a.id as number, a.code)}>
                          <DisconnectOutlined />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
                {d.annexes.length === 0 && (
                  <tr><td colSpan={canEdit ? 7 : 6}
                    style={{ textAlign: "center", color: "var(--muted)", padding: 16 }}>
                    Chưa có phụ lục nào — bấm <b>Gắn hợp đồng có sẵn</b> ở trên, hoặc vào màn{" "}
                    <b>Hợp đồng &amp; đợt giao</b> thêm hợp đồng mới và chọn hợp đồng mẹ này.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
      {picking && m && (
        <MasterAnnexPickerModal master={m} meta={meta} onClose={() => setPicking(false)} onLinked={refresh} />
      )}
      {adding && m && (
        <ContractFormModal meta={meta} onClose={() => setAdding(false)} onSaved={refresh}
          // Chỉ điền sẵn ĐƠN VỊ + HỒ SƠ MẸ. Khách hàng và loại hợp đồng vẫn do người nhập
          // khai như mọi hợp đồng khác — hồ sơ mẹ không quyết định số liệu của phụ lục.
          preset={{ company: m.company, master_id: m.id }} />
      )}
    </Modal>
  );
}
