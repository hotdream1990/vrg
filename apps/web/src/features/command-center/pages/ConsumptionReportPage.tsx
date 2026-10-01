import { DownloadOutlined, ExportOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type ConsumptionReport,
  type ContractMeta,
  downloadConsumptionXlsx,
  fetchConsumption,
  fetchContractMeta,
} from "../../../lib/sales-contract-client";
import { useAuth } from "../../auth/AuthContext";
import CustomerPicker from "../sections/CustomerPicker";
import { MultiSelect } from "./analytics/AnalyticsFilters";
import DateInput from "../sections/DateInput";
import ConsumptionByCustomer from "./components/ConsumptionByCustomer";
import ConsumptionCompanyTable from "./components/ConsumptionCompanyTable";
import ConsumptionDeliveryHistory from "./components/ConsumptionDeliveryHistory";
import ConsumptionKpiRow from "./components/ConsumptionKpiRow";
import ConsumptionMasterProgress from "./components/ConsumptionMasterProgress";
import { reportCompanies, sumBacklog, sumConsumption } from "./components/consumption-report-totals";
import "../../bulletin/bulletin.css";

const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => `${new Date().toISOString().slice(0, 7)}-01`;

/** Báo cáo → Tiêu thụ: số TÍNH TỪ HỢP ĐỒNG (các lần giao), KHÔNG còn biểu nhập tay. */
export default function ConsumptionReportPage() {
  const { isUnitAccount } = useAuth();
  const isMember = isUnitAccount;   // nhập liệu + lãnh đạo: chỉ thấy đơn vị của mình

  const [meta, setMeta] = useState<ContractMeta | null>(null);
  const [from, setFrom] = useState(monthStart());
  const [to, setTo] = useState(today());
  const [company, setCompany] = useState<string>("");
  const [customerIds, setCustomerIds] = useState<number[]>([]);
  const [grades, setGrades] = useState<string[]>([]);
  const [rep, setRep] = useState<ConsumptionReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    if (!from || !to) return;
    setLoading(true); setErr("");
    fetchConsumption(from, to, company || undefined, customerIds, grades)
      .then(setRep)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [from, to, company, customerIds, grades]);

  useEffect(() => { fetchContractMeta().then(setMeta).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);

  const companies = useMemo(() => reportCompanies(rep), [rep]);
  const totals = useMemo(() => sumConsumption(rep, companies), [rep, companies]);
  const backlog = useMemo(() => sumBacklog(rep?.backlog), [rep]);

  const exportXlsx = async () => {
    setBusy(true); setErr("");
    try { await downloadConsumptionXlsx(from, to, company || undefined, customerIds, grades); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ExportOutlined style={{ marginRight: 8 }} />Báo cáo tiêu thụ</h2>
          <p>
            Tổng hợp từ <b>các lần giao</b> ghi trên hợp đồng &amp; đợt giao — đơn vị không nhập tay
            số tiêu thụ nữa. Sản lượng tính theo <b>quy khô</b>: latex, mủ nguyên liệu và mủ dây
            lấy số quy khô, chủng loại chưa khai quy khô thì giữ nguyên số đang có. Phần phải giao lấy
            tại ngày cuối kỳ; <b>Tổng phải giao</b> = HĐ chuyến + HĐ nguyên tắc (HĐNT) đã ký chưa giao + HĐ dài
            hạn còn phải giao. Phần dài hạn tính theo <b>cam kết HĐ dài hạn (HĐDH)</b> (gồm cả phần chưa ký phụ
            lục; HĐNT không tính cam kết) nên khác số “Đã ký HĐ chưa giao” ở biểu Tồn kho. Nút <b>Xuất Excel</b> cho ra 2 sheet: tổng hợp theo đơn vị và{" "}
            <b>chi tiết từng dòng bán</b> (đã bật sẵn bộ lọc để soát/pivot trong Excel).
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-primary" onClick={exportXlsx} disabled={busy || loading}
            title="2 sheet: Tổng hợp theo đơn vị · Chi tiết từng dòng bán của mỗi lần giao">
            <DownloadOutlined /> {busy ? "Đang xuất…" : "Xuất Excel"}
          </button>
        </div>
      </div>

      <div className="blt-toolbar">
        <label className="blt-date-label">Từ ngày<DateInput value={from} onChange={setFrom} /></label>
        <label className="blt-date-label">Đến ngày<DateInput value={to} onChange={setTo} /></label>
        {meta && (!isMember || meta.units.length > 1) && (
          <label className="blt-date-label">Đơn vị
            <select className="blt-date-input" value={company}
              onChange={(e) => { setCompany(e.target.value); setCustomerIds([]); }}>
              <option value="">Tất cả</option>
              {meta.units.map((u) => <option key={u} value={u}>{u}</option>)}
            </select>
          </label>
        )}
        <label className="blt-date-label">Khách hàng
          <CustomerPicker multiple width={320} value={customerIds} company={company || undefined}
            onChange={setCustomerIds} />
        </label>
        {/* Lọc chủng loại tính LẠI theo từng dòng chi tiết (một lần giao có thể nhiều chủng loại)
            — cả bảng, khối "theo khách hàng", cột chưa giao lẫn file Excel đều theo bộ lọc này. */}
        <label className="blt-date-label">Chủng loại
          <MultiSelect placeholder="Tất cả chủng loại" options={meta?.grades ?? []} width={220}
            value={grades} onChange={setGrades} />
        </label>
        <button className="btn" onClick={load} disabled={loading}>{loading ? "Đang tải…" : "Tải lại"}</button>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>{companies.length} đơn vị</span>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <ConsumptionKpiRow totals={totals} backlog={backlog} />

      <ConsumptionCompanyTable rep={rep} meta={meta} companies={companies} totals={totals}
        backlog={backlog} loading={loading} />

      {rep && <ConsumptionMasterProgress rep={rep} totals={backlog} />}

      {rep && <ConsumptionByCustomer rep={rep} />}

      <ConsumptionDeliveryHistory from={from} to={to} company={company || undefined}
        customerIds={customerIds} grades={grades} />

      <div className="form-note" style={{ fontSize: 11.5, marginTop: 10 }}>
        Doanh thu hiện “—” khi có lần giao bán bằng ngoại tệ mà chưa nhập tỷ giá — hệ thống không tự
        suy ra tỷ giá của ngày khác. Bổ sung tỷ giá trên đợt giao để có số đầy đủ.
      </div>
    </div>
  );
}
