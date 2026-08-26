/* Thanh lọc màn Thống kê tồn kho — trục NGÀY CHỐT (số thời điểm), khác các màn kia dùng khoảng kỳ.
   Ô "xem lại N ngày" CHỈ hiện khi nhóm theo NGÀY (xem diễn biến). Từ 21/08/2026 không còn ô "số
   ngày được phép lùi": số của một đơn vị chỉ được giữ sang ngày sau khi chính họ tick "không phát
   sinh tồn kho để khai" — xem `unit_report_rows.stock_rows`. */

import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Select } from "antd";

import { isoDate } from "../../../../lib/date";
import type { FilterCatalog, Opt, StockFilters as Filters } from "../../../../lib/unit-analytics-client";
import DateInput from "../../sections/DateInput";
import { MultiSelect, SplitMergedToggle } from "./AnalyticsFilters";

/** Chỉ dùng khi nhóm theo NGÀY: xem diễn biến tồn mấy ngày trở lại ngày chốt. */
export const DAYS_BACK_OPTIONS: Opt[] = [
  { value: "0", label: "Chỉ ngày chốt" },
  { value: "7", label: "Xem lại 7 ngày" },
  { value: "14", label: "Xem lại 14 ngày" },
  { value: "30", label: "Xem lại 30 ngày" },
];

export const DEFAULT_DAYS_BACK = 7;

export const initialStockFilters = (): Filters => ({
  asOf: isoDate(new Date()), daysBack: DEFAULT_DAYS_BACK,
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
  const unitNames = value.splitMerged
    ? [...units.map((u) => u.name), ...(catalog?.merged_units ?? []).map((m) => m.name)]
    : units.map((u) => u.name);

  return (
    <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      <span style={{ color: "var(--muted)", fontSize: 13 }}>Ngày chốt</span>
      <DateInput value={value.asOf} onChange={(v) => patch({ asOf: v })} style={{ width: 160 }} />
      {groupValue === "day" && (
        <Select style={{ width: 165 }} value={String(value.daysBack)} options={DAYS_BACK_OPTIONS}
                onChange={(v) => patch({ daysBack: Number(v) })} />
      )}
      <MultiSelect placeholder="Tất cả khu vực" options={catalog?.regions ?? []}
                   value={value.regions} onChange={(v) => patch({ regions: v })} width={190} />
      <MultiSelect placeholder="Tất cả đơn vị" options={unitNames}
                   value={value.companies} onChange={(v) => patch({ companies: v })} width={230} />
      <MultiSelect placeholder="Tất cả chủng loại" options={catalog?.grades ?? []}
                   value={value.grades} onChange={(v) => patch({ grades: v })} width={210} />
      <SplitMergedToggle catalog={catalog} value={!!value.splitMerged}
                         onChange={(v) => patch({ splitMerged: v })} />
      <span style={{ color: "var(--muted)", fontSize: 13 }}>Nhóm theo</span>
      <Select style={{ width: 155 }} value={groupValue} options={groupOptions} onChange={onGroupChange} />
      <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>Làm mới</Button>
      <Button type="primary" icon={<DownloadOutlined />} onClick={onExport} loading={exporting}>
        Xuất Excel
      </Button>
    </div>
  );
}
