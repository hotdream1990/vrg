/* Modal nhập/sửa số liệu 1 đơn vị / 1 ngày — DÙNG CHUNG cho timeline (danh sách theo ngày) và
   trang tổng hợp. Chọn ngày + đơn vị → nạp số đã có (nếu có) → sửa → lưu (upsert). Role-aware. */

import { Alert, Modal, Select, Spin, Tag, message } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  type DayData, fetchMyDay, fetchDay, saveMyDaily, saveDaily,
} from "../../../lib/unit-daily-client";
import { KIND_LABEL, type Kind, type Values } from "../../../lib/unit-daily-fields";
import DateInput from "../sections/DateInput";
import UnitDailyForm from "./UnitDailyForm";

const daysBetween = (later: string, earlier: string) =>
  Math.round((new Date(later + "T00:00:00").getTime() - new Date(earlier + "T00:00:00").getTime()) / 86_400_000);

type Props = {
  open: boolean;
  kind: Kind;
  role: "member" | "hq";
  isAdmin: boolean;
  initialDay: string;
  initialCompany: string;
  today: string;
  onClose: () => void;
  onSaved: () => void;
};

export default function UnitDailyEditModal(
  { open, kind, role, isAdmin, initialDay, initialCompany, today, onClose, onSaved }: Props,
) {
  const [day, setDay] = useState(initialDay);
  const [company, setCompany] = useState(initialCompany);
  const [data, setData] = useState<DayData | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) { setDay(initialDay); setCompany(initialCompany); } }, [open, initialDay, initialCompany]);

  const load = useCallback((asOf: string) => {
    setLoading(true);
    (role === "member" ? fetchMyDay : fetchDay)(kind, asOf)
      .then((d) => { setData(d); setCompany((c) => (c && d.units.includes(c) ? c : d.units[0] ?? "")); })
      .catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [role, kind]);
  useEffect(() => { if (open && day) load(day); }, [open, day, load]);

  const units = data?.units ?? [];

  const entry = data?.entries[company] ?? null;
  const exists = !!entry;
  const editable = useMemo(() => {
    if (!day || day > today) return false;
    if (isAdmin) return true;
    return daysBetween(today, day) <= (data?.edit_window_days ?? 7);
  }, [isAdmin, day, today, data]);

  const save = async (fields: Values) => {
    setSaving(true);
    try {
      await (role === "member" ? saveMyDaily : saveDaily)(kind, company, day, fields);
      message.success("Đã lưu số liệu ngày");
      onSaved();
      onClose();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onCancel={onClose} footer={null} width={880} destroyOnHidden
           title={`Nhập số liệu — ${KIND_LABEL[kind]}`}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
        <DateInput value={day} onChange={setDay} noFuture style={{ width: 190 }} />
        <Select value={company} onChange={setCompany} showSearch style={{ minWidth: 220 }}
                options={units.map((u) => ({ value: u, label: u }))}
                filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        {exists
          ? <Tag color="blue">Đang sửa số đã có</Tag>
          : <Tag color="green">Tạo mới cho ngày này</Tag>}
      </div>
      {!editable && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message="Ngày này ở chế độ chỉ xem — ngoài cửa sổ nhập cho phép." />
      )}
      <Spin spinning={loading}>
        {data && (
          <UnitDailyForm
            kind={kind}
            formKey={`${kind}|${day}|${company}|${entry?.updated_at ?? "new"}`}
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
