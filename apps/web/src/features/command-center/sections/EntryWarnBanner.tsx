/* Banner "N ô cần kiểm tra" — gom cảnh báo của cả phiếu về đầu màn.
   CHỈ NHẮC, KHÔNG CHẶN: nút Lưu vẫn bấm được bình thường (có khi số bất thường là số thật). */

import { WarningOutlined } from "@ant-design/icons";
import { useState } from "react";

import type { EntryWarning } from "../../../lib/unit-daily-warnings";

/** Số dòng hiện sẵn; nhiều hơn thì thu lại sau nút "xem thêm" để banner không đẩy form xuống quá sâu. */
const PREVIEW = 4;

export default function EntryWarnBanner({ items }: { items: EntryWarning[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  const shown = open ? items : items.slice(0, PREVIEW);
  const rest = items.length - shown.length;
  return (
    <div className="entry-warn-banner">
      <div className="entry-warn-head">
        <WarningOutlined /> {items.length} ô cần kiểm tra
        <span className="entry-warn-sub">— vẫn lưu được, nhưng soát lại giúp trước khi lưu</span>
      </div>
      <ul className="entry-warn-list">
        {shown.map((w, i) => (
          <li key={i}><b>{w.where}</b>: {w.message}</li>
        ))}
      </ul>
      {(rest > 0 || open) && (
        <button type="button" className="btn entry-warn-more" onClick={() => setOpen(!open)}>
          {open ? "Thu gọn" : `Xem thêm ${rest} ô`}
        </button>
      )}
    </div>
  );
}
