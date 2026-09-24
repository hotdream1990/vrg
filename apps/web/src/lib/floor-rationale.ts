/* Sinh diễn giải đề xuất điều chỉnh giá sàn (tiếng Việt) từ số liệu mô hình.
 * Tách riêng khỏi component để dễ tái dùng + kiểm thử. KHÔNG gọi API. */

import { dmy } from "./date";
import type { FloorDriver, InventoryLean, SuggestItem } from "./floor-suggest-client";

export const ACTION_LABEL: Record<string, string> = { raise: "NÂNG", hold: "GIỮ NGUYÊN", lower: "HẠ" };
export const CONF_LABEL: Record<string, string> = { high: "CAO", medium: "TRUNG BÌNH", low: "THẤP" };

const int = (n: number | null | undefined) => (n == null ? "—" : Math.round(n).toLocaleString("vi-VN"));
const pct = (n: number | null | undefined) => (n == null ? "—" : `${n.toFixed(1).replace(".", ",")}%`);
const sInt = (n: number | null | undefined) => (n == null ? "—" : (n > 0 ? "+" : "") + int(n));
const sPct = (n: number | null | undefined) => (n == null ? "—" : (n > 0 ? "+" : "") + pct(n));

export type Rationale = { headline: string; reasons: string[]; cautions: string[] };
export type RationaleCtx = {
  prevAsOf: string | null; basketChangePct: number | null; drivers: FloorDriver[];
  inventoryLean?: InventoryLean | null;
};

/** Hướng tồn kho → câu ngắn (dùng chung cho ô Tồn kho và phần diễn giải). */
export const LEAN_LABEL: Record<InventoryLean["direction"], string> = {
  up: "áp lực tồn kho TĂNG → nghiêng GIỮ/HẠ",     // tổng hoặc tự do tăng quá ngưỡng
  down: "áp lực tồn kho GIẢM → ủng hộ NÂNG",
  flat: "tồn kho đi ngang → không làm nghiêng",
  mixed: "tổng và tự do trái chiều → không làm nghiêng",
};

/** "tổng +1,2%, tự do −4,0% so với 17/08/2026 (ngưỡng ±3%)". */
export const leanMoves = (l: InventoryLean) =>
  `tổng ${sPct(l.total_pct)}, tự do ${sPct(l.free_pct)} so với ${dmy(l.base_day)} (ngưỡng ±${pct(l.threshold_pct).replace(",0%", "%")})`;

