/* Sinh diễn giải đề xuất điều chỉnh giá sàn (tiếng Việt) từ số liệu mô hình.
 * Tách riêng khỏi component để dễ tái dùng + kiểm thử. KHÔNG gọi API. */

import type { FloorDriver, SuggestItem } from "./floor-suggest-client";

export const ACTION_LABEL: Record<string, string> = { raise: "NÂNG", hold: "GIỮ NGUYÊN", lower: "HẠ" };
export const CONF_LABEL: Record<string, string> = { high: "CAO", medium: "TRUNG BÌNH", low: "THẤP" };

const int = (n: number | null | undefined) => (n == null ? "—" : Math.round(n).toLocaleString("vi-VN"));
const pct = (n: number | null | undefined) => (n == null ? "—" : `${n.toFixed(1).replace(".", ",")}%`);
const sInt = (n: number | null | undefined) => (n == null ? "—" : (n > 0 ? "+" : "") + int(n));
const sPct = (n: number | null | undefined) => (n == null ? "—" : (n > 0 ? "+" : "") + pct(n));

export type Rationale = { headline: string; reasons: string[]; caution: string | null };
export type RationaleCtx = { prevAsOf: string | null; basketChangePct: number | null; drivers: FloorDriver[] };

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
  let caution: string | null = null;
  const shfe = ctx.drivers.find((d) => d.index.includes("SHFE"));
  const shfeChg = shfe?.change_pct;
  if (it.caution === "shfe_opposite") {
    caution = `SHFE RU (chỉ báo dẫn hướng, đồng hướng giá sàn ~88% lịch sử) đang đi NGƯỢC chiều đề xuất (${sPct(shfeChg)}) — cân nhắc thận trọng hoặc chờ xác nhận thêm.`;
  } else if (it.action !== "hold" && shfeChg != null) {
    if (Math.abs(shfeChg) >= 0.5 && (shfeChg > 0) === ((it.delta ?? 0) > 0)) {
      reasons.push(`SHFE RU (chỉ báo dẫn hướng, đồng hướng ~88% lịch sử) cùng chiều (${sPct(shfeChg)}) → xác nhận hướng điều chỉnh.`);
    } else if (Math.abs(shfeChg) < 0.5) {
      reasons.push(`SHFE RU gần như đi ngang (${sPct(shfeChg)}) → chưa cho tín hiệu xác nhận, dựa chủ yếu vào physical & rổ chỉ số.`);
    }
  }

  return { headline, reasons, caution };
}
