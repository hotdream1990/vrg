import { DatePicker } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import customParseFormat from "dayjs/plugin/customParseFormat";
import { useRef, useState, type CSSProperties } from "react";

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

/** Máy tính bảng / điện thoại (con trỏ chính là ngón tay). Ở đó CHẠM vào ô sẽ bật bàn phím ảo,
 *  bàn phím che mất lịch và đẩy khung trượt đi → người dùng thấy "bấm mà không chọn được ngày".
 *  Nên trên thiết bị chạm khoá gõ tay, chạm = mở lịch (đúng như trước khi mở gõ tay); máy tính
 *  con trỏ chuột vẫn gõ được bình thường. Tính 1 lần lúc nạp trang — loại thiết bị không đổi. */
const TOUCH_DEVICE = typeof window !== "undefined"
  && typeof window.matchMedia === "function"
  && window.matchMedia("(pointer: coarse)").matches;

/** Ô nhập ngày hiển thị CỐ ĐỊNH DD/MM/YYYY (thay <input type=date> vốn hiện theo locale trình
 *  duyệt), VỪA gõ tay được vừa chọn trên lịch. Giữ giao diện value/onChange dạng chuỗi YYYY-MM-DD
 *  như native input để dễ thay thế. */
export default function DateInput({
  value, onChange, readOnly, allowClear = false, noFuture = false,
  minDate, maxDate, placeholder = "dd/mm/yyyy", className, style,
}: Props) {
  const [seq, setSeq] = useState(0);   // đổi key = gắn lại ô, xoá chữ gõ sai còn nằm lại
  const typed = useRef(false);         // người dùng CÓ gõ phím trong ô lần này không?
  const display = value ? dayjs(value).format(DISPLAY) : "";

  const blocked = (d: Dayjs) =>
    (noFuture && d.isAfter(dayjs(), "day")) ||
    (!!minDate && d.isBefore(dayjs(minDate), "day")) ||
    (!!maxDate && d.isAfter(dayjs(maxDate), "day"));

  /** Rời ô mà chưa bấm Enter: antd chỉ chốt giá trị khi Enter hoặc chọn trên lịch, chữ vừa gõ sẽ
   *  nằm lại mà số liệu bên dưới vẫn của ngày cũ. Tự chốt ở đây cho khớp điều người dùng thấy.
   *
   *  ⚠ CHỈ chạy khi người dùng THẬT SỰ gõ phím, và chỉ gắn lại ô khi phải xoá chữ sai. Chọn ngày
   *  trên lịch cũng làm ô mất tiêu điểm → nếu đụng vào đây thì ô bị gắn lại ngay giữa cú bấm,
   *  lịch đóng trước khi cú bấm kịp ăn và người dùng thấy "bấm chọn ngày không được". */
  const commitTyped = (text: string) => {
    if (!typed.current) return;
    typed.current = false;
    const input = text.trim();
    if (input === display) return;
    const parsed = input ? parseTyped(input) : null;
    const rejected = input ? !parsed || blocked(parsed) : !allowClear;
    if (!rejected) {
      const iso = parsed ? parsed.format("YYYY-MM-DD") : "";
      if (iso !== value) onChange?.(iso);
      return;                 // chốt được rồi: ô tự hiện lại theo `value`, KHÔNG gắn lại
    }
    setSeq((n) => n + 1);     // gõ sai / ngoài khoảng cho phép → gắn lại ô, trả về giá trị cũ
  };

  return (
    <DatePicker
      key={seq}
      format={FORMATS}
      value={value ? dayjs(value) : null}
      onChange={(d) => { typed.current = false; onChange?.(d ? d.format("YYYY-MM-DD") : ""); }}
      onKeyDown={(e) => { if (e.key !== "Tab" && e.key !== "Escape") typed.current = true; }}
      onFocus={() => { typed.current = false; }}
      onBlur={(e) => commitTyped((e.target as HTMLInputElement).value ?? "")}
      disabled={readOnly}
      inputReadOnly={TOUCH_DEVICE}
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
