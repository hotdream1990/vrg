/* Ô nhập số + hộp chỉ đọc dùng chung cho form Thu mua & Tiêu thụ–Tồn kho.
   Định dạng số kiểu vi-VN: nhóm nghìn "." + thập phân ",". */

import { useCallback, useState } from "react";
import { InputNumber, Tooltip } from "antd";

import { type Bound, boundWarning } from "../../../lib/entry-bounds";
import { formatViNumber } from "../../../lib/number-format";

//: Dạng nhóm nghìn kiểu Việt: "1.250" · "12.345.678" — mỗi nhóm sau dấu chấm ĐÚNG 3 chữ số.
const THOUSANDS = /^-?\d{1,3}(\.\d{3})+$/;

/** Chuỗi người dùng gõ → chuỗi số cho `InputNumber` (giữ nguyên trạng thái đang gõ dở).
 *
 *  ⚠ Trước 20/09/2026 hàm này XOÁ MỌI dấu chấm, nên gõ `3.5` ra **35** — sai gấp 10 lần mà không
 *  có dấu hiệu gì. Bàn phím số của laptop cho ra dấu chấm nên đây là bẫy rất dễ sập.
 *  Nay theo đúng luật của `parseViNumber` (lib/number-format.ts — nguồn duy nhất): dấu chấm chỉ là
 *  phân cách nghìn khi chuỗi ĐÚNG dạng nhóm nghìn; còn lại coi là dấu thập phân.
 *  KHÔNG gọi thẳng `parseViNumber` vì antd gọi hàm này sau MỖI phím: nó phải giữ được trạng thái
 *  gõ dở như "3," hay "3." (parse ra số sẽ nuốt mất dấu vừa gõ).
 */
export const parseInput = (s?: string): string => {
  const raw = (s ?? "").trim();
  if (raw.includes(",")) return raw.replace(/\./g, "").replace(",", ".");
  return THOUSANDS.test(raw) ? raw.replace(/\./g, "") : raw;
};

type ViNumberFieldProps = {
  value: number | null; onChange: (v: number | null) => void;
  disabled?: boolean; size?: "small"; status?: "warning";
  /** `undefined` = không bọc Tooltip; còn lại (kể cả "") = bọc. Tooltip nằm TRONG component vì
   *  Tooltip cần gắn ref/sự kiện chuột thẳng lên InputNumber. */
  tip?: string;
};

/** `InputNumber` hiển thị số vi-VN. Chỉ nhóm nghìn khi KHÔNG đứng trong ô.
 *
 *  ⚠ Nếu nhóm nghìn cả lúc đang gõ/sửa thì gõ "1234" → ô hiện "1.234", gõ tiếp "5" → `parseInput`
 *  nhận "1.2345" (không còn là dạng nhóm nghìn) → hiểu là thập phân 1,2345: không nhập nổi quá 4
 *  chữ số; sửa số có sẵn bằng cách gõ nối cũng sai y vậy. Nên:
 *   - đang gõ (`userTyping`) → trả NGUYÊN chuỗi người dùng gõ;
 *   - đứng trong ô (focus) → số TRẦN không dấu chấm nghìn ("1234567,5"), để gõ nối không sai;
 *   - rời ô → nhóm nghìn "1.234.567,5".
 *  Trạng thái focus nằm trong component này nên chỉ ô đang sửa vẽ lại (bảng 1.100+ ô vẫn nhẹ). */
function ViNumberField({ value, onChange, disabled, size, status, tip }: ViNumberFieldProps) {
  const [focused, setFocused] = useState(false);
  const formatter = useCallback((v: string | number | undefined, info: { userTyping: boolean; input: string }) => {
    if (info.userTyping) return info.input;
    const text = formatViNumber(v);
    return focused ? text.replace(/\./g, "") : text;
  }, [focused]);
  const el = (
    <InputNumber
      value={value}
      onChange={(v) => onChange(v as number | null)}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      disabled={disabled}
      size={size}
      controls={false}
      min={0}
      status={status}
      formatter={formatter}
      parser={parseInput}
      style={{ width: "100%" }}
      placeholder="—"
    />
  );
  return tip === undefined ? el : <Tooltip title={tip}>{el}</Tooltip>;
}

/** Hộp ô chỉ đọc (cột suy ra / tự quy đổi) — nền mờ, viền nét đứt. */
export const readOnlyBox = (text: string, tag: string) => (
  <div style={{
    height: 32, lineHeight: "32px", padding: "0 11px", borderRadius: 6, textAlign: "right",
    background: "rgba(125,125,125,.12)", border: "1px dashed rgba(125,125,125,.35)", fontWeight: 600,
  }}>
    {text}
    <span style={{ fontSize: 10, opacity: 0.55, fontWeight: 400 }}> · {tag}</span>
  </div>
);

/** Ô nhập số (vi-VN). `size="small"` cho ô nằm TRONG BẢNG — để cao bằng Select/nút cùng dòng
    (mặc định của antd là 32px, lệch hẳn so với Select size="small" 24px).
    `bound` (tuỳ chọn): số ra ngoài khoảng thường gặp → viền cam (status="warning") + tooltip nói rõ
    đơn vị tính (xem `lib/entry-bounds.ts`). CHỈ CẢNH BÁO — không chặn gõ, không chặn lưu.
    `warn` (tuỳ chọn): lời cảnh báo ép sẵn, dùng cho lỗi mà bản thân con số không nói lên được —
    vd ô TRỐNG vẫn phải cảnh báo (dòng USD chưa nhập tỷ giá). Ưu tiên hơn `bound`.
    Cách bọc GIỮ NGUYÊN cây phần tử để lúc cảnh báo bật/tắt không remount input → không mất focus
    khi đang gõ; chỉ đổi màu viền, không lệch layout. */
export const numInput = (
  value: number | null, onChange: (v: number | null) => void, readOnly?: boolean,
  size?: "small", bound?: Bound | null, warnText?: string | null,
) => {
  const warn = warnText ?? boundWarning(value, bound);
  const hasTip = bound != null || warnText !== undefined;
  return (
    <ViNumberField
      value={value} onChange={onChange} disabled={readOnly} size={size}
      status={warn ? "warning" : undefined} tip={hasTip ? (warn ?? "") : undefined}
    />
  );
};

/** Nhãn ô + đơn vị (dùng chung). */
export const fieldLabel = (label: React.ReactNode, unit?: string) => (
  <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 2 }}>
    {label}{unit ? <> <span style={{ opacity: 0.6 }}>({unit})</span></> : null}
  </div>
);

/** Lưới ô nhập của biểu Thu mua — ô tự xuống dòng theo bề ngang màn hình. */
export const ENTRY_GRID = {
  display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))",
  gap: 10, alignItems: "end",
} as const;

/** Tiêu đề một khối trong lưới (chiếm trọn bề ngang). `first` = khối đầu, không chừa lề trên. */
export const sectionHead = (title: string, first?: boolean, hint?: string) => (
  <div style={{
    gridColumn: "1 / -1", fontWeight: 600, fontSize: 12.5, opacity: 0.85,
    marginTop: first ? 0 : 8, paddingBottom: 2, borderBottom: "1px solid rgba(125,125,125,.25)",
  }}>
    {title}
    {hint && <span style={{ fontWeight: 400, opacity: 0.7 }}> ({hint})</span>}
  </div>
);

/** Một ô của lưới: nhãn + đơn vị + ô nhập (hoặc hộp chỉ đọc). */
export const entryField = (label: React.ReactNode, unit: string | undefined, node: React.ReactNode) => (
  <label style={{ display: "block" }}>{fieldLabel(label, unit)}{node}</label>
);
