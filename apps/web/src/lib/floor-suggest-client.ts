/* Client API Gợi ý giá sàn + tương quan chỉ số. */

import { API } from "./api-client";
import { authHeaders, onUnauthorized } from "./auth-token";
import { apiFetch } from "./http";

export type FloorModel = "v1" | "v1i" | "v1f" | "v2"; // rổ · +tồn kho tổng · +tồn kho tự do · đa biến
/** Mô hình xếp theo độ chính xác backtest trên prod (83 lần ban hành 2024 → 09/09/2026, 14 chủng loại):
 *  đa biến + mủ nước thắng rổ 4 futures ở cả 14 chủng loại (MAPE TB 2,85% vs 3,41%, đúng hướng 78% vs 73%,
 *  sai số khi điều chỉnh 3,81% vs 5,20%). Hai mô hình "+ tồn kho" chưa đủ lần ban hành có tồn kho ngày để đo
 *  nên xếp cuối. Phần tử đầu = mặc định của màn. */
export const FLOOR_MODELS: { value: FloorModel; label: string; short: string }[] = [
  { value: "v2", label: "Đa biến: 4 futures + mủ nước (khuyến nghị)", short: "Đa biến + mủ nước" },
  { value: "v1", label: "Rổ 4 futures (đối chiếu)", short: "Rổ futures" },
  { value: "v1i", label: "Rổ + Tồn kho tổng (thử nghiệm)", short: "+ Tồn kho tổng" },
  { value: "v1f", label: "Rổ + Tồn kho tự do (thử nghiệm)", short: "+ Tồn kho tự do" },
];
export const DEFAULT_FLOOR_MODEL: FloorModel = FLOOR_MODELS[0].value;
export type FloorPoint = { lan: number; as_of: string; title?: string };
export type FloorAction = "raise" | "hold" | "lower";
export type FloorCaution = "shfe_opposite" | "inventory_opposite";
/** Tồn kho tổng + tự do so với lần ban hành trước → tham chiếu nghiêng (không đổi số mô hình).
 *  up = tồn tăng (nghiêng GIỮ/HẠ) · down = tồn giảm (ủng hộ NÂNG) · flat = trong ±ngưỡng · mixed = trái chiều. */
export type InventoryLean = {
  direction: "up" | "down" | "flat" | "mixed";
  total_pct: number | null; free_pct: number | null; threshold_pct: number;
  base_day: string | null; day: string | null;
};
export type FloorConfidence = "high" | "medium" | "low";
/** Biến động 1 chỉ số trong rổ kể từ lần ban hành trước (căn cứ cho đề xuất). */
export type FloorDriver = { index: string; prev: number | null; cur: number | null; change_pct: number | null };
export type SuggestItem = {
  grade: string; unit: string; actual: number | null; suggested: number | null;
  diff: number | null; r: number | null;
  prev: number | null;          // giá sàn grade ở lần ban hành liền trước
  delta: number | null;         // đề xuất điều chỉnh = suggested − prev
  delta_pct: number | null;
  band: number;                 // ngưỡng nhiễu (USD) = MAE backtest grade
  action: FloorAction | null;   // NÂNG / GIỮ / HẠ theo dead-band
  confidence: FloorConfidence | null;
  cautions: FloorCaution[];     // tín hiệu đi ngược đề xuất nâng/hạ (mỗi cái hạ tin cậy 1 bậc)
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
  inventory?: InventoryAt | null;       // tồn kho Tập đoàn THEO NGÀY (biểu Tồn kho đơn vị)
  inventory_start?: string;             // ngày đầu tiên tồn kho ngày đủ đơn vị nhập
  inventory_lean?: InventoryLean | null; // tham chiếu nghiêng lên/xuống theo tồn kho
};
/** Tồn kho ngày có số gần nhất ≤ ngày gợi ý; `d_*` so với lần ban hành trước, chỉ trên đơn vị có số cả 2 ngày. */
export type InventoryAt = {
  day: string; ton_kho: number; ton_kho_hd: number; ton_free: number; units_counted: number;
  base_day: string | null; units_compared: number;
  d_ton_kho: number | null; d_ton_kho_pct: number | null; d_free: number | null; d_free_pct: number | null;
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
  ton_free?: number | null;  // tồn kho tự do (chưa có HĐ) tại lần này
};
export type BacktestResult = {
  grade: string; model: FloorModel; alpha: number;
  metrics: BacktestMetrics; points: BacktestPoint[];
  inventory_start?: string;             // tồn kho ngày có từ ngày này → v1i/v1f chỉ kiểm được sau đó
};
export type BacktestSummaryRow = {
  grade: string; mape: number | null; rmse: number | null; hit: number | null; n: number;
};

const req = apiFetch;

/** Danh sách lần đã ban hành (cho dropdown chọn điểm so sánh). */
export const fetchFloorPoints = () => req<FloorPoint[]>(`/api/floor-suggest/points`);

/** Gợi ý giá sàn tại 1 lần + so với giá đã ban hành. */
export const fetchFloorSuggest = (as_of: string, model: FloorModel = DEFAULT_FLOOR_MODEL, backtest = true) =>
  req<SuggestResult>(`/api/floor-suggest?as_of=${as_of}&model=${model}&backtest=${backtest}`);

/** Backtest toàn chuỗi 1 grade (dự báo từng lần vs giá sàn thực + metrics). */
export const fetchFloorBacktest = (grade: string, model: FloorModel = DEFAULT_FLOOR_MODEL) =>
  req<BacktestResult>(`/api/floor-suggest/backtest?grade=${encodeURIComponent(grade)}&model=${model}`);

/** MAPE / % đúng hướng cho cả 13 grade (so độ khớp tổng quát v1 vs v2). */
export const fetchFloorBacktestSummary = (model: FloorModel = DEFAULT_FLOOR_MODEL) =>
  req<BacktestSummaryRow[]>(`/api/floor-suggest/backtest/summary?model=${model}`);

/** Bảng tương quan giá sàn (1 grade) vs các chỉ số. */
export const fetchFloorCorrelation = (grade: string) =>
  req<CorrRow[]>(`/api/floor-suggest/correlation?grade=${encodeURIComponent(grade)}`);

export type ScenarioItem = {
  grade: string; unit: string; prev: number | null;
  bear: number | null; base: number | null; bull: number | null;
};
export type ScenarioResult = {
  as_of: string; model: FloorModel; shock_pct: number; items: ScenarioItem[]; error?: string;
};

/** Ma trận kịch bản Giảm/Cơ sở/Tăng (sốc ±shock lên rổ chỉ số). */
export const fetchScenarios = (as_of: string, model: FloorModel = DEFAULT_FLOOR_MODEL) =>
  req<ScenarioResult>(`/api/floor-suggest/scenarios?as_of=${as_of}&model=${model}`);

/** Chuỗi chuẩn hoá base-100 (giá sàn + chỉ số) để vẽ chart tương quan. */
export const fetchFloorChart = (grade: string) =>
  req<FloorChart>(`/api/floor-suggest/chart?grade=${encodeURIComponent(grade)}`);

/** Tờ trình giá sàn (HTML A4) cho 1 lần ban hành — để preview & in. */
export async function fetchToTrinhHtml(as_of: string, model: FloorModel = DEFAULT_FLOOR_MODEL): Promise<string> {
  let res: Response;
  try { res = await fetch(`${API}/api/floor-suggest/to-trinh?as_of=${as_of}&model=${model}`, { headers: authHeaders() }); }
  catch { throw new Error("Không kết nối được API (" + API + ")"); }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn"); }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}
