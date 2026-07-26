/* Preset kỳ báo cáo dùng chung cho các màn thống kê (tuần theo ISO: Thứ 2 → Chủ nhật). */

import { isoDate } from "./date";

export const PRESETS = ["Tuần này", "Tuần trước", "Tháng này", "Tháng trước", "Năm nay", "Tự chọn"] as const;
export type Preset = (typeof PRESETS)[number];

export type DateRange = { from: string; to: string };

/** Khoảng ngày của preset — "Tự chọn" trả null (giữ nguyên khoảng người dùng đang gõ). */
export function rangeOf(p: Preset, today = new Date()): DateRange | null {
  const d = new Date(today);
  if (p === "Tuần này" || p === "Tuần trước") {
    const dow = (d.getDay() + 6) % 7;                 // 0 = Thứ 2
    const mon = new Date(d); mon.setDate(d.getDate() - dow);
    if (p === "Tuần trước") mon.setDate(mon.getDate() - 7);
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    return { from: isoDate(mon), to: isoDate(sun) };
  }
  if (p === "Tháng này" || p === "Tháng trước") {
    const m = d.getMonth() - (p === "Tháng trước" ? 1 : 0);
    return { from: isoDate(new Date(d.getFullYear(), m, 1)), to: isoDate(new Date(d.getFullYear(), m + 1, 0)) };
  }
  if (p === "Năm nay") return { from: `${d.getFullYear()}-01-01`, to: `${d.getFullYear()}-12-31` };
  return null;
}
