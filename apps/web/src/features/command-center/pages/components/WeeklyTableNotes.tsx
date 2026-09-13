/* Ghi chú dưới bảng III.1 / III.2: phần TỰ ĐỘNG từ dữ liệu (sàn không có giá ngày nào — chỉ đọc)
   + ghi chú tay thêm (mỗi dòng 1 ghi chú). Cả hai in dưới bảng trong PDF. */

import { InfoCircleOutlined } from "@ant-design/icons";

import WeeklyListField from "./WeeklyListField";

type Props = {
  gaps: string[];
  fieldKey: "exchange_table_notes" | "physical_table_notes";
  notes: string[];
  placeholder: string;
  onChange: (v: string[]) => void;
};

export default function WeeklyTableNotes({ gaps, fieldKey, notes, placeholder, onChange }: Props) {
  return (
    <div className="wk-notes">
      <div className="wk-subtle-title"><InfoCircleOutlined /> Ghi chú (tự động từ dữ liệu)</div>
      {gaps?.length ? (
        <ul className="wk-gap-list">{gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
      ) : (
        <div className="wk-muted wk-gap-empty">Không có phiên thiếu giá trong kỳ.</div>
      )}
      <WeeklyListField fieldKey={fieldKey} label="Ghi chú thêm dưới bảng" items={notes}
        ai={false} checkWords={false} minHeight={48} placeholder={placeholder} onChange={onChange} />
    </div>
  );
}
