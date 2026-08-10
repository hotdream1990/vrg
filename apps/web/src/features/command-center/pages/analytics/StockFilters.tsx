/* Thanh lọc màn Thống kê tồn kho — trục NGÀY CHỐT (số thời điểm), khác các màn kia dùng khoảng kỳ.
   "Số cũ tối đa" = đơn vị chưa nhập đúng ngày chốt thì được lùi tối đa mấy ngày; quá thì coi như
   thiếu số (thà báo thiếu còn hơn lấy số quá cũ đắp cho ngày chốt). */

import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Select } from "antd";

import { isoDate } from "../../../../lib/date";
import type { FilterCatalog, Opt, StockFilters as Filters } from "../../../../lib/unit-analytics-client";
import DateInput from "../../sections/DateInput";
import { MultiSelect } from "./AnalyticsFilters";

/** Mức lùi cho phép — 7 ngày là mặc định (đơn vị nhập gần như hằng ngày, cuối tuần thường trống). */
export const AGE_OPTIONS: Opt[] = [
  { value: "0", label: "Chỉ đúng ngày chốt" },
  { value: "3", label: "Số cũ tối đa 3 ngày" },
  { value: "7", label: "Số cũ tối đa 7 ngày" },
  { value: "14", label: "Số cũ tối đa 14 ngày" },
  { value: "30", label: "Số cũ tối đa 30 ngày" },
];

export const DEFAULT_MAX_AGE_DAYS = 7;

export const initialStockFilters = (): Filters => ({
  asOf: isoDate(new Date()), maxAgeDays: DEFAULT_MAX_AGE_DAYS,
  companies: [], regions: [], grades: [], groupBy: "region",
});

type Props = {
  catalog: FilterCatalog | null;
  value: Filters;
  onChange: (f: Filters) => void;
  groupOptions: Opt[];
  groupValue: string;
  onGroupChange: (v: string) => void;
  onReload: () => void;
  onExport: () => void;
  loading?: boolean;
  exporting?: boolean;
};

export default function StockFilters({
  catalog, value, onChange, groupOptions, groupValue, onGroupChange,
  onReload, onExport, loading, exporting,
}: Props) {
  const patch = (p: Partial<Filters>) => onChange({ ...value, ...p });
  const units = (catalog?.units ?? []).filter(
    (u) => !value.regions.length || value.regions.includes(u.region ?? ""));

  return (
    <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <span style={{ color: "var(--muted)", fontSize: 13 }}>Ngày chốt</span>
      <DateInput value={value.asOf} onChange={(v) => patch({ asOf: v })} style={{ width: 160 }} />
      <Select style={{ width: 195 }} value={String(value.maxAgeDays)} options={AGE_OPTIONS}
              onChange={(v) => patch({ maxAgeDays: Number(v) })} />
      <MultiSelect placeholder="Tất cả khu vực" options={catalog?.regions ?? []}
                   value={value.regions} onChange={(v) => patch({ regions: v })} width={190} />
      <MultiSelect placeholder="Tất cả đơn vị" options={units.map((u) => u.name)}
                   value={value.companies} onChange={(v) => patch({ companies: v })} width={230} />
      <MultiSelect placeholder="Tất cả chủng loại" options={catalog?.grades ?? []}
                   value={value.grades} onChange={(v) => patch({ grades: v })} width={210} />
      <span style={{ color: "var(--muted)", fontSize: 13 }}>Nhóm theo</span>
      <Select style={{ width: 155 }} value={groupValue} options={groupOptions} onChange={onGroupChange} />
      <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>Làm mới</Button>
      <Button type="primary" icon={<DownloadOutlined />} onClick={onExport} loading={exporting}>
        Xuất Excel
      </Button>
    </div>
  );
}
