import { Segmented, Space } from "antd";

import {
  CAP_GROUPS,
  type Cap,
  type CapLevel,
  DATA_CAPS,
  formatCap,
  isSplitCap,
  parseCap,
} from "../../../lib/permissions";

const META: Record<string, { label: string; hint?: string }> =
  Object.fromEntries(DATA_CAPS.map((c) => [c.key, { label: c.label, hint: c.hint }]));

type Choice = "none" | CapLevel;

// Mục nhập liệu: 3 mức. Mục phân tích/bản tin: chỉ bật/tắt (không có khái niệm "chỉ xem").
const SPLIT_OPTS = [
  { value: "none", label: "Không" },
  { value: "view", label: "Xem" },
  { value: "edit", label: "Sửa" },
];
const FLAG_OPTS = [
  { value: "none", label: "Không" },
  { value: "edit", label: "Có quyền" },
];

/** Chọn quyền theo mục cho chuyên viên (editor) — mỗi mục nhập liệu chọn được Xem hoặc Sửa.
 *
 * Dùng như 1 field của antd Form (`value`/`onChange`): value là mảng dạng lưu,
 * vd `["physical:view", "raw_material"]` = Physical chỉ Xem, Giá mủ nguyên liệu được Sửa. */
export default function CapPermissionPicker(
  { value = [], onChange }: { value?: string[]; onChange?: (v: string[]) => void },
) {
  const current = new Map<Cap, CapLevel>();
  for (const entry of value) {
    const parsed = parseCap(entry);
    if (parsed) current.set(parsed[0], parsed[1]);
  }

  const set = (key: Cap, choice: Choice) => {
    const next = new Map(current);
    if (choice === "none") next.delete(key);
    else next.set(key, choice);
    // Giữ đúng thứ tự DATA_CAPS cho dễ đọc/so sánh.
    onChange?.(DATA_CAPS.filter((c) => next.has(c.key)).map((c) => formatCap(c.key, next.get(c.key)!)));
  };

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      {CAP_GROUPS.map((g) => (
        <div key={g.title}>
          <div style={{ fontWeight: 600, fontSize: 11, color: "#0a9e48", letterSpacing: 0.4,
            textTransform: "uppercase", marginBottom: 6 }}>{g.title}</div>
          <Space direction="vertical" size={6} style={{ width: "100%", paddingLeft: 2 }}>
            {g.keys.map((k) => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0, lineHeight: 1.35 }}>
                  {META[k].label}
                  {META[k].hint && <span style={{ color: "#999", fontSize: 12 }}> — {META[k].hint}</span>}
                </div>
                <Segmented
                  size="small"
                  style={{ flex: "0 0 auto" }}
                  value={current.get(k) ?? "none"}
                  options={isSplitCap(k) ? SPLIT_OPTS : FLAG_OPTS}
                  onChange={(v) => set(k, v as Choice)}
                />
              </div>
            ))}
          </Space>
        </div>
      ))}
    </Space>
  );
}
