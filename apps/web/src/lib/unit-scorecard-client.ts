/* Client API màn "Chỉ số đơn vị" — một bảng hai cấp khu vực → đơn vị, nhiều tab chỉ số.
   Danh mục cho các ô lọc dùng chung `fetchFilterCatalog` của màn Thống kê (cùng một nguồn). */

import { apiFetch } from "./http";
import type { StockCoverage } from "./unit-analytics-client";

const BASE = "/api/unit-daily/scorecard";

/** `by_grade` là tab CHỈ CÓ Ở WEB (lật bảng: cột = chủng loại), gọi endpoint `/by-grade`. */
export type TabKey = "overview" | "purchase" | "consumption" | "stock" | "compliance"
  | "by_grade";

/** `grade_filter`: full = lọc chủng loại áp cho cả bảng · partial = chỉ áp phần thành phẩm ·
 *  none = chỉ số của tab không gắn chủng loại (web làm mờ ô lọc kèm giải thích). */
export type TabInfo = {
  key: TabKey; label: string; axis: "period" | "as_of";
  grade_filter: "full" | "partial" | "none";
};

export type ScorecardCol = {
  key: string; label: string; unit: string; note: string;
  /** Chỉ số cộng dồn theo kỳ → so được với kỳ khác (giá BQ, %, ảnh chụp tồn kho thì không). */
  compare: boolean;
};

export type ScorecardValues = Record<string, number | string | null>;

export type ScorecardUnit = {
  company: string;
  merged_into: string | null;
  has_data: boolean;
  values: ScorecardValues;
};

export type ScorecardRegion = {
  region: string;
  units: number;
  /** Số đơn vị trong khu vực CHƯA có số nào ở tab này — ô trống là thiếu dữ liệu, không phải 0. */
  no_data: number;
  values: ScorecardValues;
  children: ScorecardUnit[];
};

export type ScorecardReport = {
  tab: TabKey;
  axis: "period" | "as_of";
  date_from: string; date_to: string; as_of: string;
  cols: ScorecardCol[];
  regions: ScorecardRegion[];
  totals: ScorecardValues;
  coverage: StockCoverage | null;
  /** Tab Tồn kho: ngày gần nhất CÓ số khi ngày chốt đang trống (gợi ý đổi ngày, không tự đổi). */
  latest_stock_day: string | null;
  warnings: string[];
};

export type ScorecardFilters = {
  tab: TabKey;
  from: string; to: string;
  /** Ngày chốt tồn kho — để trống thì server lấy ngày cuối kỳ. */
  asOf?: string;
  companies: string[]; regions: string[]; grades: string[];
  statusKind: "purchase" | "consumption";
  splitMerged: boolean;
};

export function scorecardQuery(f: ScorecardFilters): string {
  const p = new URLSearchParams({
    tab: f.tab, date_from: f.from, date_to: f.to, status_kind: f.statusKind,
  });
  if (f.asOf) p.set("as_of", f.asOf);
  const put = (k: string, v: string[]) => { if (v.length) p.set(k, v.join(",")); };
  put("companies", f.companies);
  put("regions", f.regions);
  put("grades", f.grades);
  if (f.splitMerged) p.set("split_merged", "true");
  return p.toString();
}

/** Chỉ số đổ vào ô của BẢNG CHÉO đơn vị × chủng loại (cột là chủng loại nên chỉ chọn được một). */
export type MeasureInfo = {
  key: string; label: string; unit: string; axis: "period" | "as_of";
  /** Lời nhắc về phạm vi của chỉ số (vd thu mua chỉ gồm thành phẩm mua ngoài). */
  note: string;
};

export const fetchScorecardTabs = () =>
  apiFetch<{ tabs: TabInfo[]; measures: MeasureInfo[] }>(`${BASE}/tabs`);

/** Bảng chéo: cùng khuôn `ScorecardReport` nên web dùng lại đúng một component bảng. */
export type GradeReport = ScorecardReport & {
  measure: string; label: string; unit: string;
  /** Chủng loại đã gộp vào cột "Khác" — hiện ra để người xem biết cột đó gồm những gì. */
  hidden_grades: string[];
};

export const fetchScorecardByGrade = (f: ScorecardFilters, measure: string) => {
  const p = new URLSearchParams({
    measure, date_from: f.from, date_to: f.to,
  });
  if (f.asOf) p.set("as_of", f.asOf);
  if (f.companies.length) p.set("companies", f.companies.join(","));
  if (f.regions.length) p.set("regions", f.regions.join(","));
  if (f.splitMerged) p.set("split_merged", "true");
  return apiFetch<GradeReport>(`${BASE}/by-grade?${p.toString()}`);
};

export const fetchScorecard = (f: ScorecardFilters) =>
  apiFetch<ScorecardReport>(`${BASE}?${scorecardQuery(f)}`);
