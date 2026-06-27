/* Client API Gợi ý giá sàn + tương quan chỉ số. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";

export type FloorModel = "v1" | "v1i" | "v1f" | "v2"; // rổ · +tồn kho tổng · +tồn kho tự do · đa biến
export type FloorPoint = { lan: number; as_of: string };
export type FloorAction = "raise" | "hold" | "lower";
export type FloorConfidence = "high" | "medium" | "low";
/** Biến động 1 chỉ số trong rổ kể từ lần ban hành trước (căn cứ cho đề xuất). */
export type FloorDriver = { index: string; prev: number | null; cur: number | null; change_pct: number | null };
export type SuggestItem = {
  grade: string; actual: number | null; suggested: number | null;
  diff: number | null; r: number | null;
  prev: number | null;          // giá sàn grade ở lần ban hành liền trước
  delta: number | null;         // đề xuất điều chỉnh = suggested − prev
  delta_pct: number | null;
  band: number;                 // ngưỡng nhiễu (USD) = MAE backtest grade
  action: FloorAction | null;   // NÂNG / GIỮ / HẠ theo dead-band
  confidence: FloorConfidence | null;
  caution: string | null;       // "shfe_opposite" khi SHFE ngược hướng
  mape: number | null;          // MAPE gộp toàn chuỗi backtest
  mape_move: number | null;     // MAPE RIÊNG các lần mô hình đề xuất điều chỉnh
  n_move: number;               // số lần backtest mô hình đề xuất điều chỉnh
  hit: number | null; n_bt: number; // bằng chứng backtest grade
};
export type SuggestResult = {
  as_of: string; model: FloorModel; backtest: boolean; n_train: number;
  feats: string[]; items: SuggestItem[];
  prev_as_of: string | null;            // ngày lần ban hành liền trước
  basket_change_pct: number | null;     // TB biến động rổ kể từ lần trước
  drivers: FloorDriver[];
  is_issuance?: boolean;                // false = ngày bất kỳ (chưa ban hành)
  error?: string;                       // ngày không hợp lệ
};
export type CorrRow = { index: string; r: number; n: number };
export type ChartSeries = { name: string; values: (number | null)[] };
export type FloorChart = { labels: string[]; series: ChartSeries[] };

export type BacktestMetrics = {
  mae: number; mape: number; rmse: number; r2: number; n: number; hit: number | null;
  mape_move?: number | null; n_move?: number;  // sai số trên các lần thực sự điều chỉnh
};
export type BacktestPoint = {
  as_of: string; lan: number; actual: number; pred: number; err: number; err_pct: number;
};
export type BacktestResult = {
  grade: string; model: FloorModel; alpha: number;
  metrics: BacktestMetrics; points: BacktestPoint[];
};
export type BacktestSummaryRow = {
  grade: string; mape: number | null; rmse: number | null; hit: number | null; n: number;
};

async function req<T>(path: string): Promise<T> {
  let res: Response;
  try { res = await fetch(`${API}${path}`, { headers: authHeaders() }); }
  catch { throw new Error("Không kết nối được API (" + API + ")"); }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const b = await res.json(); msg = b.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

/** Danh sách lần đã ban hành (cho dropdown chọn điểm so sánh). */
export const fetchFloorPoints = () => req<FloorPoint[]>(`/api/floor-suggest/points`);

/** Gợi ý giá sàn tại 1 lần + so với giá đã ban hành. */
export const fetchFloorSuggest = (as_of: string, model: FloorModel = "v1", backtest = true) =>
  req<SuggestResult>(`/api/floor-suggest?as_of=${as_of}&model=${model}&backtest=${backtest}`);

/** Backtest toàn chuỗi 1 grade (dự báo từng lần vs giá sàn thực + metrics). */
export const fetchFloorBacktest = (grade: string, model: FloorModel = "v1") =>
  req<BacktestResult>(`/api/floor-suggest/backtest?grade=${encodeURIComponent(grade)}&model=${model}`);

/** MAPE / % đúng hướng cho cả 13 grade (so độ khớp tổng quát v1 vs v2). */
export const fetchFloorBacktestSummary = (model: FloorModel = "v1") =>
  req<BacktestSummaryRow[]>(`/api/floor-suggest/backtest/summary?model=${model}`);

/** Bảng tương quan giá sàn (1 grade) vs các chỉ số. */
export const fetchFloorCorrelation = (grade: string) =>
  req<CorrRow[]>(`/api/floor-suggest/correlation?grade=${encodeURIComponent(grade)}`);

export type ScenarioItem = {
  grade: string; prev: number | null;
  bear: number | null; base: number | null; bull: number | null;
};
export type ScenarioResult = {
  as_of: string; model: FloorModel; shock_pct: number; items: ScenarioItem[]; error?: string;
};

/** Ma trận kịch bản Giảm/Cơ sở/Tăng (sốc ±shock lên rổ chỉ số). */
export const fetchScenarios = (as_of: string, model: FloorModel = "v1") =>
  req<ScenarioResult>(`/api/floor-suggest/scenarios?as_of=${as_of}&model=${model}`);

/** Chuỗi chuẩn hoá base-100 (giá sàn + chỉ số) để vẽ chart tương quan. */
export const fetchFloorChart = (grade: string) =>
  req<FloorChart>(`/api/floor-suggest/chart?grade=${encodeURIComponent(grade)}`);

/** Tờ trình giá sàn (HTML A4) cho 1 lần ban hành — để preview & in. */
export async function fetchToTrinhHtml(as_of: string, model: FloorModel = "v1"): Promise<string> {
  let res: Response;
  try { res = await fetch(`${API}/api/floor-suggest/to-trinh?as_of=${as_of}&model=${model}`, { headers: authHeaders() }); }
  catch { throw new Error("Không kết nối được API (" + API + ")"); }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}
