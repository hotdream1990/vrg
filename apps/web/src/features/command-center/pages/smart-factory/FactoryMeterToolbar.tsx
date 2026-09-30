/* Thanh công cụ màn Chỉ số điện · nước · số bành: nhà máy · kỳ xem · Tải lại · Xuất Excel.
   Chỉ 1 nhà máy thì hiện tên (khỏi bắt chọn); lịch chặn ngày tương lai + kỳ quá MAX_DAYS ngày,
   preset tính lại mỗi lần mở. */

import { BankOutlined, FileExcelOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, DatePicker, Select } from "antd";

import type { FactoryBrief } from "../../../../lib/smart-factory-client";
import { disabledRangeDate, RANGE_PRESETS, type Range } from "./smart-factory-format";

const { RangePicker } = DatePicker;

type Props = {
  factories: FactoryBrief[];
  factoryId: number | null;
  onFactory: (id: number) => void;
  range: Range;
  onRange: (r: Range) => void;
  onReload: () => void;
  onExport: () => void;
  loading: boolean;
  exporting: boolean;
  canExport: boolean;
};

export default function FactoryMeterToolbar({
  factories, factoryId, onFactory, range, onRange, onReload, onExport, loading, exporting, canExport,
}: Props) {
  return (
    <div className="card sf-toolbar">
      {factories.length === 1 ? (
        <span className="sf-factory-name"><BankOutlined /> {factories[0].name}</span>
      ) : (
        <Select
          style={{ minWidth: 240 }} value={factoryId ?? undefined} placeholder="Chọn nhà máy"
          onChange={onFactory}
          options={factories.map((f) => ({ value: f.id, label: f.name }))}
        />
      )}
      <RangePicker
        format="DD/MM/YYYY" allowClear={false} value={range}
        placeholder={["Từ ngày", "Đến ngày"]}
        disabledDate={disabledRangeDate} presets={RANGE_PRESETS}
        onChange={(v) => { if (v?.[0] && v[1]) onRange([v[0], v[1]]); }}
      />
      <span className="sf-toolbar-end">
        <Button icon={<ReloadOutlined />} loading={loading} disabled={factoryId == null} onClick={onReload}>
          Tải lại
        </Button>
        <Button icon={<FileExcelOutlined />} loading={exporting} disabled={!canExport} onClick={onExport}>
          Xuất Excel
        </Button>
      </span>
    </div>
  );
}
