import { FileTextOutlined, PlusOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";

import { dmy } from "../../../lib/date";
import {
  type MasterContract,
  type MasterFilters,
  deleteMasterContract,
  listMasterContracts,
} from "../../../lib/master-contract-client";
import { type ContractMeta, fetchContractMeta } from "../../../lib/sales-contract-client";
import { useAuth } from "../../auth/AuthContext";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import MasterContractDetailModal from "./components/MasterContractDetailModal";
import MasterContractFormModal from "./components/MasterContractFormModal";
import "../../bulletin/bulletin.css";

const PAGE_SIZE = 25;
const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Quản lý hợp đồng → Hợp đồng mẹ: hồ sơ gốc HĐ nguyên tắc (HĐNT) / HĐ dài hạn (HĐDH).
 *
 *  Hợp đồng mẹ giữ khách hàng, chủng loại–sản lượng cam kết, công thức giá và bản scan. Từng
 *  chuyến hàng nhập ở màn "Hợp đồng & đợt giao" rồi chọn hợp đồng mẹ — bản ghi đó là PHỤ LỤC.
 *  ⚠ Màn này KHÔNG có số tiêu thụ: mọi báo cáo sản lượng vẫn tính trên hợp đồng/đợt giao.
 */
export default function MasterContractPage() {
  const { canEditCap, isUnitAccount, canEditUnitData } = useAuth();
  const isMember = isUnitAccount;   // nhập liệu + lãnh đạo: chỉ thấy đơn vị của mình
  const canEdit = canEditUnitData || canEditCap("sales_contract");

  const [meta, setMeta] = useState<ContractMeta | null>(null);
  const [rows, setRows] = useState<MasterContract[]>([]);
  // Phân trang Ở SERVER — hồ sơ hợp đồng mẹ dài thêm mỗi năm, không tải hết về máy.
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [f, setF] = useState<MasterFilters>({});
  const [form, setForm] = useState<{ initial: MasterContract | null } | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [lastCompany, setLastCompany] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    listMasterContracts({ ...f, page, page_size: PAGE_SIZE })
      .then((r) => { setRows(r.items); setTotal(r.total); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [f, page]);

  useEffect(() => {
    fetchContractMeta()
      .then((m) => { setMeta(m); setLastCompany((v) => v || m.units[0] || ""); })
      .catch((e) => setErr(e.message));
  }, []);
  useEffect(() => { load(); }, [load]);

  // Đổi bộ lọc thì về trang 1 — đang ở trang 5 mà lọc còn 2 trang sẽ ra bảng trống.
  const setFilter = (next: MasterFilters) => { setPage(1); setF(next); };

  const remove = async (m: MasterContract) => {
    if (!confirm(`Xoá hợp đồng mẹ ${m.code} của ${m.company}?`)) return;
    try { await deleteMasterContract(m.id as number); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FileTextOutlined style={{ marginRight: 8 }} />Hợp đồng mẹ (HĐNT/HĐDH)</h2>
          <p>
            Hồ sơ gốc ký với khách hàng: <b>HĐ nguyên tắc</b> hoặc <b>HĐ dài hạn</b> — số hợp đồng,
            khách hàng, chủng loại kèm sản lượng cam kết, công thức giá và bản scan. Từng chuyến
            hàng vẫn nhập ở <b>Hợp đồng &amp; đợt giao</b> như bình thường, chỉ chọn thêm hợp đồng
            mẹ này để nối vào hồ sơ — <b>không đổi</b> khách hàng hay bất kỳ số liệu nào của hợp đồng.
          </p>
        </div>
        {canEdit && meta && (
          <div className="actions">
            <button className="btn btn-primary" onClick={() => setForm({ initial: null })}>
              <PlusOutlined /> Thêm hợp đồng mẹ
            </button>
          </div>
        )}
      </div>

      {!canEdit && <ReadOnlyNotice cap="sales_contract" />}

      {meta && (
        <div className="blt-toolbar">
          {!isMember || meta.units.length > 1 ? (
            <label className="blt-date-label">Đơn vị
              <select className="blt-date-input" value={f.company ?? ""}
                onChange={(e) => setFilter({ ...f, company: e.target.value || undefined })}>
                <option value="">Tất cả</option>
                {meta.units.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </label>
          ) : null}
          <label className="blt-date-label">Loại
            <select className="blt-date-input" value={f.master_type ?? ""}
              onChange={(e) => setFilter({
                ...f, master_type: (e.target.value || undefined) as MasterFilters["master_type"],
              })}>
              <option value="">Tất cả</option>
              {Object.entries(meta.master_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <input className="blt-date-input" style={{ width: 220 }} placeholder="Tìm theo số HĐ"
            value={f.q ?? ""} onChange={(e) => setFilter({ ...f, q: e.target.value || undefined })} />
          <span style={{ color: "var(--muted)", fontSize: 13 }}>
            {loading ? "Đang tải…" : `${total.toLocaleString("vi-VN")} hợp đồng mẹ`}
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
      )}

      {err && <div className="blt-error">{err}</div>}

      {/* Bề rộng chốt ở từng cột (`.mc-table` là `table-layout:fixed`): tên đơn vị / tên khách
          hàng rất dài, để bảng tự chia thì cột bị bóp còn vài ký tự. Màn hẹp thì cuộn ngang.
          KHÔNG có cột "Công thức giá": nó là đoạn văn dài, chiếm chỗ của mọi cột khác mà đọc vẫn
          cụt — xem đủ ở màn chi tiết. */}
      <div className="card table-scroll" style={{ padding: 0 }}>
        <table className="mc-table">
          <thead><tr>
            <th style={{ width: 150 }}>Đơn vị</th>
            <th style={{ width: 135 }}>Số hợp đồng</th>
            <th style={{ width: 95 }}>Loại</th>
            <th style={{ width: 150 }}>Khách hàng</th>
            <th style={{ width: 120 }}>Chủng loại</th>
            <th className="r" style={{ width: 90 }}>SL cam kết (tấn)</th>
            <th className="r" style={{ width: 100 }}>Đã ký phụ lục</th>
            {/* Gộp ngày ký + thời hạn thành MỘT cột: hai cột ngày cạnh nhau ngốn chỗ của cột
                chữ, mà đọc thì luôn đọc thành một khoảng hiệu lực. */}
            <th style={{ width: 110 }}>Hiệu lực</th>
            <th className="r" style={{ width: 175 }}>Thao tác</th>
          </tr></thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id}>
                <td>{m.company}</td>
                <td style={{ fontWeight: 500 }}>{m.code}</td>
                <td><span className="chip" style={{ display: "inline-block" }}>
                  {meta?.master_types[m.master_type] ?? m.master_type}</span></td>
                <td>{m.customer_name ?? "—"}</td>
                <td style={{ fontSize: 12.5 }}>{m.lines.map((l) => l.grade).join(", ") || "—"}</td>
                {/* HĐ nguyên tắc thường không cam kết sản lượng → "—", KHÔNG hiện 0 (0 bị đọc là
                    cam kết bằng không). */}
                <td className="r" style={{ whiteSpace: "nowrap" }}>{m.qty > 0 ? t3(m.qty) : "—"}</td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  {t3(m.annex_qty ?? 0)}
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    {(m.annexes ?? 0).toLocaleString("vi-VN")} phụ lục
                  </div>
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {dmy(m.sign_date) || "—"}
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    đến {dmy(m.expiry_date) || "—"}
                  </div>
                </td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  <button className="btn" onClick={() => setOpenId(m.id as number)}>Xem</button>{" "}
                  {canEdit && (
                    <>
                      <button className="btn" onClick={() => setForm({ initial: m })}>Sửa</button>{" "}
                      <button className="btn" onClick={() => remove(m)}>Xoá</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr><td colSpan={9} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có hợp đồng mẹ nào khớp bộ lọc.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {meta && form && (
        <MasterContractFormModal meta={meta} initial={form.initial} defaultCompany={lastCompany}
          onClose={() => setForm(null)}
          onSaved={(company) => { setLastCompany(company); load(); }} />
      )}
      {meta && openId != null && (
        <MasterContractDetailModal masterId={openId} meta={meta} canEdit={canEdit}
          onClose={() => setOpenId(null)} onChanged={load} />
      )}
    </div>
  );
}
