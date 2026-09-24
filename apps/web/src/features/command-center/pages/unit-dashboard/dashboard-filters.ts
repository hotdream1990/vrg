/* Trạng thái bộ lọc của Dashboard đơn vị: phạm vi (Tập đoàn · khu vực · đơn vị) + kỳ + ngày chốt
   tồn kho. Tách khỏi component để luật chuyển phạm vi đọc được một chỗ. */

import { type Preset, rangeOf } from "../../../../lib/date-presets";
import type { DashQuery, DashScope, ScopeCatalog } from "../../../../lib/unit-dashboard-client";

export type DashPreset = Extract<Preset, "Tuần này" | "Tháng này" | "Tháng trước" | "Năm nay" | "Tự chọn">;
export const DASH_PRESETS: readonly DashPreset[] = ["Tuần này", "Tháng này", "Tháng trước", "Năm nay", "Tự chọn"];

export type DashFilters = DashQuery & { preset: DashPreset };

/** "Hôm nay" theo giờ VN do server gửi — dựng Date theo giờ ĐỊA PHƯƠNG (new Date("YYYY-MM-DD")
 *  hiểu là nửa đêm UTC, ở múi giờ âm sẽ lùi một ngày). */
const localDate = (iso: string): Date => {
  const [y, m, d] = iso.split("-").map(Number);
  return y && m && d ? new Date(y, m - 1, d) : new Date();
};

export function presetRange(p: DashPreset, today: string) {
  return rangeOf(p, localDate(today));
}

/** Bộ lọc khởi tạo: phạm vi mặc định do server chọn, kỳ = tháng này, ngày chốt để server tự lấy. */
export function initialDashFilters(catalog: ScopeCatalog): DashFilters {
  const r = presetRange("Tháng này", catalog.today)!;
  const scope = catalog.mode === "unit" ? "unit" : catalog.default.scope;
  const key = catalog.mode === "unit"
    ? (catalog.default.key ?? catalog.units[0]?.name ?? null)
    : catalog.default.key;
  return { scope, key, from: r.from, to: r.to, asOf: "", preset: "Tháng này" };
}

/** Đổi cấp phạm vi mà vẫn bám chỗ đang xem: đơn vị → khu vực của chính nó; khu vực → đơn vị đầu
 *  tiên trong khu vực đó. Không có gì để bám thì lấy mục đầu danh sách. */
export function switchScope(catalog: ScopeCatalog, f: DashFilters, next: DashScope): DashFilters {
  if (next === f.scope) return f;
  if (next === "group") return { ...f, scope: next, key: null };
  if (next === "region") {
    const own = f.scope === "unit" ? catalog.units.find((u) => u.name === f.key)?.region : null;
    return { ...f, scope: next, key: own ?? catalog.regions[0]?.name ?? null };
  }
  const inRegion = f.scope === "region" ? catalog.units.find((u) => u.region === f.key) : undefined;
  return { ...f, scope: next, key: (inRegion ?? catalog.units[0])?.name ?? null };
}

/** Bộ lọc → tham số gọi API; null khi chưa đủ điều kiện (thiếu khu vực/đơn vị, khoảng ngày ngược). */
export function toQuery(f: Partial<DashQuery>): DashQuery | null {
  const { scope, key, from, to, asOf } = f;
  if (!scope || !from || !to || from > to) return null;
  if (scope !== "group" && !key) return null;
  return { scope, key: scope === "group" ? null : key ?? null, from, to, asOf: asOf ?? "" };
}

/** Nhãn phạm vi khi server chưa trả (đang tải) — server trả `scope.label` thì dùng của server. */
export function localScopeLabel(f: DashFilters): string {
  if (f.scope === "group") return "Toàn Tập đoàn";
  if (f.scope === "region") return `Khu vực ${f.key ?? "—"}`;
  return f.key ?? "—";
}
