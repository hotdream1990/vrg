/* Thanh lọc dùng chung cho các màn Thống kê: kỳ (preset + tự chọn) · đơn vị · khu vực ·
   chủng loại · cách nhóm — cộng các ô đặc thù của từng màn truyền vào qua `extra`. */

import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Checkbox, Segmented, Select, Tooltip } from "antd";
import type { ReactNode } from "react";
import { useState } from "react";

import { PRESETS, type Preset, rangeOf } from "../../../../lib/date-presets";
import type { FilterCatalog, Opt, StatsFilters } from "../../../../lib/unit-analytics-client";
import DateInput from "../../sections/DateInput";

type Props = {
  catalog: FilterCatalog | null;
  value: StatsFilters;
  onChange: (f: StatsFilters) => void;
  groupOptions: Opt[];
  // Cách nhóm do drill-down quyết định → truyền từ ngoài vào thay vì lấy trong `value.groupBy`.
  groupValue?: string;
  onGroupChange?: (v: string) => void;
  showGrades?: boolean;
  extra?: ReactNode;
  onReload: () => void;
  onExport?: () => void;
  loading?: boolean;
  exporting?: boolean;
};

/** Ô chọn nhiều giá trị (đơn vị · khu vực · chủng loại…) — rỗng = không lọc. */
export function MultiSelect({ placeholder, options, value, onChange, width = 220 }: {
  placeholder: string; options: (string | Opt)[]; value: string[];
  onChange: (v: string[]) => void; width?: number;
}) {
  return (
    <Select
      mode="multiple" allowClear maxTagCount="responsive" style={{ minWidth: width }}
      placeholder={placeholder} value={value} onChange={onChange}
      options={options.map((o) => (typeof o === "string" ? { value: o, label: o } : o))}
    />
  );
}

/** Công tắc "Tách đơn vị đã sáp nhập" — KHÔNG hiện khi hệ thống chưa có đơn vị nào sáp nhập,
 *  để thanh lọc không phình thêm một ô mà đa số người dùng không bao giờ cần. */
export function SplitMergedToggle({ catalog, value, onChange }: {
  catalog: FilterCatalog | null; value: boolean; onChange: (v: boolean) => void;
}) {
  const merged = catalog?.merged_units ?? [];
  if (!merged.length) return null;
  const list = merged.map((m) => `${m.name} → ${m.merged_into}`).join(" · ");
  return (
    <Tooltip title={`Mặc định số liệu trước sáp nhập được cộng vào đơn vị hiện hành: ${list}`}>
      <Checkbox checked={value} onChange={(e) => onChange(e.target.checked)}>
        Tách đơn vị đã sáp nhập
      </Checkbox>
    </Tooltip>
  );
}

export default function AnalyticsFilters({
  catalog, value, onChange, groupOptions, groupValue, onGroupChange,
  showGrades, extra, onReload, onExport, loading, exporting,
}: Props) {
  const [preset, setPreset] = useState<Preset>("Tuần này");
  const patch = (p: Partial<StatsFilters>) => onChange({ ...value, ...p });

  const pickPreset = (p: Preset) => {
    setPreset(p);
    const r = rangeOf(p);
    if (r) onChange({ ...value, from: r.from, to: r.to });
  };

  // Chọn khu vực thì danh sách đơn vị thu hẹp theo khu vực đó (đỡ phải dò trong danh sách dài).
  const units = (catalog?.units ?? []).filter(
    (u) => !value.regions.length || value.regions.includes(u.region ?? ""));
  // Đang TÁCH thì đơn vị đã sáp nhập mới có dòng riêng để chọn.
  const unitNames = value.splitMerged
    ? [...units.map((u) => u.name), ...(catalog?.merged_units ?? []).map((m) => m.name)]
    : units.map((u) => u.name);

  return (
    <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <Segmented value={preset} onChange={(v) => pickPreset(v as Preset)} options={[...PRESETS]} />
      <DateInput value={value.from} onChange={(v) => { patch({ from: v }); setPreset("Tự chọn"); }} style={{ width: 160 }} />
      <span style={{ color: "var(--muted)" }}>→</span>
      <DateInput value={value.to} onChange={(v) => { patch({ to: v }); setPreset("Tự chọn"); }} style={{ width: 160 }} />
      <MultiSelect placeholder="Tất cả khu vực" options={catalog?.regions ?? []}
                   value={value.regions} onChange={(v) => patch({ regions: v })} width={190} />
      <MultiSelect placeholder="Tất cả đơn vị" options={unitNames}
                   value={value.companies} onChange={(v) => patch({ companies: v })} width={230} />
      {showGrades && (
        <MultiSelect placeholder="Tất cả chủng loại" options={catalog?.grades ?? []}
                     value={value.grades} onChange={(v) => patch({ grades: v })} width={210} />
      )}
      {extra}
      <SplitMergedToggle catalog={catalog} value={!!value.splitMerged}
                         onChange={(v) => patch({ splitMerged: v })} />
      <span style={{ color: "var(--muted)", fontSize: 13 }}>Nhóm theo</span>
      <Select style={{ width: 155 }} value={groupValue ?? value.groupBy} options={groupOptions}
              onChange={(v) => (onGroupChange ? onGroupChange(v) : patch({ groupBy: v }))} />
      <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>Làm mới</Button>
      {onExport && (
        <Button type="primary" icon={<DownloadOutlined />} onClick={onExport} loading={exporting}>
          Xuất Excel
        </Button>
      )}
    </div>
  );
}
