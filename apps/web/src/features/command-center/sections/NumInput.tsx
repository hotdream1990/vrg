/* Ô nhập số có định dạng nghìn (vi-VN) — dùng chung cho các form giá.
   `prevValue` (tuỳ chọn) = giá kỳ trước; lệch ≥10% → viền vàng + icon cảnh báo. */

import { useState } from "react";

import { isBigChange } from "../../../lib/change-warning";
import { formatViNumber, parseViNumber } from "../../../lib/number-format";
import ChangeWarn from "./ChangeWarn";

type Props = {
  value: number | null;
  onChange: (v: number | null) => void;
  readOnly?: boolean;
  placeholder?: string;
  className?: string;
  prevValue?: number | null;
};

export default function NumInput({ value, onChange, readOnly, placeholder = "—", className, prevValue }: Props) {
  const warn = isBigChange(value, prevValue);
  // Đang gõ thì giữ NGUYÊN chuỗi thô (`draft`): nếu format lại sau mỗi phím thì vừa gõ "2238,"
  // đã bị nắn thành "2.238" → ký tự thập phân tiếp theo dính sai chỗ. Rời ô mới format lại.
  const [draft, setDraft] = useState<string | null>(null);
  // Luôn giữ cùng một cây phần tử gốc (span > input): nếu đổi kiểu gốc khi warn lật,
  // React remount thẻ input → mất focus giữa lúc gõ. Chỉ bật/tắt icon cảnh báo bên trong.
  return (
    <span className="num-warn-wrap">
      <input
        type="text"
        inputMode="decimal"
        className={`${className ?? "blt-cell-input"}${warn ? " num-warn" : ""}`}
        value={draft ?? formatViNumber(value)}
        readOnly={readOnly}
        placeholder={placeholder}
        onChange={(e) => { setDraft(e.target.value); onChange(parseViNumber(e.target.value)); }}
        onBlur={() => setDraft(null)}
      />
      {warn && <ChangeWarn value={value} prev={prevValue} />}
    </span>
  );
}
