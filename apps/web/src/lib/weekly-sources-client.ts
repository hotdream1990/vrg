/* Client danh mục "Nguồn tham khảo" của Báo cáo tuần — `/api/weekly-sources`.
   Hợp đồng: plans/260913-weekly-report-v2/plan.md mục B (Nguồn tham khảo). */

import { apiFetch } from "./http";

export type WeeklySource = {
  id: number;
  category: string;        // futures | physical | financial | news | macro
  name: string;
  role: string;
  url: string;
  sections: string[];      // ⊂ I, II, III.1, III.2, III.3, IV.1..IV.4, V, VI
  guide: string;
  mode: string;            // internal | market_feed | vietnambiz | attachment | manual
  feed_symbol: string | null;
  enabled: boolean;
  sort_order: number;
  updated_by: string | null;
  updated_at: string | null;
};
/** Body POST/PUT — role/url/guide là chuỗi ("" = trống; máy chủ KHÔNG nhận null), sort_order null = xếp cuối. */
export type WeeklySourceInput = Omit<WeeklySource, "id" | "updated_by" | "updated_at" | "sort_order"> & {
  sort_order: number | null;
};
export type MetaOption = { key: string; label: string };
export type WeeklySourceMeta = { categories: MetaOption[]; modes: MetaOption[]; sections: MetaOption[] };

/** Mã mục của báo cáo — dùng khi /meta chưa trả về (nhãn = mã). */
export const SECTION_KEYS = ["I", "II", "III.1", "III.2", "III.3", "IV.1", "IV.2", "IV.3", "IV.4", "V", "VI"];

const J = { "Content-Type": "application/json" };

export const listWeeklySources = () => apiFetch<WeeklySource[]>("/api/weekly-sources");

export async function getWeeklySourceMeta(): Promise<WeeklySourceMeta> {
  const raw = await apiFetch<Record<string, unknown>>("/api/weekly-sources/meta");
  return {
    categories: toOptions(raw.categories),
    modes: toOptions(raw.modes),
    sections: toOptions(raw.sections),
  };
}

export const createWeeklySource = (body: WeeklySourceInput) =>
  apiFetch<WeeklySource>("/api/weekly-sources", { method: "POST", headers: J, body: JSON.stringify(body) });

export const updateWeeklySource = (id: number, body: WeeklySourceInput) =>
  apiFetch<WeeklySource>(`/api/weekly-sources/${id}`, { method: "PUT", headers: J, body: JSON.stringify(body) });

export const deleteWeeklySource = (id: number) =>
  apiFetch<unknown>(`/api/weekly-sources/${id}`, { method: "DELETE" });

export const resetWeeklySources = () =>
  apiFetch<unknown>("/api/weekly-sources/reset-defaults", { method: "POST" });

/** Bỏ các cột máy chủ tự quản → body gửi PUT/POST. */
export const toSourceInput = (s: WeeklySource): WeeklySourceInput => ({
  category: s.category, name: s.name, role: s.role ?? "", url: s.url ?? "", sections: s.sections ?? [],
  guide: s.guide ?? "", mode: s.mode, feed_symbol: s.feed_symbol, enabled: s.enabled, sort_order: s.sort_order,
});

/** Nhãn của 1 mã theo meta; không có thì trả chính mã. */
export const optionLabel = (opts: MetaOption[], key: string) =>
  opts.find((o) => o.key === key)?.label ?? key;

/* /meta trả mảng {value, label}; vẫn chấp nhận {key|code, label}
   lẫn object {key: label} hay mảng chuỗi — tránh vỡ màn chỉ vì khác hình dạng JSON. */
function toOptions(x: unknown): MetaOption[] {
  if (Array.isArray(x)) {
    return x.map((it) => {
      if (typeof it === "string") return { key: it, label: it };
      const o = (it ?? {}) as Record<string, unknown>;
      const key = String(o.key ?? o.value ?? o.code ?? o.id ?? "");
      return { key, label: String(o.label ?? o.name ?? key) };
    }).filter((o) => o.key);
  }
  if (x && typeof x === "object") {
    return Object.entries(x as Record<string, unknown>).map(([key, label]) => ({ key, label: String(label) }));
  }
  return [];
}
