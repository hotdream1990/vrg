/* Thanh chọn của Dashboard đơn vị: phạm vi · kỳ · ngày chốt tồn kho · tải lại.
   Tài khoản đơn vị (mode="unit") chỉ chọn trong các đơn vị được gán — gán 1 đơn vị thì ẩn hẳn ô
   chọn phạm vi (server vẫn ép phạm vi, ô này chỉ là tiện lợi). */

import { ReloadOutlined } from "@ant-design/icons";
import { Button, Segmented, Select, Tooltip } from "antd";

import type { DashScope, ScopeCatalog } from "../../../../lib/unit-dashboard-client";
import DateInput from "../../sections/DateInput";
import {
  DASH_PRESETS, type DashFilters, type DashPreset, presetRange, switchScope,
} from "./dashboard-filters";

type Props = {
  catalog: ScopeCatalog;
  value: DashFilters;
  onChange: (f: DashFilters) => void;
  onReload: () => void;
  loading: boolean;
};

const SCOPE_OPTIONS: { value: DashScope; label: string }[] = [
  { value: "group", label: "Toàn Tập đoàn" },
  { value: "region", label: "Khu vực" },
  { value: "unit", label: "Đơn vị" },
];

const NO_REGION = "Chưa gán khu vực";

/** Danh sách đơn vị nhóm theo khu vực (Select có nhóm) — giữ thứ tự server trả. */
function unitOptions(units: ScopeCatalog["units"]) {
  const groups = new Map<string, { value: string; label: string }[]>();
  for (const u of units) {
    const g = u.region ?? NO_REGION;
    groups.set(g, [...(groups.get(g) ?? []), { value: u.name, label: u.name }]);
  }
  return [...groups].map(([label, options]) => ({ label, title: label, options }));
}

/** Tìm không dấu: gõ "tay nguyen" vẫn ra "Tây Nguyên". */
const fold = (s: string) =>
  s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/gi, "d").toLowerCase();

const searchable = {
  showSearch: {
    filterOption: (input: string, opt?: { label?: unknown }) =>
      fold(String(opt?.label ?? "")).includes(fold(input)),
  },
};

export default function DashboardFilterBar({ catalog, value, onChange, onReload, loading }: Props) {
  const patch = (p: Partial<DashFilters>) => onChange({ ...value, ...p });

  // Đổi kỳ thì ngày chốt tồn kho về "tự động" (cuối kỳ mới) — giữ ngày chốt cũ dễ xem tồn của một
  // ngày nằm ngoài kỳ mà không để ý.
  const pickPreset = (p: DashPreset) => {
    const r = presetRange(p, catalog.today);
    patch(r ? { preset: p, from: r.from, to: r.to, asOf: "" } : { preset: p });
  };

  const groupMode = catalog.mode === "group";
  const showUnitSelect = groupMode ? value.scope === "unit" : catalog.units.length > 1;

  return (
    <div className="card ud-filter">
      {groupMode && (
        <Segmented value={value.scope} options={SCOPE_OPTIONS}
                   onChange={(v) => onChange(switchScope(catalog, value, v as DashScope))} />
      )}
      {groupMode && value.scope === "region" && (
        <Select
          {...searchable} style={{ minWidth: 220 }} value={value.key ?? undefined}
          placeholder="Chọn khu vực" onChange={(v: string) => patch({ key: v })}
          options={catalog.regions.map((r) => ({ value: r.name, label: `${r.name} (${r.units} đơn vị)` }))}
        />
      )}
      {showUnitSelect && (
        <Select
          {...searchable} style={{ minWidth: 260 }} value={value.key ?? undefined}
          placeholder="Chọn đơn vị" onChange={(v: string) => patch({ scope: "unit", key: v })}
          options={groupMode ? unitOptions(catalog.units)
                             : catalog.units.map((u) => ({ value: u.name, label: u.name }))}
        />
      )}

      <span className="ud-filter-gap" />

      <Segmented value={value.preset} options={[...DASH_PRESETS]}
                 onChange={(v) => pickPreset(v as DashPreset)} />
      <DateInput value={value.from} style={{ width: 140 }}
                 onChange={(v) => patch({ from: v, preset: "Tự chọn", asOf: "" })} />
      <span className="ud-muted">→</span>
      <DateInput value={value.to} style={{ width: 140 }}
                 onChange={(v) => patch({ to: v, preset: "Tự chọn", asOf: "" })} />

      <Tooltip title="Tồn kho là số THỜI ĐIỂM. Để trống = tự lấy ngày cuối kỳ (không quá hôm nay).">
        <span className="ud-inline">
          <b className="ud-inline-label">Chốt tồn kho</b>
          <DateInput value={value.asOf} allowClear placeholder="Tự động" style={{ width: 140 }}
                     onChange={(v) => patch({ asOf: v })} />
        </span>
      </Tooltip>

      <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>Tải lại</Button>
    </div>
  );
}
