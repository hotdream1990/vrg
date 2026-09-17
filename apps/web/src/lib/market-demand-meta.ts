/* Danh mục · định dạng · luật kiểm tra phía web cho Nhu cầu thị trường (api-contract §2, §3, §7) —
   bản rút gọn 17/09/2026: thời gian giao và kết quả là ô chữ tự do.
   Kiểm tra ở đây chỉ để BÁO SỚM cho người nhập — server vẫn là hàng rào thật. */

import { dmy } from "./date";
import type {
  DemandCurrency, DemandItem, DemandItemInput, DemandQtyUnit,
} from "./market-demand-client";

type Option<T extends string> = { value: T; label: string };

export const QTY_UNITS: Option<DemandQtyUnit>[] = [
  { value: "ton", label: "tấn" },
  { value: "container", label: "container" },
];

export const CURRENCIES: Option<DemandCurrency>[] = [
  { value: "VND", label: "triệu đồng/tấn" },
  { value: "USD", label: "USD/tấn" },
];

/** Hậu tố gọn trong bảng: "40 triệu đ/tấn" · "2.380 USD/tấn". */
const PRICE_SUFFIX: Record<DemandCurrency, string> = { VND: "triệu đ/tấn", USD: "USD/tấn" };
/** Trần đơn giá — vượt là gần như chắc nhập sai đơn vị tính (vd gõ 40.000.000 thay vì 40). */
const PRICE_CAP: Record<DemandCurrency, number> = { VND: 1000, USD: 20000 };
/** Cùng giới hạn với server (`market_demand_meta.*_MAX`). */
const MAX_LEN = { customer: 200, delivery_place: 200, delivery_time: 200, result: 500, note: 2000 };

export const DEFAULT_DELIVERY_PLACE = "Tại kho";

/** Tên đơn vị gọn cho cột bảng (bỏ loại hình doanh nghiệp) — tên đầy đủ vẫn hiện khi rê chuột. */
export const shortUnit = (name: string): string =>
  name.replace(/^Công ty\s+(Cổ phần|TNHH\s+MTV|TNHH)?\s*/i, "").trim() || name;

const labelOf = <T extends string>(list: Option<T>[], v: T): string =>
  list.find((x) => x.value === v)?.label ?? v;

export const qtyUnitLabel = (u: DemandQtyUnit) => labelOf(QTY_UNITS, u);
export const currencyLabel = (c: DemandCurrency) => labelOf(CURRENCIES, c);

const num = (v: number) => v.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** "100 tấn" · "3 container" · trống → "—". */
export const fmtQty = (i: Pick<DemandItemInput, "qty" | "qty_unit">): string =>
  (i.qty == null ? "—" : `${num(i.qty)} ${qtyUnitLabel(i.qty_unit)}`);

/** "40 triệu đ/tấn" · "2.380 USD/tấn" · trống → "—". */
export const fmtPrice = (i: Pick<DemandItemInput, "price" | "currency">): string =>
  (i.price == null ? "—" : `${num(i.price)} ${PRICE_SUFFIX[i.currency] ?? i.currency}`);

type LabelFields = Pick<DemandItemInput, "customer" | "grade" | "as_of">;

/** "Công ty A · LATEX ngày 17/09/2026" — nhận diện một phiếu trong câu hỏi/tiêu đề. */
export const demandLabel = (v: LabelFields): string =>
  `${v.customer.trim()} · ${v.grade} ngày ${dmy(v.as_of)}`;

/** Tiêu đề đề nghị sửa (api-contract §5): "Nhu cầu …" / "Xoá nhu cầu …". */
export const demandTitle = (v: LabelFields, remove = false): string =>
  `${remove ? "Xoá nhu cầu" : "Nhu cầu"} ${demandLabel(v)}`;

export const emptyDemand = (company: string, today: string): DemandItemInput => ({
  id: null, company, as_of: today, customer: "", grade: "",
  qty: null, qty_unit: "ton", price: null, currency: "VND",
  delivery_place: "", delivery_time: "", result: "", note: "",
});

/** Đúng thân PUT — bỏ các ô chỉ-đọc server trả kèm (legacy, created_*, updated_*). */
export const toDemandInput = (i: DemandItem): DemandItemInput => ({
  id: i.id, company: i.company, as_of: i.as_of, customer: i.customer, grade: i.grade,
  qty: i.qty, qty_unit: i.qty_unit, price: i.price, currency: i.currency,
  delivery_place: i.delivery_place, delivery_time: i.delivery_time ?? "",
  result: i.result ?? "", note: i.note,
});

