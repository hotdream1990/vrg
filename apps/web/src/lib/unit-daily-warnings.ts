/* Gom mọi cảnh báo của MỘT phiếu báo cáo ngày để dựng banner "N ô cần kiểm tra".
 *
 *  Vì sao cần gom: bảng tiêu thụ phải cuộn ngang, ô bị cảnh báo rất dễ nằm ngoài tầm nhìn —
 *  chỉ tô viền cam thôi thì đơn vị vẫn bấm Lưu mà không thấy gì. Banner nói rõ SAI Ở ĐÂU.
 *
 *  Toàn bộ chỉ để HIỂN THỊ: không chặn gõ, không chặn lưu, không đổi số liệu.
 */

import {
  FX_USD_VND, PRICE_CUP,
  PRICE_LATEX, TONNES_DAILY, TONNES_STOCK, TONNES_YEAR,
  boundWarning, fxWarning, priceBound,
} from "./entry-bounds";
import type { ConsumptionData, StockQtyLine } from "./unit-daily-consumption";

/** Một cảnh báo: `where` = chỉ đường tới ô (bảng · dòng · cột), `message` = lý do. */
export type EntryWarning = { where: string; message: string };

type Raw = { where: string; message: string | null };
const keep = (items: Raw[]): EntryWarning[] =>
  items.filter((w): w is EntryWarning => w.message != null);

/** Cảnh báo của một bảng tồn kho chỉ có số lượng (khối 1 & 2). */
function stockQtyWarnings(rows: StockQtyLine[] | undefined, table: string): EntryWarning[] {
  return (rows ?? []).flatMap((r, i) =>
    keep([{ where: `${table} · dòng ${i + 1} · Số lượng`, message: boundWarning(r.qty, TONNES_STOCK) }]));
}

/** Toàn bộ cảnh báo của biểu TỒN KHO.
 *
 *  CỐ Ý không rà 2 mảng tiêu thụ cũ `sales` / `sales_own`: từ 30/07/2026 tiêu thụ tính từ hợp đồng
 *  nên form KHÔNG hiện chúng nữa, chỉ chuyển tiếp khi lưu. Rà tiếp thì phiếu cũ mở ra là báo
 *  "N ô cần kiểm tra" về những dòng người dùng không nhìn thấy và không sửa được ở đâu cả — bắt
 *  người ta đi tìm một ô không tồn tại. Số bán nay soát ở màn Hợp đồng (`ContractLinesTable`).
 */
export function consumptionWarnings(d: ConsumptionData): EntryWarning[] {
  return [
    ...stockQtyWarnings(d.stock_not_warehoused, "Tồn kho 1 · chưa nhập kho"),
    ...stockQtyWarnings(d.stock_warehoused, "Tồn kho 2 · đã nhập kho"),
    ...keep([{
      where: "Tồn kho 4 · nguyên liệu chưa sản xuất",
      message: boundWarning(d.stock_material, TONNES_STOCK),
    }]),
  ];
}

/** Số liệu biểu THU MUA cần soát.
 *
 *  CỐ Ý BỎ QUA hai nhóm ô của đơn vị nước ngoài, vì không thể có một biên cứng đúng cho chúng:
 *   - `price_*_local`: đơn giá theo nội tệ (LAK · KHR) — mỗi nội tệ một thang giá khác hẳn.
 *   - `fx_purchase`  : tỷ giá nội tệ→VND, thực tế 1,24–6,48 — dùng biên USD/VND (15.000–40.000)
 *                      thì cảnh báo sai mọi dòng.
 *  Nhóm này cần biên theo từng nội tệ; chưa đủ dữ liệu để chốt nên tạm không cảnh báo còn hơn
 *  cảnh báo bừa (xem [[entry-bounds]]).
 */
export type PurchaseValues = {
  latex_wet?: number | null;
  coagulum?: number | null;
  price_latex_vnd?: number | null;
  price_cup_vnd?: number | null;
  finished?: { grade?: string; qty?: number | null; price?: number | null;
               ccy?: string; fx?: number | null }[];
};

/** Toàn bộ cảnh báo của biểu THU MUA. */
export function purchaseWarnings(d: PurchaseValues): EntryWarning[] {
  const finished = (d.finished ?? []).flatMap((ln, i) => {
    const at = `Thu mua thành phẩm · dòng ${i + 1}`;
    return keep([
      { where: `${at} · Sản lượng`, message: boundWarning(ln.qty, TONNES_DAILY) },
      { where: `${at} · Đơn giá`, message: boundWarning(ln.price, priceBound(ln.ccy, ln.grade)) },
      { where: `${at} · Tỷ giá`, message: fxWarning(ln) ?? boundWarning(ln.fx, FX_USD_VND) },
    ]);
  });
  return [
    ...keep([
      { where: "Mủ nước · Sản lượng thu mua", message: boundWarning(d.latex_wet, TONNES_DAILY) },
      { where: "Mủ nước · Đơn giá thu mua", message: boundWarning(d.price_latex_vnd, PRICE_LATEX) },
      { where: "Mủ chén · Sản lượng thu mua", message: boundWarning(d.coagulum, TONNES_DAILY) },
      { where: "Mủ chén · Đơn giá thu mua", message: boundWarning(d.price_cup_vnd, PRICE_CUP) },
    ]),
    ...finished,
  ];
}

/** Cảnh báo của bảng chỉ tiêu KẾ HOẠCH NĂM (số cả năm nên biên riêng, rộng hơn hẳn số ngày). */
export function yearPlanWarnings(
  rows: { company: string; plan_tonnes?: number | null; signed_lt_tonnes?: number | null }[],
): EntryWarning[] {
  return rows.flatMap((r) => keep([
    { where: `${r.company} · Kế hoạch thu mua`, message: boundWarning(r.plan_tonnes, TONNES_YEAR) },
    { where: `${r.company} · Đã ký HĐ dài hạn`, message: boundWarning(r.signed_lt_tonnes, TONNES_YEAR) },
  ]));
}
