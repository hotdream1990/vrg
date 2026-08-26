import { Select } from "antd";
import { useState } from "react";

import { type MemberUnit, mergeUnit, unmergeUnit } from "../../../../lib/member-unit-client";
import DateInput from "../../sections/DateInput";

const dmy = (iso: string | null) =>
  iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "";

type Props = {
  unit: MemberUnit;
  units: MemberUnit[];                                   // để chọn đơn vị nhận
  canEdit: boolean;
  run: (fn: () => Promise<MemberUnit[]>) => void;         // chạy lệnh + nạp lại danh sách
};

/**
 * Ô "Sáp nhập" ở màn Đơn vị thành viên.
 *
 * Sáp nhập KHÔNG chuyển số liệu cũ sang đơn vị mới: bản ghi trước ngày hiệu lực vẫn đứng tên đơn
 * vị cũ, nhờ vậy vẫn tra được đơn vị đó làm được bao nhiêu khi chưa sáp nhập. Từ ngày hiệu lực,
 * đơn vị cũ không nhận số liệu mới và tài khoản của nó chuyển sang đơn vị mới.
 */
export default function UnitMergeCell({ unit, units, canEdit, run }: Props) {
  const [open, setOpen] = useState(false);
  const [into, setInto] = useState<string | undefined>();
  const [at, setAt] = useState(new Date().toISOString().slice(0, 10));

  if (unit.merged_into) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span className="chip info" style={{ fontSize: 11, whiteSpace: "nowrap" }}>→ {unit.merged_into}</span>
        <span style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap" }}>từ {dmy(unit.merged_at)}</span>
        {canEdit && (
          <button className="btn" onClick={() => {
            if (confirm(`Gỡ sáp nhập cho "${unit.name}"?\n\n`
              + "Đơn vị hoạt động độc lập trở lại và nhập liệu được như cũ. "
              + "Tài khoản đã chuyển sang đơn vị mới thì KHÔNG tự trả về — cấp lại ở màn Tài khoản."))
              run(() => unmergeUnit(unit.name));
          }}>Gỡ</button>
        )}
      </div>
    );
  }
  if (!canEdit) return <span style={{ color: "var(--muted)" }}>—</span>;

  if (!open) return <button className="btn" onClick={() => setOpen(true)}>Sáp nhập…</button>;

  const submit = () => {
    if (!into || !at) return;
    if (!confirm(`Sáp nhập "${unit.name}" vào "${into}" từ ngày ${dmy(at)}?\n\n`
      + `• Số liệu TRƯỚC ${dmy(at)} vẫn đứng tên "${unit.name}" (không mất, không chuyển đi đâu).\n`
      + `• Từ ${dmy(at)}, "${unit.name}" không nhận số liệu mới — nhập vào "${into}".\n`
      + `• Tài khoản của "${unit.name}" chuyển sang "${into}".\n`
      + `• Báo cáo mặc định gộp số của "${unit.name}" vào "${into}".`)) return;
    setOpen(false);
    run(() => mergeUnit(unit.name, into, at));
  };

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
      <Select showSearch size="small" style={{ minWidth: 150 }} placeholder="Sáp nhập vào…"
        value={into}
        options={units
          .filter((o) => o.name !== unit.name && o.is_active && !o.merged_into)
          .map((o) => ({ value: o.name, label: o.name }))}
        filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())}
        onChange={setInto} />
      <DateInput value={at} onChange={setAt} style={{ width: 130 }} />
      <button className="btn btn-primary" onClick={submit} disabled={!into || !at}>Lưu</button>
      <button className="btn" onClick={() => { setOpen(false); setInto(undefined); }}>Huỷ</button>
    </div>
  );
}
