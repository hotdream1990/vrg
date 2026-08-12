import { DatePicker } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { useState, type CSSProperties } from "react";

dayjs.extend(customParseFormat);   // cần cho dayjs(text, format, strict) khi tự đọc chuỗi gõ tay

type Props = {
  value: string;                       // YYYY-MM-DD ("" = trống)
  onChange?: (iso: string) => void;    // trả về YYYY-MM-DD ("" khi xoá)
  readOnly?: boolean;
  allowClear?: boolean;
  noFuture?: boolean;                  // chặn chọn ngày sau hôm nay
  minDate?: string;                    // YYYY-MM-DD — chặn ngày TRƯỚC mốc này
  maxDate?: string;                    // YYYY-MM-DD — chặn ngày SAU mốc này
  placeholder?: string;
  className?: string;
  style?: CSSProperties;
};

/** Phần tử ĐẦU là định dạng hiển thị; các phần tử sau chỉ dùng để hiểu chuỗi người dùng GÕ TAY,
 *  nhờ vậy gõ "5/8/2026", "05-08-2026", "05082026" hay "2026-08-05" đều ra đúng ngày.
 *  Cố ý KHÔNG nhận năm 2 chữ số ("5/8/26"): người dùng gõ dở "5/8/20" rồi rời ô sẽ thành 2020 —
 *  sai ngày mà không ai thấy. Gõ không khớp định dạng nào thì ô tự trả về giá trị cũ. */
const FORMATS = [
  "DD/MM/YYYY", "D/M/YYYY", "DD/M/YYYY", "D/MM/YYYY",
  "DD-MM-YYYY", "D-M-YYYY",
  "DD.MM.YYYY", "D.M.YYYY",
  "DDMMYYYY",
  "YYYY-MM-DD",
];
const DISPLAY = FORMATS[0];

const parseTyped = (text: string): Dayjs | null =>
  FORMATS.map((f) => dayjs(text, f, true)).find((d) => d.isValid()) ?? null;

/** Ô nhập ngày hiển thị CỐ ĐỊNH DD/MM/YYYY (thay <input type=date> vốn hiện theo locale trình
 *  duyệt), VỪA gõ tay được vừa chọn trên lịch. Giữ giao diện value/onChange dạng chuỗi YYYY-MM-DD
 *  như native input để dễ thay thế. */
export default function DateInput({
  value, onChange, readOnly, allowClear = false, noFuture = false,
  minDate, maxDate, placeholder = "dd/mm/yyyy", className, style,
}: Props) {
  const [seq, setSeq] = useState(0);   // đổi key = gắn lại ô, xoá chữ gõ dở/gõ sai còn nằm lại
  const display = value ? dayjs(value).format(DISPLAY) : "";

  const blocked = (d: Dayjs) =>
    (noFuture && d.isAfter(dayjs(), "day")) ||
    (!!minDate && d.isBefore(dayjs(minDate), "day")) ||
    (!!maxDate && d.isAfter(dayjs(maxDate), "day"));

  /** Rời ô mà chưa bấm Enter: antd chỉ chốt giá trị khi Enter hoặc chọn trên lịch, chữ vừa gõ sẽ
   *  nằm lại mà số liệu bên dưới vẫn của ngày cũ. Tự chốt ở đây cho khớp điều người dùng thấy. */
  const commitTyped = (text: string) => {
    const typed = text.trim();
    if (typed === display) return;
    const parsed = typed ? parseTyped(typed) : null;
    const rejected = typed ? !parsed || blocked(parsed) : !allowClear;
    if (!rejected) {
      const iso = parsed ? parsed.format("YYYY-MM-DD") : "";
      if (iso !== value) onChange?.(iso);
    }
    setSeq((n) => n + 1);   // gắn lại ô: hiển thị đúng chuẩn DD/MM/YYYY (hoặc trả về giá trị cũ)
  };

  return (
    <DatePicker
      key={seq}
      format={FORMATS}
      value={value ? dayjs(value) : null}
      onChange={(d) => onChange?.(d ? d.format("YYYY-MM-DD") : "")}
      onBlur={(e) => commitTyped((e.target as HTMLInputElement).value ?? "")}
      disabled={readOnly}
      allowClear={allowClear}
      disabledDate={noFuture ? (d) => d.isAfter(dayjs(), "day") : undefined}
      minDate={minDate ? dayjs(minDate) : undefined}
      maxDate={maxDate ? dayjs(maxDate) : undefined}
      placeholder={placeholder}
      className={className}
      style={style}
    />
  );
}
