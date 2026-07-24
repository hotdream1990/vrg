/* Bộ lọc màn Lịch sử hợp đồng tồn kho: đơn vị · trạng thái · khoảng ngày · tìm kiếm. */

import { ReloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Input, Segmented, Select } from "antd";

import type { ContractHistoryFilters, ContractStatus } from "../../../lib/unit-daily-client";
import DateInput from "../sections/DateInput";

const STATUS_OPTS: { label: string; value: ContractStatus }[] = [
  { label: "Tất cả", value: "all" },
  { label: "Chưa giao", value: "undelivered" },
  { label: "Đã giao", value: "delivered" },
];

type Props = {
  units: string[];
  showCompany: boolean;         // ẩn ô đơn vị khi tài khoản chỉ gán 1 đơn vị
  value: ContractHistoryFilters;
  onChange: (f: ContractHistoryFilters) => void;
  onReload: () => void;
  loading?: boolean;
};

export default function StockContractHistoryFilters({ units, showCompany, value, onChange, onReload, loading }: Props) {
  const patch = (p: Partial<ContractHistoryFilters>) => onChange({ ...value, ...p });

  return (
    <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
      {showCompany && (
        <Select
          allowClear placeholder="Tất cả đơn vị" style={{ width: 220 }}
          value={value.company || undefined}
          onChange={(v) => patch({ company: v })}
          options={units.map((u) => ({ value: u, label: u }))}
        />
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
