import { ContactsOutlined, PlusOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";

import {
  type Customer,
  deleteCustomer,
  fetchContractMeta,
  listCustomers,
  saveCustomer,
} from "../../../lib/sales-contract-client";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import CustomerFormModal from "./components/CustomerFormModal";
import "../../bulletin/bulletin.css";

const PAGE_SIZE = 50;

/** Quản lý hợp đồng → Khách hàng: danh mục RIÊNG của từng đơn vị (không dùng chung Tập đoàn). */
export default function CustomerPage() {
  const { canEditCap, canEditUnitData } = useAuth();
  const canEdit = canEditUnitData || canEditCap("sales_contract");

  const [units, setUnits] = useState<string[]>([]);
  const [rows, setRows] = useState<Customer[]>([]);
  // Tìm kiếm + phân trang Ở SERVER: danh mục là của TỪNG đơn vị nên tổng số khách tăng theo số
  // đơn vị — tải hết về máy rồi lọc tại chỗ sẽ nặng dần và không bao giờ tự dừng lại.
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  // `editing` = khách đang sửa · `adding` = đang thêm mới; cả hai cùng mở một modal.
  const [editing, setEditing] = useState<Customer | null>(null);
  const [adding, setAdding] = useState(false);
  const [lastCompany, setLastCompany] = useState("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    listCustomers({ q: filter.trim() || undefined, page, pageSize: PAGE_SIZE })
      .then((r) => { setRows(r.items); setTotal(r.total); })
      .catch((e) => setErr(e.message));
  }, [filter, page]);

  useEffect(() => {
    fetchContractMeta()
      .then((m) => {
        setUnits(m.units);
        setLastCompany((v) => v || m.units[0] || "");
      })
      .catch((e) => setErr(e.message));
    load();
  }, [load]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleActive = async (c: Customer) => {
    setBusy(true); setErr("");
    try { await saveCustomer({ ...c, is_active: !c.is_active }); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const remove = async (c: Customer) => {
    if (!confirm(`Xoá khách hàng “${c.name}” của ${c.company}?`)) return;
    setBusy(true); setErr("");
    try { await deleteCustomer(c.id as number); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ContactsOutlined style={{ marginRight: 8 }} />Khách hàng</h2>
          <p>Danh mục khách hàng của <b>từng đơn vị</b> — hợp đồng chỉ gán được khách của chính đơn vị đó.</p>
        </div>
      </div>

      {!canEdit && <ReadOnlyNotice cap="sales_contract" />}

      {err && <div className="blt-error">{err}</div>}

      <div className="blt-toolbar">
        {canEdit && (
          <button className="btn btn-primary" onClick={() => setAdding(true)} disabled={busy}>
            <PlusOutlined /> Thêm khách hàng
          </button>
        )}
        <input className="blt-date-input" style={{ width: 260 }} value={filter} placeholder="Tìm theo tên · mã · MST"
          onChange={(e) => { setPage(1); setFilter(e.target.value); }} />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          {total.toLocaleString("vi-VN")} khách hàng
        </span>
        {pages > 1 && (
          <>
            <button className="btn" disabled={page <= 1}
              onClick={() => setPage((v) => Math.max(1, v - 1))}>‹ Trước</button>
            <span style={{ fontSize: 13 }}>Trang {page} / {pages}</span>
            <button className="btn" disabled={page >= pages}
              onClick={() => setPage((v) => v + 1)}>Sau ›</button>
          </>
        )}
      </div>

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th>Đơn vị</th><th>Mã KH</th><th>Tên khách hàng</th><th>Mã số thuế</th>
            <th>Trạng thái</th><th>Ghi chú</th>{canEdit && <th className="r" style={{ width: 190 }}>Thao tác</th>}
          </tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>{c.company}</td>
                <td>{c.code ?? "—"}</td>
                <td style={{ fontWeight: 500 }}>{c.name}</td>
                <td>{c.tax_code ?? "—"}</td>
                <td><span className={c.is_active ? "chip" : "chip warn"}>{c.is_active ? "Đang dùng" : "Đã ẩn"}</span></td>
                <td style={{ color: "var(--muted)" }}>{c.note ?? "—"}</td>
                {canEdit && (
                  <td className="r" style={{ whiteSpace: "nowrap" }}>
                    <button className="btn" onClick={() => setEditing(c)} disabled={busy}>Sửa</button>{" "}
                    <button className="btn" onClick={() => toggleActive(c)} disabled={busy}>{c.is_active ? "Ẩn" : "Hiện"}</button>{" "}
                    <button className="btn" onClick={() => remove(c)} disabled={busy}>Xoá</button>
                  </td>
                )}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={canEdit ? 7 : 6} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có khách hàng nào.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {(adding || editing) && (
        <CustomerFormModal units={units} initial={editing} defaultCompany={lastCompany}
          onClose={() => { setAdding(false); setEditing(null); }}
          onSaved={(company) => { setLastCompany(company); load(); }} />
      )}
    </div>
  );
}
