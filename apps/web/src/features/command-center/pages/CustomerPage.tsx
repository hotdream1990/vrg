import { ContactsOutlined, PlusOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type Customer,
  deleteCustomer,
  fetchContractMeta,
  listCustomers,
  saveCustomer,
} from "../../../lib/sales-contract-client";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import "../../bulletin/bulletin.css";

type Draft = { id: number | null; company: string; code: string; name: string; tax_code: string; note: string };
const EMPTY: Draft = { id: null, company: "", code: "", name: "", tax_code: "", note: "" };

/** Quản lý hợp đồng → Khách hàng: danh mục RIÊNG của từng đơn vị (không dùng chung Tập đoàn). */
export default function CustomerPage() {
  const { canEditCap, user } = useAuth();
  const isMember = user?.role === "member";
  const canEdit = isMember || canEditCap("sales_contract");

  const [units, setUnits] = useState<string[]>([]);
  const [rows, setRows] = useState<Customer[]>([]);
  const [form, setForm] = useState<Draft>({ ...EMPTY });
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    listCustomers().then(setRows).catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    fetchContractMeta()
      .then((m) => {
        setUnits(m.units);
        setForm((f) => (f.company ? f : { ...f, company: m.units[0] ?? "" }));
      })
      .catch((e) => setErr(e.message));
    load();
  }, [load]);

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) => `${r.name} ${r.code ?? ""} ${r.tax_code ?? ""} ${r.company}`
      .toLowerCase().includes(q));
  }, [rows, filter]);

  const save = async () => {
    if (!form.company) { setErr("Chọn đơn vị sở hữu danh mục."); return; }
    if (!form.name.trim()) { setErr("Nhập tên khách hàng."); return; }
    setBusy(true); setErr("");
    try {
      await saveCustomer({
        id: form.id, company: form.company, code: form.code || null, name: form.name.trim(),
        tax_code: form.tax_code || null, note: form.note || null, is_active: true,
      });
      setForm({ ...EMPTY, company: form.company });
      load();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

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

  const edit = (c: Customer) => setForm({
    id: c.id, company: c.company, code: c.code ?? "", name: c.name,
    tax_code: c.tax_code ?? "", note: c.note ?? "",
  });

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ContactsOutlined style={{ marginRight: 8 }} />Khách hàng</h2>
          <p>Danh mục khách hàng của <b>từng đơn vị</b> — hợp đồng chỉ gán được khách của chính đơn vị đó.</p>
        </div>
      </div>

      {!isMember && <ReadOnlyNotice cap="sales_contract" />}

      {canEdit && (
        <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label className="form-field">Đơn vị
            <select className="blt-date-input" value={form.company} disabled={form.id != null}
              onChange={(e) => setForm({ ...form, company: e.target.value })}>
              {units.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </label>
          <label className="form-field">Mã KH
            <input className="blt-date-input" style={{ width: 110 }} value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </label>
          <label className="form-field" style={{ flex: 1, minWidth: 220 }}>Tên khách hàng
            <input className="blt-date-input" value={form.name} placeholder="vd: Công ty TNHH ABC"
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label className="form-field">Mã số thuế
            <input className="blt-date-input" style={{ width: 140 }} value={form.tax_code}
              onChange={(e) => setForm({ ...form, tax_code: e.target.value })} />
          </label>
          <label className="form-field" style={{ flex: 1, minWidth: 160 }}>Ghi chú
            <input className="blt-date-input" value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </label>
          <button className="btn btn-primary" onClick={save} disabled={busy || !form.name.trim()}>
            {form.id != null ? "Cập nhật" : <><PlusOutlined /> Thêm khách hàng</>}
          </button>
          {form.id != null && (
            <button className="btn" onClick={() => setForm({ ...EMPTY, company: form.company })} disabled={busy}>Hủy</button>
          )}
          <div className="form-note" style={{ fontSize: 11.5, flexBasis: "100%" }}>
            Lưu ý: danh mục tách riêng theo đơn vị nên trùng tên giữa hai đơn vị là bình thường; trong
            cùng một đơn vị thì không được trùng tên. Khách đã gắn hợp đồng chỉ ẩn được, không xoá.
          </div>
        </div>
      )}

      {err && <div className="blt-error">{err}</div>}

      <div className="blt-toolbar">
        <input className="blt-date-input" style={{ width: 260 }} value={filter} placeholder="Tìm theo tên · mã · MST"
          onChange={(e) => setFilter(e.target.value)} />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{shown.length} khách hàng</span>
      </div>

      <div className="card" style={{ padding: 0, overflow: "auto" }}>
        <table>
          <thead><tr>
            <th>Đơn vị</th><th>Mã KH</th><th>Tên khách hàng</th><th>Mã số thuế</th>
            <th>Trạng thái</th><th>Ghi chú</th>{canEdit && <th className="r" style={{ width: 190 }}>Thao tác</th>}
          </tr></thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.id} style={{ background: form.id === c.id ? "var(--card-2, #eef6f0)" : undefined }}>
                <td>{c.company}</td>
                <td>{c.code ?? "—"}</td>
                <td style={{ fontWeight: 500 }}>{c.name}</td>
                <td>{c.tax_code ?? "—"}</td>
                <td><span className={c.is_active ? "chip" : "chip warn"}>{c.is_active ? "Đang dùng" : "Đã ẩn"}</span></td>
                <td style={{ color: "var(--muted)" }}>{c.note ?? "—"}</td>
                {canEdit && (
                  <td className="r" style={{ whiteSpace: "nowrap" }}>
                    <button className="btn" onClick={() => edit(c)} disabled={busy}>Sửa</button>{" "}
                    <button className="btn" onClick={() => toggleActive(c)} disabled={busy}>{c.is_active ? "Ẩn" : "Hiện"}</button>{" "}
                    <button className="btn" onClick={() => remove(c)} disabled={busy}>Xoá</button>
                  </td>
                )}
              </tr>
            ))}
            {shown.length === 0 && (
              <tr><td colSpan={canEdit ? 7 : 6} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có khách hàng nào.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
