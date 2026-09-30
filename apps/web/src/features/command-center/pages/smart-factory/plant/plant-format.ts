/* Trạng thái thiết bị · độ mới của số · hình học khung cho Sơ đồ vận hành (định dạng số/giờ dùng chung
   ở ../smart-factory-format). Giờ là giờ nhà máy `YYYY-MM-DDTHH:MM:SS` → so chuỗi, không qua múi máy người xem. */

import type { PlantNode, PlantValues } from "../../../../../lib/smart-factory-client";

/** Nhiệt độ thiết bị (ổ đỡ, mô-tơ…) từ mức này trở lên thì tô cam. */
export const HOT_TEMP_C = 70;
/** Tag trạng thái 0/1: từ mức này trở lên là đang chạy. */
export const RUN_MIN = 0.5;
/** Số lẻ trên ô số của thiết bị (Hz · A · °C). */
export const VALUE_DIGITS = 2;

export const valueOf = (values: PlantValues, tag?: string | null): number | null =>
  (tag ? values[tag]?.value ?? null : null);

/** Giờ đọc mới nhất trong các số (chuỗi ISO cùng khuôn → so chuỗi là đủ). */
export function latestAt(values: PlantValues | null): string | null {
  let best: string | null = null;
  for (const r of Object.values(values ?? {})) {
    if (r?.at && r.value != null && (best == null || r.at > best)) best = r.at;
  }
  return best;
}

/** Máy chủ trả lời (`fetchedAt`) mà số mới nhất đã đọc từ trước đó quá mức này → số cũ (SCADA ngừng ghi). */
const STALE_S = 90;

/** Hai mốc cùng khuôn của server đọc như UTC → hiệu số không phụ thuộc múi giờ máy người xem. */
const toSec = (ts: string) => Date.parse(`${ts.slice(0, 19)}Z`) / 1000;

export function isStale(fetchedAt: string | null | undefined, latest: string | null): boolean {
  if (!fetchedAt || !latest) return false;
  const gap = toSec(fetchedAt) - toSec(latest);
  return Number.isFinite(gap) && gap > STALE_S;
}

/** run/stop theo tag trạng thái · unknown = không có tag trạng thái hoặc tag chưa có số. */
export type RunState = "run" | "stop" | "unknown";

export function runState(n: PlantNode, values: PlantValues): RunState {
  const v = valueOf(values, n.status_tag);
  if (v == null) return "unknown";
  return v >= RUN_MIN ? "run" : "stop";
}

/** Mọi tag của một thiết bị (trạng thái → chỉ số → nhiệt độ). */
export const nodeTags = (n: PlantNode): string[] => [
  ...(n.status_tag ? [n.status_tag] : []),
  ...(n.metrics ?? []).map((m) => m.tag),
  ...(n.temps ?? []).map((t) => t.tag),
];

/** Thiết bị chưa có số nào (mọi tag trống) → vẽ viền nét đứt. */
export const hasNoData = (n: PlantNode, values: PlantValues) =>
  nodeTags(n).every((t) => valueOf(values, t) == null);

export type Box = { x: number; y: number; w: number; h: number };

/** Khung bao THẲNG của thiết bị sau khi xoay quanh tâm — để đặt nhãn/ô số không đè lên hình. */
export function outerBox(n: PlantNode): Box {
  const a = ((n.angle ?? 0) * Math.PI) / 180;
  const w = Math.abs(n.w * Math.cos(a)) + Math.abs(n.h * Math.sin(a));
  const h = Math.abs(n.w * Math.sin(a)) + Math.abs(n.h * Math.cos(a));
  return { x: n.x + n.w / 2 - w / 2, y: n.y + n.h / 2 - h / 2, w, h };
}

export const center = (n: PlantNode): [number, number] => [n.x + n.w / 2, n.y + n.h / 2];

export type Side = "top" | "bottom" | "left" | "right";

const OPPOSITE: Record<Side, Side> = { top: "bottom", bottom: "top", left: "right", right: "left" };
export const opposite = (s: Side) => OPPOSITE[s];

const GAP = 5;

/** Góc trên-trái của khối nhãn/ô số rộng bw × cao bh đặt ở cạnh `side` của khung `b`. */
export function blockAt(b: Box, side: Side, bw: number, bh: number): [number, number] {
  switch (side) {
    case "bottom": return [b.x + b.w / 2 - bw / 2, b.y + b.h + GAP];
    case "left": return [b.x - bw - GAP, b.y + b.h / 2 - bh / 2];
    case "right": return [b.x + b.w + GAP, b.y + b.h / 2 - bh / 2];
    default: return [b.x + b.w / 2 - bw / 2, b.y - bh - GAP];
  }
}
