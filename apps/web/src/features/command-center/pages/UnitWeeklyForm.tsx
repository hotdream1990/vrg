/* Form nhập số liệu 1 đơn vị / 1 tuần / 1 loại biểu mẫu (thu mua | tiêu thụ–tồn kho).
   THỨ TỰ Ô GIỮ ĐÚNG NHƯ EXCEL; ô suy ra (chỉ đọc, nền mờ) nằm xen giữa đúng vị trí, tính realtime.
   Dùng chung: đơn vị thành viên nhập inline · chuyên viên sửa trong Modal. */

import { InputNumber } from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  type Column, INPUT_KEYS, type Kind, type Values, fmtNum, isDerived, segments,
} from "../../../lib/unit-weekly-fields";

type Props = {
  kind: Kind;
  values: Values;
  plan?: number | null;           // chỉ tiêu kế hoạch năm (tính % — chỉ thu mua)
  readOnly?: boolean;
  formKey: string;                // đổi khi đổi đơn vị/tuần/loại → reset nháp
  onDirty?: (dirty: boolean) => void;
  footer?: (dirty: boolean, current: Values) => React.ReactNode;
};

export default function UnitWeeklyForm({ kind, values, plan, readOnly, formKey, onDirty, footer }: Props) {
  const [draft, setDraft] = useState<Values>(values ?? {});
  useEffect(() => { setDraft(values ?? {}); }, [formKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = useMemo(
    () => INPUT_KEYS[kind].some((k) => (draft[k] ?? null) !== (values?.[k] ?? null)),
    [draft, values, kind],
  );
  useEffect(() => { onDirty?.(dirty); }, [dirty]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key: string, v: number | null) => setDraft((d) => ({ ...d, [key]: v ?? undefined }));

  const cell = (c: Column) => {
    const derived = isDerived(c);
    return (
      <label key={c.key} style={{ display: "block" }}>
        <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 2 }}>
          {c.label} <span style={{ opacity: 0.6 }}>({c.unit})</span>
          {c.hint && <div style={{ fontSize: 11, opacity: 0.55 }}>{c.hint}</div>}
        </div>
        {derived ? (
          <div style={{
            height: 32, lineHeight: "32px", padding: "0 11px", borderRadius: 6, textAlign: "right",
            background: "rgba(125,125,125,.12)", border: "1px dashed rgba(125,125,125,.35)", fontWeight: 600,
          }}>
            {fmtNum(c.compute!(draft, plan), c.unit === "%" ? 1 : 2)}
            <span style={{ fontSize: 10, opacity: 0.55, fontWeight: 400 }}> · tự tính</span>
          </div>
        ) : (
          <InputNumber
            value={draft[c.key] ?? null}
            onChange={(v) => set(c.key, v as number | null)}
            disabled={readOnly}
            controls={false}
            min={0}
            decimalSeparator=","
            style={{ width: "100%" }}
            placeholder="—"
          />
        )}
      </label>
    );
  };

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 10, alignItems: "end" }}>
        {segments(kind).map((seg, i) => (
          <div key={seg.group ?? seg.cols[0].key} style={{ display: "contents" }}>
            {seg.group && (
              <div style={{
                gridColumn: "1 / -1", fontWeight: 600, fontSize: 12.5, opacity: 0.85,
                marginTop: i ? 8 : 0, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)",
              }}>{seg.group}</div>
            )}
            {seg.cols.map(cell)}
          </div>
        ))}
      </div>
      {!readOnly && footer?.(dirty, draft)}
    </div>
  );
}
