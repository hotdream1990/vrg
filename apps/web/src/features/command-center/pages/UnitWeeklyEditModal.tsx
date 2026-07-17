/* Modal nhập/sửa số liệu 1 đơn vị / 1 tuần — DÙNG CHUNG cho timeline (danh sách theo tuần) và
   trang tổng hợp. Chọn tuần + đơn vị → nạp số đã có (nếu có) → sửa → lưu (upsert). Role-aware. */

import { Alert, Modal, Select, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type WeekData, fetchMyWeek, fetchWeek, saveMyWeekly, saveWeekly,
} from "../../../lib/unit-weekly-client";
import { KIND_LABEL, type Kind, type Values } from "../../../lib/unit-weekly-fields";
import { recentWeeks, weekLabel, weekRange } from "../../../lib/week";
import { todayISO } from "../../../lib/date";
import UnitWeeklyForm from "./UnitWeeklyForm";

const daysBetween = (a: string, b: string) =>
  Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000);

type Props = {
  open: boolean;
  kind: Kind;
  role: "member" | "hq";
  isAdmin: boolean;
  initialWeek: string;
  initialCompany: string;
  todayWeek: string;
  onClose: () => void;
  onSaved: () => void;
};

export default function UnitWeeklyEditModal(
  { open, kind, role, isAdmin, initialWeek, initialCompany, todayWeek, onClose, onSaved }: Props,
) {
  const [week, setWeek] = useState(initialWeek);
  const [company, setCompany] = useState(initialCompany);
  const [data, setData] = useState<WeekData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) { setWeek(initialWeek); setCompany(initialCompany); } }, [open, initialWeek, initialCompany]);

  const load = useCallback((wk: string) => {
    setLoading(true);
    (role === "member" ? fetchMyWeek : fetchWeek)(kind, wk)
      .then((d) => { setData(d); setCompany((c) => (c && d.units.includes(c) ? c : d.units[0] ?? "")); })
      .catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [role, kind]);
  useEffect(() => { if (open) load(week); }, [open, week, load]);

  const units = data?.units ?? [];

  const entry = data?.entries[company] ?? null;
  const exists = !!entry;
  const editable = useMemo(() => {
    if (isAdmin) return week <= todayWeek;
    if (week > todayWeek) return false;
    return daysBetween(weekRange(week).end, week === todayWeek ? weekRange(week).end : todayISO())
      <= (data?.edit_window_days ?? 7);
  }, [isAdmin, week, todayWeek, data]);

  const save = async (fields: Values) => {
    setSaving(true);
    try {
      await (role === "member" ? saveMyWeekly : saveWeekly)(kind, company, week, fields);
      message.success("Đã lưu số liệu tuần");
      onSaved();
      onClose();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const weekOpts = recentWeeks(todayWeek, 20).map((w) => ({ value: w, label: weekLabel(w) }));

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={880} destroyOnHidden
           title={`Nhập số liệu — ${KIND_LABEL[kind]}`}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <Select value={week} onChange={setWeek} options={weekOpts} style={{ width: 230 }} />
        <Select value={company} onChange={setCompany} showSearch style={{ minWidth: 220 }}
                options={units.map((u) => ({ value: u, label: u }))}
                filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        {exists
          ? <Tag color="blue">Đang sửa số đã có</Tag>
          : <Tag color="green">Tạo mới cho tuần này</Tag>}
      </div>
      {!editable && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message="Tuần này ở chế độ chỉ xem — ngoài cửa sổ nhập cho phép." />
      )}
      <Spin spinning={loading}>
        {data && (
          <UnitWeeklyForm
            kind={kind}
            formKey={`${kind}|${week}|${company}|${entry?.updated_at ?? "new"}`}
            values={entry?.fields ?? {}}
            plan={data.plans[company] ?? null}
            readOnly={!editable}
            footer={(dirty, current) => (
              <div style={{ marginTop: 14, textAlign: "right" }}>
                <button className="btn btn-primary" disabled={!dirty || saving}
                        onClick={() => save(current)}>
                  {saving ? "Đang lưu…" : "Lưu số liệu"}
                </button>
              </div>
            )}
          />
        )}
      </Spin>
    </Modal>
  );
}
