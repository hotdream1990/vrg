import { DatePicker } from "antd";
import dayjs from "dayjs";
import type { CSSProperties } from "react";

type Props = {
  value: string;                       // YYYY-MM-DD ("" = trống)
  onChange?: (iso: string) => void;    // trả về YYYY-MM-DD ("" khi xoá)
  readOnly?: boolean;
  allowClear?: boolean;
  noFuture?: boolean;                  // chặn chọn ngày sau hôm nay
  className?: string;
  style?: CSSProperties;
};

/** Ô nhập ngày hiển thị CỐ ĐỊNH DD/MM/YYYY (thay <input type=date> vốn hiện theo locale trình
 *  duyệt). Giữ giao diện value/onChange dạng chuỗi YYYY-MM-DD như native input để dễ thay thế. */
export default function DateInput({
  value, onChange, readOnly, allowClear = false, noFuture = false, className, style,
}: Props) {
  return (
    <DatePicker
      format="DD/MM/YYYY"
      value={value ? dayjs(value) : null}
      onChange={(d) => onChange?.(d ? d.format("YYYY-MM-DD") : "")}
      disabled={readOnly}
      allowClear={allowClear}
      disabledDate={noFuture ? (d) => d.isAfter(dayjs(), "day") : undefined}
      inputReadOnly
      className={className}
      style={style}
    />
  );
}
