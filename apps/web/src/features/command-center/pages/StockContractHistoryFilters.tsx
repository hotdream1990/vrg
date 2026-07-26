/* Bộ lọc màn Thống kê hợp đồng: đơn vị · khu vực · chủng loại · trạng thái · khoảng ngày · tìm kiếm. */

import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Input, Segmented, Select } from "antd";

import type { ContractHistoryFilters, ContractStatus } from "../../../lib/unit-daily-client";
import DateInput from "../sections/DateInput";
import { MultiSelect } from "./analytics/AnalyticsFilters";

const STATUS_OPTS: { label: string; value: ContractStatus }[] = [
  { label: "Tất cả", value: "all" },
  { label: "Chưa giao", value: "undelivered" },
  { label: "Đã giao", value: "delivered" },
];

type Props = {
  units: string[];
  regions?: string[];           // danh mục khu vực (chỉ chuyên viên/admin mới lọc theo khu vực)
  grades?: string[];            // danh mục chủng loại
  showCompany: boolean;         // ẩn ô đơn vị khi tài khoản chỉ gán 1 đơn vị
  value: ContractHistoryFilters;
  onChange: (f: ContractHistoryFilters) => void;
  onReload: () => void;
  loading?: boolean;
};

export default function StockContractHistoryFilters({
  units, regions, grades, showCompany, value, onChange, onReload, loading,
}: Props) {
  const patch = (p: Partial<ContractHistoryFilters>) => onChange({ ...value, ...p });

  return (
    <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
      {!!regions?.length && (
        <MultiSelect placeholder="Tất cả khu vực" options={regions} width={185}
                     value={value.regions ?? []} onChange={(v) => patch({ regions: v })} />
      )}
      {showCompany && (
        <Select
          allowClear placeholder="Tất cả đơn vị" style={{ width: 220 }}
          value={value.company || undefined}
          onChange={(v) => patch({ company: v })}
          options={units.map((u) => ({ value: u, label: u }))}
        />
      )}
      {!!grades?.length && (
        <MultiSelect placeholder="Tất cả chủng loại" options={grades} width={200}
                     value={value.grades ?? []} onChange={(v) => patch({ grades: v })} />
      )}
      <Segmented value={value.status ?? "all"} onChange={(v) => patch({ status: v as ContractStatus })}
        options={STATUS_OPTS} />
      <DateInput value={value.dateFrom ?? ""} onChange={(v) => patch({ dateFrom: v || undefined })}
        allowClear style={{ width: 160 }} />
      <span style={{ color: "var(--muted)" }}>→</span>
      <DateInput value={value.dateTo ?? ""} onChange={(v) => patch({ dateTo: v || undefined })}
        allowClear style={{ width: 160 }} />
      <Input
        prefix={<SearchOutlined />} placeholder="Số HĐ/PL hoặc chủng loại" allowClear
        style={{ width: 220 }} value={value.q ?? ""}
        onChange={(e) => patch({ q: e.target.value || undefined })}
      />
      <Button icon={<ReloadOutlined />} onClick={onReload} loading={loading}>Làm mới</Button>
    </div>
  );
}