/** Trả về diễn giải có cấu trúc (headline + căn cứ + cảnh báo), null nếu thiếu dữ liệu. */
export function buildRationale(it: SuggestItem | undefined, ctx: RationaleCtx): Rationale | null {
  if (!it || it.suggested == null || it.prev == null || it.action == null) return null;

  const headline = it.action === "hold"
    ? `Đề xuất GIỮ NGUYÊN giá sàn ${it.grade} (mô hình ≈ ${int(it.suggested)} USD/T, sát lần trước)`
    : `Đề xuất ${ACTION_LABEL[it.action]} giá sàn ${it.grade} ${sInt(it.delta)} USD/T (${sPct(it.delta_pct)}) → ${int(it.suggested)}`;

  const reasons: string[] = [];

  // 1) Biến động rổ chỉ số thị trường kể từ lần ban hành trước.
  const moved = ctx.drivers.filter((d) => d.change_pct != null);
  if (moved.length) {
    const top = [...moved].sort((a, b) => Math.abs(b.change_pct!) - Math.abs(a.change_pct!)).slice(0, 4)
      .map((d) => `${d.index} ${sPct(d.change_pct)}`).join(", ");
    reasons.push(`Rổ chỉ số thị trường ${sPct(ctx.basketChangePct)} kể từ lần ban hành ${ctx.prevAsOf ?? "trước"} (${top}).`);
  }

  // 2) Dead-band: so sánh mức điều chỉnh với ngưỡng nhiễu của mô hình.
  reasons.push(it.action === "hold"
    ? `Chênh lệch so với lần trước (${sInt(it.delta)}) nằm trong ngưỡng nhiễu ±${int(it.band)} USD (≈ sai số trung bình mô hình) → giữ nguyên, tránh điều chỉnh theo dao động ngắn hạn.`
    : `Mức điều chỉnh ${sInt(it.delta)} vượt ngưỡng nhiễu ±${int(it.band)} USD (≈ sai số trung bình mô hình) → là tín hiệu thực, không phải biến động ngẫu nhiên.`);

  // 3) Độ tin cậy = độ khớp backtest. Khi ĐỀ XUẤT điều chỉnh ⇒ nêu sai số RIÊNG trên các
  //    lần điều chỉnh (mape_move), trung thực hơn MAPE gộp (bị các lần giữ-nguyên kéo xuống).
  const onMove = it.action !== "hold" && it.n_move >= 3 && it.mape_move != null;
  if (onMove) {
    reasons.push(`Độ tin cậy ${CONF_LABEL[it.confidence ?? "low"]}: trên ${it.n_move} lần mô hình từng đề xuất điều chỉnh, sai số TB ${pct(it.mape_move)} (mức gộp mọi lần ${pct(it.mape)}, đúng hướng ${pct(it.hit)}).`);
  } else if (it.mape != null) {
    const hitTxt = it.hit != null ? `, đúng hướng ${pct(it.hit)}` : "";
    reasons.push(`Độ tin cậy ${CONF_LABEL[it.confidence ?? "low"]}: mô hình khớp lịch sử grade này với MAPE ${pct(it.mape)}${hitTxt} qua ${it.n_bt} lần kiểm định (walk-forward).`);
  }

  // 4) Đối chiếu SHFE (chỉ báo dẫn hướng) — chỉ tính khi SHFE biến động RÕ (≥0,5%), cùng
  //    ngưỡng với cảnh báo; SHFE đi ngang KHÔNG được coi là "xác nhận".
  const cautions: string[] = [];
  const shfe = ctx.drivers.find((d) => d.index.includes("SHFE"));
  const shfeChg = shfe?.change_pct;
  if (it.cautions.includes("shfe_opposite")) {
    cautions.push(`SHFE RU (chỉ báo dẫn hướng, đồng hướng giá sàn ~88% lịch sử) đang đi NGƯỢC chiều đề xuất (${sPct(shfeChg)}) — cân nhắc thận trọng hoặc chờ xác nhận thêm.`);
  } else if (it.action !== "hold" && shfeChg != null) {
    if (Math.abs(shfeChg) >= 0.5 && (shfeChg > 0) === ((it.delta ?? 0) > 0)) {
      reasons.push(`SHFE RU (chỉ báo dẫn hướng, đồng hướng ~88% lịch sử) cùng chiều (${sPct(shfeChg)}) → xác nhận hướng điều chỉnh.`);
    } else if (Math.abs(shfeChg) < 0.5) {
      reasons.push(`SHFE RU gần như đi ngang (${sPct(shfeChg)}) → chưa cho tín hiệu xác nhận, dựa chủ yếu vào physical & rổ chỉ số.`);
    }
  }

  // 5) Tham chiếu tồn kho (tổng + tự do so với lần trước) — chỉ để NGHIÊNG, không đổi số mô hình.
  const lean = ctx.inventoryLean;
  if (lean) {
    const moves = leanMoves(lean);
    if (it.cautions.includes("inventory_opposite")) {
      cautions.push(`Tồn kho đi NGƯỢC đề xuất ${ACTION_LABEL[it.action]}: ${moves} — đã hạ độ tin cậy 1 bậc; cân nhắc giữ nguyên hoặc điều chỉnh ít hơn mức mô hình.`);
    } else if (it.action === "hold") {
      reasons.push(`Tham chiếu tồn kho: ${moves} → ${LEAN_LABEL[lean.direction]}${lean.direction === "up" ? ", ủng hộ giữ nguyên" : ""}.`);
    } else {
      const agree = (it.action === "raise" && lean.direction === "down") || (it.action === "lower" && lean.direction === "up");
      reasons.push(`Tham chiếu tồn kho: ${moves} → ${agree ? `cùng chiều, ủng hộ ${ACTION_LABEL[it.action]}` : LEAN_LABEL[lean.direction]}.`);
    }
  }

  return { headline, reasons, cautions };
}
