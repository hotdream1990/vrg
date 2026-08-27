import { Modal, Select, Tooltip } from "antd";
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

/** Hệ quả của việc sáp nhập — bày ra TRƯỚC khi bấm, vì đây là thao tác đổi cách đọc số liệu. */
function Consequences({ from, into, at }: { from: string; into: string; at: string }) {
  return (
    <ul style={{ margin: "10px 0 0", paddingLeft: 18, fontSize: 12.5, lineHeight: 1.75 }}>
      <li>Số liệu <b>trước {dmy(at)}</b> vẫn đứng tên <b>{from}</b> — không mất, không chuyển đi đâu.</li>
      <li>Từ <b>{dmy(at)}</b>, <b>{from}</b> không nhận số liệu mới — nhập vào <b>{into}</b>.</li>
      <li>Tài khoản của <b>{from}</b> chuyển sang <b>{into}</b>.</li>
      <li>Báo cáo mặc định <b>gộp</b> số của <b>{from}</b> vào <b>{into}</b>.</li>
    </ul>
  );
}

/**
 * Ô "Sáp nhập" ở màn Đơn vị thành viên.
 *
 * Sáp nhập KHÔNG chuyển số liệu cũ sang đơn vị mới: bản ghi trước ngày hiệu lực vẫn đứng tên đơn
 * vị cũ, nhờ vậy vẫn tra được đơn vị đó làm được bao nhiêu khi chưa sáp nhập. Từ ngày hiệu lực,
 * đơn vị cũ không nhận số liệu mới và tài khoản của nó chuyển sang đơn vị mới.
 *
 * Form nằm trong CỬA SỔ RIÊNG chứ không nhét vào ô của bảng: tên đơn vị dài (“Công ty TNHH MTV
 * Cao su Chư Prông”) nên ô chọn trong bảng cắt cụt thành “Công ty TNHH …”, phải rê chuột mới đọc
 * được — chọn nhầm đơn vị nhận là hỏng số liệu của cả hai bên (phản hồi 27/08/2026).
 */
export default function UnitMergeCell({ unit, units, canEdit, run }: Props) {
  const [open, setOpen] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const [into, setInto] = useState<string | undefined>();
  const [at, setAt] = useState(new Date().toISOString().slice(0, 10));

  if (unit.merged_into) {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
        <Tooltip title={`Đã sáp nhập vào ${unit.merged_into}`}>
          <span className="chip info" style={{
            fontSize: 11, maxWidth: 190, overflow: "hidden",
            textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>→ {unit.merged_into}</span>
        </Tooltip>
        <span style={{ color: "var(--muted)", fontSize: 12, whiteSpace: "nowrap" }}>
          từ {dmy(unit.merged_at)}
        </span>
        {canEdit && <button className="btn" onClick={() => setUndoing(true)}>Gỡ</button>}
        {undoing && (
          <Modal open destroyOnHidden title={`Gỡ sáp nhập — ${unit.name}`}
            okText="Gỡ sáp nhập" cancelText="Đóng" okButtonProps={{ danger: true }}
            onCancel={() => setUndoing(false)}
            onOk={() => { setUndoing(false); run(() => unmergeUnit(unit.name)); }}>
            <div style={{ fontSize: 13, lineHeight: 1.75 }}>
              <b>{unit.name}</b> hoạt động độc lập trở lại và nhập liệu được như cũ.
              <div className="form-note" style={{ marginTop: 10, fontSize: 12.5 }}>
                Tài khoản đã chuyển sang <b>{unit.merged_into}</b> thì <b>không tự trả về</b> —
                cấp lại ở màn <b>Tài khoản</b>.
              </div>
            </div>
          </Modal>
        )}
      </div>
    );
  }
  if (!canEdit) return <span style={{ color: "var(--muted)" }}>—</span>;

  const submit = () => {
    if (!into || !at) return;
    setOpen(false);
    run(() => mergeUnit(unit.name, into, at));
  };

  return (
    <>
      <button className="btn" onClick={() => setOpen(true)}>Sáp nhập…</button>
      {open && (
        <Modal open destroyOnHidden width="min(620px, 94vw)"
          title={`Sáp nhập đơn vị — ${unit.name}`}
          okText="Sáp nhập" cancelText="Huỷ"
          okButtonProps={{ danger: true, disabled: !into || !at }}
          onCancel={() => { setOpen(false); setInto(undefined); }} onOk={submit}>
          <label className="form-field">Sáp nhập vào đơn vị
            <Select showSearch style={{ width: "100%" }} placeholder="Chọn đơn vị nhận…"
              value={into} onChange={setInto}
              options={units
                .filter((o) => o.name !== unit.name && o.is_active && !o.merged_into)
                .map((o) => ({ value: o.name, label: o.name }))}
              filterOption={(i, o) => (o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
          </label>
          <label className="form-field" style={{ marginTop: 12, alignItems: "start" }}>Ngày hiệu lực
            <DateInput value={at} onChange={setAt} style={{ width: 180 }} />
          </label>
          {into && <Consequences from={unit.name} into={into} at={at} />}
        </Modal>
      )}
    </>
  );
}
