import { ApartmentOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons";
import { Alert, App, Button, Input, Select } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { daysAgoISO, todayISO } from "../../../lib/date";
import {
  type DemandItem, type DemandItemInput, type DemandList, demandApi,
} from "../../../lib/market-demand-client";
import { cloneDemand, demandTitle, emptyDemand, toDemandInput } from "../../../lib/market-demand-meta";
import { GRADES } from "../../../lib/unit-daily-consumption";
import { DIRECT_SAVED_IN_REQUEST_MODE, useEditRequest } from "../../../lib/use-edit-request";
import { useAuth } from "../../auth/AuthContext";
import DemandItemFormModal, { type DemandFormMode } from "../sections/DemandItemFormModal";
import DemandItemTable, { type DemandRowPerm } from "../sections/DemandItemTable";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";

const RANGES = [30, 60, 90, 180, 365].map((d) => ({ value: d, label: `${d} ngày gần nhất` }));
const toOptions = (list: string[]) => list.map((x) => ({ value: x, label: x }));
const daysBetween = (later: string, earlier: string) =>
  Math.round((new Date(`${later}T00:00:00`).getTime() - new Date(`${earlier}T00:00:00`).getTime()) / 86400000);
const uniqDates = (...dates: (string | undefined)[]) => [...new Set(dates.filter((d): d is string => !!d))];

type FormState = { mode: DemandFormMode; initial: DemandItemInput; original: DemandItem | null; locked: boolean };

/** Nhu cầu thị trường — phiếu có trường, mỗi dòng một chủng loại, kết quả cập nhật về sau.
 *  Dùng chung cho tài khoản đơn vị (chỉ đơn vị được gán; lãnh đạo đơn vị chỉ xem) và chuyên viên
 *  có quyền `market_demand` (mọi đơn vị) — đổi nguồn dữ liệu theo loại tài khoản. */
export default function MarketDemandTimelinePage() {
  const { message } = App.useApp();
  const { user, canEditCap, isUnitAccount, canEditUnitData } = useAuth();
  const isAdmin = user?.role === "admin";
  const api = useMemo(() => demandApi(isUnitAccount), [isUnitAccount]);
  const { saveOrRequest, modal } = useEditRequest();

  const [days, setDays] = useState(90);
  const [company, setCompany] = useState<string>();
  const [grade, setGrade] = useState<string>();
  const [qText, setQText] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState<DemandList | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState<FormState | null>(null);
  const seq = useRef(0);   // bỏ kết quả của lần tải cũ về muộn hơn lần tải mới

  // Phía đơn vị server không nhận `company` → lọc đơn vị tại trình duyệt, không cần tải lại.
  const serverCompany = isUnitAccount ? undefined : company;
  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true); setErr("");
    try {
      const r = await api.fetch({ date_from: daysAgoISO(days), company: serverCompany, grade, q });
      if (mine === seq.current) setData(r);
    } catch (e) {
      if (mine === seq.current) setErr((e as Error).message);
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [api, days, serverCompany, grade, q]);
  useEffect(() => { void load(); }, [load]);

  // Chuyên viên chỉ được cấp mức Xem và lãnh đạo đơn vị: không có nút ghi nào.
  const mayEdit = canEditUnitData || canEditCap("market_demand");
  const today = data?.today ?? todayISO();
  const units = useMemo(() => data?.units ?? [], [data]);
  // Đơn vị đã SÁP NHẬP vào đơn vị của tài khoản: phiếu cũ vẫn hiện để tra cứu nhưng không ghi được.
  const viewOnly = useMemo(() => new Set(data?.view_only_units ?? []), [data]);
  const writableUnits = useMemo(() => units.filter((u) => !viewOnly.has(u)), [units, viewOnly]);
  const grades = data?.grades?.length ? data.grades : GRADES;
  const multiUnit = units.length > 1;
  const items = useMemo(() => {
    const all = data?.items ?? [];
    return isUnitAccount && company ? all.filter((i) => i.company === company) : all;
  }, [data, isUnitAccount, company]);
  const customers = useMemo(() => (data?.items ?? []).map((i) => i.customer), [data]);
  const places = useMemo(() => (data?.items ?? []).map((i) => i.delivery_place), [data]);

  // Cửa sổ sửa tính như màn cũ: admin luôn sửa được; còn lại trong N ngày gần nhất tính tới hôm nay.
  const inWindow = (asOf: string) => isAdmin
    || (!!data && asOf <= data.today && daysBetween(data.today, asOf) <= data.edit_window_days);
  const perm = (i: DemandItem): DemandRowPerm => {
    const own = mayEdit && !viewOnly.has(i.company);
    const open = inWindow(i.as_of);
    return {
      edit: own,                                   // ngoài cửa sổ: form chỉ mở ô theo dõi
      request: own && canEditUnitData && !open,
      clone: mayEdit && writableUnits.length > 0,
      remove: own && (open || canEditUnitData),    // đơn vị xoá quá hạn → thành đề nghị xoá
      locked: !open,
    };
  };

  const pickCompany = (preferred?: string) => {
    if (preferred && writableUnits.includes(preferred)) return preferred;
    if (company && writableUnits.includes(company)) return company;
    return writableUnits.length === 1 ? writableUnits[0] : "";
  };
  const openCreate = () =>
    setForm({ mode: "create", initial: emptyDemand(pickCompany(), today), original: null, locked: false });
  const openEdit = (i: DemandItem, request: boolean) => setForm({
    mode: request ? "request" : "edit", initial: toDemandInput(i), original: i, locked: !inWindow(i.as_of),
  });
  const openClone = (i: DemandItem) => setForm({
    mode: "create", initial: cloneDemand(i, pickCompany(i.company), today), original: null, locked: false,
  });

  // Server cho lưu thì lưu thẳng; tài khoản đơn vị bị cửa sổ sửa chặn thì popup gửi đề nghị với đúng thân PUT.
  const submit = async (v: DemandItemInput) => {
    if (!form) return;
    const result = await saveOrRequest(() => api.save(v), {
      op: "demand_save", payload: { ...v }, title: demandTitle(v), company: v.company,
      dates: uniqDates(form.original?.as_of, v.as_of),
    });
    if (result === "cancelled") return;   // đóng hộp đề nghị → giữ form để sửa tiếp
    setForm(null);
    if (result === "saved") {
      message.success(form.mode === "request" ? DIRECT_SAVED_IN_REQUEST_MODE : "Đã lưu nhu cầu.");
      void load();
    }
  };

  const remove = async (i: DemandItem) => {
    try {
      const result = await saveOrRequest(() => api.remove(i.id), {
        op: "demand_delete", payload: { id: i.id }, title: demandTitle(i, true),
        company: i.company, dates: [i.as_of],
      });
      if (result === "saved") {
        message.success("Đã xoá phiếu nhu cầu.");
        void load();
      }
    } catch (e) {
      message.error((e as Error).message);
    }
  };

  const applySearch = () => setQ(qText.trim());

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ApartmentOutlined style={{ marginRight: 8 }} />Nhu cầu thị trường</h2>
          <p>Ghi nhận các nhu cầu hỏi mua của khách hàng — mỗi dòng một chủng loại, ghi kết quả khi có.</p>
        </div>
      </div>
      {err && <Alert type="error" showIcon title={err} style={{ marginBottom: 12 }} />}

      <ReadOnlyNotice cap="market_demand" />

      <div className="card" style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginBottom: 14 }}>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>Khoảng thời gian:</span>
        <Select value={days} options={RANGES} style={{ width: 170 }} onChange={setDays} />
        {multiUnit && (
          <Select showSearch allowClear placeholder="Tất cả đơn vị" style={{ minWidth: 240 }}
            value={company} options={toOptions(units)} onChange={setCompany} />
        )}
        <Select showSearch allowClear placeholder="Mọi chủng loại" style={{ width: 200 }}
          value={grade} options={toOptions(grades)} onChange={setGrade} />
        <Input allowClear prefix={<SearchOutlined />} style={{ width: 280 }}
          placeholder="Tìm khách hàng, kết quả, ghi chú" value={qText}
          onChange={(e) => { setQText(e.target.value); if (!e.target.value) setQ(""); }}
          onPressEnter={applySearch} onBlur={applySearch} />
        {mayEdit && (
          <Button type="primary" icon={<PlusOutlined />} style={{ marginLeft: "auto" }}
            disabled={!data || writableUnits.length === 0} onClick={openCreate}>
            Thêm nhu cầu
          </Button>
        )}
      </div>

      <div className="card">
        <DemandItemTable items={items} loading={loading} showCompany={multiUnit} showActions={mayEdit}
          perm={perm} onEdit={openEdit} onClone={openClone} onDelete={(i) => { void remove(i); }} />
      </div>

      {form && data && (
        <DemandItemFormModal mode={form.mode} initial={form.initial} contentLocked={form.locked}
          units={writableUnits} grades={grades} customers={customers} places={places} today={data.today}
          onSubmit={submit} onCancel={() => setForm(null)} />
      )}
      {modal}
    </div>
  );
}
