import { FileProtectOutlined, PlusOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";

import {
  type Contract,
  type ContractFilters,
  type ContractMeta,
  type ContractRow,
  deleteContract,
  fetchContractMeta,
  listContracts,
} from "../../../lib/sales-contract-client";
import { dmy } from "../../../lib/date";
import { useAuth } from "../../auth/AuthContext";
import DateInput from "../sections/DateInput";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ContractDetailModal from "./components/ContractDetailModal";
import ContractFormModal from "./components/ContractFormModal";
import "../../bulletin/bulletin.css";

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
/** Quá thời hạn hợp đồng mà vẫn còn hàng chưa giao. */
const overdue = (r: ContractRow) =>
  r.remaining_qty + r.pending_qty > 0 && !!r.expiry_date
  && r.expiry_date < new Date().toISOString().slice(0, 10);

/** Quản lý hợp đồng → Hợp đồng & phụ lục: danh sách HỢP ĐỒNG MẸ + tiến độ giao. */
export default function SalesContractPage() {
  const { canEditCap, user } = useAuth();
  const isMember = user?.role === "member";
  const canEdit = isMember || canEditCap("sales_contract");

  const [meta, setMeta] = useState<ContractMeta | null>(null);
  const [rows, setRows] = useState<ContractRow[]>([]);
  const [f, setF] = useState<ContractFilters>({ status: "all" });
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState<{ initial: Contract | null } | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    listContracts(f)
      .then((r) => setRows(r.contracts))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [f]);

  useEffect(() => { fetchContractMeta().then(setMeta).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);

  const remove = async (r: ContractRow) => {
    if (!confirm(`Xoá hợp đồng ${r.code} của ${r.company}?`)) return;
    try { await deleteContract(r.id as number); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FileProtectOutlined style={{ marginRight: 8 }} />Hợp đồng &amp; phụ lục</h2>
          <p>
            Danh sách <b>hợp đồng mẹ</b>. Hợp đồng <b>giao nhiều lần</b> thì mở ra để thêm{" "}
            <b>phụ lục</b> — mỗi phụ lục là một lần giao đã hoàn tất, tính ngay vào tiêu thụ.
          </p>
        </div>
        {canEdit && meta && (
          <div className="actions">
            <button className="btn btn-primary" onClick={() => setForm({ initial: null })}>
              <PlusOutlined /> Thêm hợp đồng
            </button>
          </div>
        )}
      </div>

      {!isMember && <ReadOnlyNotice cap="sales_contract" />}

      {meta && (
        <div className="blt-toolbar">
          {!isMember || meta.units.length > 1 ? (
            <label className="blt-date-label">Đơn vị
              <select className="blt-date-input" value={f.company ?? ""}
                onChange={(e) => setF({ ...f, company: e.target.value || undefined })}>
                <option value="">Tất cả</option>
                {meta.units.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </label>
          ) : null}
          <label className="blt-date-label">Khách hàng
            <select className="blt-date-input" value={f.customer_id ?? ""}
              onChange={(e) => setF({ ...f, customer_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Tất cả</option>
              {meta.customers.map((x) => <option key={x.id} value={x.id as number}>{x.name}</option>)}
            </select>
          </label>
          <label className="blt-date-label">Trạng thái
            <select className="blt-date-input" value={f.status ?? "all"}
              onChange={(e) => setF({ ...f, status: e.target.value as ContractFilters["status"] })}>
              <option value="all">Tất cả</option>
              <option value="open">Còn hàng chưa giao</option>
              <option value="done">Đã giao đủ</option>
            </select>
          </label>
          <label className="blt-date-label">Ngày ký từ
            <DateInput value={f.date_from ?? ""} onChange={(v) => setF({ ...f, date_from: v || undefined })} />
          </label>
          <label className="blt-date-label">đến
            <DateInput value={f.date_to ?? ""} onChange={(v) => setF({ ...f, date_to: v || undefined })} />
          </label>
          <input className="blt-date-input" style={{ width: 200 }} placeholder="Tìm theo số HĐ"
            value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value || undefined })} />
          <span style={{ color: "var(--muted)", fontSize: 13 }}>
            {loading ? "Đang tải…" : `${rows.length} hợp đồng`}
          </span>
        </div>
      )}

      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th>Đơn vị</th><th>Số hợp đồng</th><th>Khách hàng</th><th>Loại giao</th>
            <th>Ngày ký</th><th className="r">Cam kết (tấn)</th><th className="r">Đã giao</th>
            <th className="r">Chờ giao</th><th className="r">Chưa mở đợt</th><th className="r">Phụ lục</th>
            <th className="r" style={{ width: 160 }}>Thao tác</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.company}</td>
                <td style={{ fontWeight: 500 }}>{r.code}</td>
                <td>{r.customer_name ?? "—"}</td>
                <td>
                  <span className="chip" title={meta?.delivery_types[r.delivery_type]}>
                    {r.delivery_type === "multi" ? "Nhiều lần" : "1 lần"}
                  </span>
                </td>
                <td>{dmy(r.sign_date) || "—"}</td>
                <td className="r">{t3(r.qty)}</td>
                <td className="r">{t3(r.delivered_qty)}</td>
                {/* Đang chờ giao = đã mở đợt, chưa điền ngày giao → phần đang nằm ở khối 3. */}
                <td className="r">{t3(r.pending_qty)}</td>
                <td className="r">
                  {/* Chưa mở đợt là trạng thái BÌNH THƯỜNG của hợp đồng mới ký — chỉ tô cảnh báo
                      khi đã QUÁ THỜI HẠN mà vẫn còn hàng chưa giao xong. */}
                  <span className={overdue(r) ? "chip warn" : "chip"}>{t3(r.remaining_qty)}</span>
                </td>
                <td className="r">{r.delivery_type === "multi" ? r.children : "—"}</td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  <button className="btn" onClick={() => setOpenId(r.id as number)}>Xem</button>{" "}
                  {canEdit && <>
                    <button className="btn" onClick={() => setForm({ initial: r })}>Sửa</button>{" "}
                    <button className="btn" onClick={() => remove(r)}>Xoá</button>
                  </>}
                </td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr><td colSpan={11} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có hợp đồng nào khớp bộ lọc.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {meta && openId != null && (
        <ContractDetailModal contractId={openId} meta={meta} canEdit={canEdit}
          onClose={() => setOpenId(null)} onChanged={load} />
      )}
      {meta && form && (
        <ContractFormModal meta={meta} initial={form.initial}
          onClose={() => setForm(null)} onSaved={load} />
      )}
    </div>
  );
}
