/* Ô hiển thị/sửa dùng trong bảng Phương án giá sàn (FloorProposalPanel). */

import { ExclamationCircleOutlined, WarningOutlined } from "@ant-design/icons";
import { Tag, Tooltip } from "antd";
import { useEffect, useRef, useState } from "react";

import type { ProposalOrigin, ProposalRow } from "../../../../lib/floor-proposal-client";
import NumInput from "../../sections/NumInput";

export const OFF_STEP_HINT = "Không phải bội bước ban hành (5 USD/tấn · 50.000 đ/tấn)";

const ORIGIN: Record<ProposalOrigin, { text: string; color: string }> = {
  model: { text: "Mô hình", color: "green" },
  current: { text: "Giá hiện hành", color: "blue" },
  ai: { text: "AI chỉnh", color: "purple" },
  manual: { text: "Sửa tay", color: "orange" },
};

/** Số kiểu VN: 2360 → "2.360", 1.5 → "1,5". Thiếu số → "—". */
export const fmtVi = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("vi-VN"));

const signed = (n: number) => (n > 0 ? "+" : "") + n.toLocaleString("vi-VN");

/** Chênh lệch so với lần trước: "+20 (+0,8%)" — xanh tăng, đỏ giảm, xám không đổi. */
export function DeltaText({ delta, pct }: { delta: number | null; pct: number | null }) {
  if (delta == null) return <span style={{ color: "var(--muted)" }}>—</span>;
  const color = delta > 0 ? "#16a34a" : delta < 0 ? "#e11d48" : "var(--muted)";
  return (
    <span style={{ color, fontWeight: 600, whiteSpace: "nowrap" }}>
      {signed(delta)}
      {pct != null && (
        <span style={{ fontSize: 11, marginLeft: 3, opacity: 0.85 }}>
          ({signed(Number(pct.toFixed(1)))}%)
        </span>
      )}
    </span>
  );
}

export function OriginTag({ origin }: { origin: ProposalOrigin }) {
  const o = ORIGIN[origin] ?? { text: origin, color: "default" };
  return <Tag color={o.color} style={{ marginInlineEnd: 0 }}>{o.text}</Tag>;
}

/** Tên chủng loại + chip đơn vị (dòng chỉ nội địa) + icon lệch bước / cảnh báo của dòng. */
export function GradeCell({ row }: { row: ProposalRow }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5, whiteSpace: "nowrap", fontWeight: 500 }}>
      <Tooltip title={row.grade}><span>{row.label}</span></Tooltip>
      {row.unit === "VNĐ/T" && <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 400 }}>(VNĐ/T)</span>}
      {row.off_step && (
        <Tooltip title={OFF_STEP_HINT}>
          <ExclamationCircleOutlined style={{ color: "var(--warn)", cursor: "help" }} />
        </Tooltip>
      )}
      {row.warning && (
        <Tooltip title={row.warning}>
          <WarningOutlined style={{ color: "var(--danger)", cursor: "help" }} />
        </Tooltip>
      )}
    </span>
  );
}

type NumCellProps = {
  value: number | null;
  prev: number | null;           // lần ban hành trước → cảnh báo lệch ≥10% (quy ước mọi ô nhập tay)
  readOnly?: boolean;
  syncKey: unknown;              // đổi khi phương án đổi → ô đang KHÔNG sửa đồng bộ lại số server
  onCommit: (v: number) => Promise<boolean>;
};

/** Ô sửa số: gõ tự do, chỉ gửi server khi rời ô / Enter; Esc = bỏ, trả số cũ.
 *  Ô đang được sửa giữ nguyên số đang gõ kể cả khi ô khác vừa được server cập nhật. */
export function ProposalNumCell({ value, prev, readOnly, syncKey, onCommit }: NumCellProps) {
  const [val, setVal] = useState<number | null>(value);
  const editing = useRef(false);
  const cancel = useRef(false);
  // Số của phương án HIỆN TẠI (props mới nhất) — server từ chối thì trả ô về số này, không lấy
  // `value` trong closure lúc gửi (các lần áp trước trong hàng đợi có thể đã đổi nó).
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => { if (!editing.current) setVal(value); }, [value, syncKey]);

  const commit = async () => {
    editing.current = false;
    if (cancel.current || val == null || val === value) {
      cancel.current = false;
      setVal(value);
      return;
    }
    const ok = await onCommit(val);
    if (!ok) setVal(valueRef.current);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLSpanElement>) => {
    const input = e.target as HTMLInputElement;
    if (e.key === "Enter") input.blur();
    // Esc chỉ huỷ ô đang sửa — chặn nổi bọt để không đóng luôn ngăn kéo/hộp thoại chứa bảng.
    if (e.key === "Escape") { e.stopPropagation(); cancel.current = true; input.blur(); }
  };

  // Bọc span để bắt blur/phím từ NumInput (sự kiện React nổi bọt) mà không phải sửa ô dùng chung.
  return (
    <span
      style={{ display: "block", minWidth: 84 }}
      onFocus={() => { if (!readOnly) editing.current = true; }}
      onBlur={readOnly ? undefined : commit}
      onKeyDown={readOnly ? undefined : onKeyDown}
    >
      <NumInput value={val} onChange={setVal} readOnly={readOnly} prevValue={prev} />
    </span>
  );
}