/** Nhân bản: phiếu MỚI nhận hôm nay, cùng nội dung (khách hàng, nơi giao, thời gian giao…) nhưng
 *  chưa có kết quả — kết quả thuộc về phiếu gốc. */
export const cloneDemand = (i: DemandItem, company: string, today: string): DemandItemInput => ({
  ...toDemandInput(i), id: null, company, as_of: today, result: "",
});

/** Chuẩn hoá trước khi gửi: bỏ khoảng trắng thừa ở mọi ô chữ (server cũng làm vậy — làm luôn ở đây
 *  để bảng so sánh của đề nghị sửa không hiện ô "đổi" giả). */
export function normalizeDemand(v: DemandItemInput): DemandItemInput {
  return {
    ...v,
    customer: v.customer.trim(),
    delivery_place: v.delivery_place.trim(),
    delivery_time: v.delivery_time.trim(),
    result: v.result.trim(),
    note: v.note.trim(),
  };
}

/** Luật §3 — trả câu báo lỗi đầu tiên, hoặc null khi hợp lệ. `today` = ngày server (YYYY-MM-DD). */
export function validateDemand(raw: DemandItemInput, today: string): string | null {
  const v = normalizeDemand(raw);
  if (!v.company) return "Chọn đơn vị.";
  if (!v.as_of) return "Chọn ngày nhận nhu cầu.";
  if (v.as_of > today) return "Ngày nhận không được sau hôm nay.";
  if (!v.customer) return "Nhập tên khách hàng.";
  if (v.customer.length > MAX_LEN.customer) return `Tên khách hàng tối đa ${MAX_LEN.customer} ký tự.`;
  if (!v.grade) return "Chọn chủng loại.";
  if (v.qty != null && v.qty < 0) return "Số lượng không được âm.";
  if (v.price != null && v.price < 0) return "Đơn giá không được âm.";
  if (v.price != null && v.price > PRICE_CAP[v.currency]) {
    // Cùng câu với server (`market_demand_meta.PRICE_CAP_MESSAGE`) — một lỗi, một câu báo.
    return v.currency === "VND"
      ? `Đơn giá tính bằng TRIỆU đồng/tấn (vd 40 = 40 triệu) — tối đa ${num(PRICE_CAP.VND)}.`
      : `Đơn giá tính bằng USD/tấn (vd 2380 = 2.380 USD/tấn) — tối đa ${num(PRICE_CAP.USD)}.`;
  }
  if (v.delivery_place.length > MAX_LEN.delivery_place) return `Nơi giao tối đa ${MAX_LEN.delivery_place} ký tự.`;
  if (v.delivery_time.length > MAX_LEN.delivery_time) {
    return `Thời gian giao tối đa ${MAX_LEN.delivery_time} ký tự.`;
  }
  if (v.result.length > MAX_LEN.result) return `Kết quả tối đa ${MAX_LEN.result} ký tự.`;
  if (v.note.length > MAX_LEN.note) return `Ghi chú tối đa ${MAX_LEN.note} ký tự.`;
  return null;
}

export const DEMAND_MAX_LEN = MAX_LEN;

/** Mã → nhãn (đơn vị số lượng, đơn vị giá) cho bảng so sánh đề nghị sửa. Đổi cả hai phía nên vẫn so
 *  đúng. Chỉ dùng cho op nhu cầu: `currency`… trùng tên khoá ở nhóm số liệu khác. */
export function labelDemandCodes(o: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!o) return null;
  const out = { ...o };
  if (typeof o.qty_unit === "string") out.qty_unit = qtyUnitLabel(o.qty_unit as DemandQtyUnit);
  if (typeof o.currency === "string") out.currency = currencyLabel(o.currency as DemandCurrency);
  return out;
}

/** Gợi ý cho ô gõ tự do (khách hàng, nơi giao): giá trị đã có, khớp chữ đang gõ. Trùng nhau chỉ khác
 *  hoa/thường thì giữ cách viết gặp trước (nơi giao: "Tại kho" đứng đầu nguồn). */
export function suggest(pool: string[], typed: string, limit = 12): { value: string }[] {
  const t = typed.trim().toLowerCase();
  const seen = new Map<string, string>();
  for (const s of pool.map((x) => x.trim()).filter(Boolean)) {
    if (!seen.has(s.toLowerCase())) seen.set(s.toLowerCase(), s);
  }
  return [...seen.values()]
    .filter((s) => s.toLowerCase() !== t && s.toLowerCase().includes(t))
    .sort((a, b) => a.localeCompare(b, "vi"))
    .slice(0, limit)
    .map((value) => ({ value }));
}
