/* So sánh 3 phía của một ĐỀ NGHỊ SỬA SỐ LIỆU: lúc gửi (`before`) · hiện tại (`current`) · đề nghị (`payload`).

   `before`/`current` và `payload` KHÁC hình dạng theo op (api-contract §2) nên trước hết chiếu cả ba
   về cùng một khuôn, rồi làm phẳng thành đường dẫn (`fields.finished[1].qty`) để so từng ô.
   Nhãn tiếng Việt tái dùng bảng nhãn của Nhật ký hoạt động (`audit-diff`) — thiếu thì hiện khoá gốc. */

import { fieldLabel, fmtValue } from "./audit-diff";
import { dmy } from "./date";
import type { EditRequest, EditRequestOp } from "./edit-request-client";
import { labelDemandCodes } from "./market-demand-meta";
import { SALE_DATES, SALE_DOCS } from "./unit-daily-consumption";
import { CUP_PRICE_UNIT, LACE_PRICE_UNIT, LATEX_PRICE_UNIT } from "./purchase-price-unit";
import { COLUMNS } from "./unit-daily-fields";
import { PLAN_LABELS } from "../features/command-center/pages/year-plan-fields";

type Obj = Record<string, unknown>;

/** Một file đính kèm nằm trong số liệu — hiện tên file + mở được. */
export type FileLeaf = { kind: "file"; file: string; filename: string };
/** Đơn giá 0 trong đề nghị biểu Thu mua = XOÁ ô giá — so như ô trống, hiện "(xoá)". */
export type ClearLeaf = { kind: "clear" };
const CLEAR: ClearLeaf = { kind: "clear" };

export type DiffRow = {
  path: string;
  label: string;
  before: unknown;
  current: unknown;
  proposed: unknown;
  /** Ô đề nghị khác hiện tại (hoặc khác lúc gửi khi không có cột hiện tại) → tô nổi. */
  highlight: boolean;
};

/** Nhãn dùng chung mọi op — bổ sung cho audit-diff. */
const COMMON_LABELS: Record<string, string> = {
  company: "Đơn vị", lines: "Dòng hàng", qty_dry: "Quy khô",
};

/** Nhãn biểu ngày — CHỈ áp cho op biểu ngày: `revenue`, `consumption`… trùng tên khoá của hợp đồng. */
const DAILY_LABELS: Record<string, string> = {
  // 3 cột cùng tên "Sản lượng thu mua" (mủ nước/chén/dây) → kèm tên nhóm cột cho khỏi nhầm.
  ...Object.fromEntries([...COLUMNS.purchase, ...COLUMNS.consumption]
    .map((c) => [c.key, c.group ? `${c.group} · ${c.label}` : c.label])),
  purchase: `Đơn giá mủ nước (${LATEX_PRICE_UNIT})`,
  purchase_cup: `Đơn giá mủ chén (${CUP_PRICE_UNIT})`,
  purchase_lace: `Đơn giá mủ dây (${LACE_PRICE_UNIT})`,
  finished: "Thu mua thành phẩm", sales: "Tiêu thụ mủ thu mua", sales_own: "Tiêu thụ mủ khai thác",
  stock_not_warehoused: "Chế biến chưa nhập kho", stock_warehoused: "Đã nhập kho",
  no_stock: "Không phát sinh tồn kho",
  ...Object.fromEntries(SALE_DOCS.map((d) => [d.listKey, d.label])),
  ...Object.fromEntries(SALE_DATES.map((d) => [d.key, d.label])),
};

/** Nhãn hợp đồng / đợt giao. */
const CONTRACT_LABELS: Record<string, string> = {
  customer_id: "Khách hàng", parent_id: "Hợp đồng gốc", master_id: "Hợp đồng mẹ",
  delivery_type: "Hình thức giao", contract_type: "Loại hợp đồng", sign_date: "Ngày ký",
  expiry_date: "Ngày hết hạn", start_date: "Ngày mở đợt", delivered_at: "Ngày giao",
  channel: "Hình thức tiêu thụ", to_company: "Đơn vị nhận nội bộ", source: "Nguồn tiêu thụ",
  invoice_no: "Số hoá đơn", invoice_docs: "Hoá đơn", payment_date: "Ngày thanh toán",
  payment_qty: "Sản lượng thanh toán",
  payment_docs: "Chứng từ thanh toán", files: "Bộ hợp đồng", completed_at: "Ngày hoàn thành",
  certs: "Chứng chỉ", premium: "Premium", premium_ccy: "Loại tiền premium",
};

/** Mã loại giao → chữ (khớp `DELIVERY_TYPES` ở server, bỏ phần giải thích trong ngoặc). */
const DELIVERY_TYPE_NAMES: Record<string, string> = {
  single: "Giao 1 lần", multi: "Giao nhiều lần",
};
const deliveryLabel = (v: unknown): unknown =>
  (typeof v === "string" ? DELIVERY_TYPE_NAMES[v] ?? v : v);

/** Nhãn dự phòng khi KHÔNG có bảng nhãn server gửi (màn đề nghị của ĐƠN VỊ) — theo khoá cuối của
 *  đường dẫn, nên áp cho cả `source` cấp bản ghi lẫn `lines[i].source`. Khớp `CONSUMPTION_SOURCES`
 *  ở server; trang duyệt vẫn ưu tiên nhãn server. */
const FALLBACK_VALUE_NAMES: Record<string, Record<string, string>> = {
  source: { exploit: "Khai thác", purchase: "Thu mua", goods: "Hàng hóa cao su" },
};

/** Nguồn tiêu thụ nằm ở TỪNG DÒNG (05/10/2026); ô `source` cấp bản ghi chỉ là nguồn chung server
 *  tự tính (form mới gửi null) → so nó là hiện dòng "Nguồn tiêu thụ: Khai thác → (trống)" gây hiểu
 *  nhầm, nên bỏ khỏi so sánh khi các dòng đã mang nguồn. Đề nghị gửi từ bản web CŨ chỉ có nguồn ở
 *  cấp bản ghi → điền nó xuống dòng chưa có nguồn, đúng như server làm khi duyệt (`default_source`),
 *  để bảng không báo oan "Dòng hàng N · Nguồn: Thu mua → (trống)". */
function normalizeLineSource(p: Obj): Obj {
  if (!Array.isArray(p.lines)) return p;
  const fill = typeof p.source === "string" && p.source ? p.source : null;
  const lines = fill
    ? p.lines.map((l) => (isObj(l) && !l.source ? { ...l, source: fill } : l))
    : p.lines;
  if (!lines.some((l) => isObj(l) && l.source)) return p;
  const { source: _s, ...rest } = p;
  return { ...rest, lines };
}

/** Nhãn nhu cầu thị trường — phần còn lại (khách hàng, giao tại, thời gian giao, kết quả…) lấy từ audit-diff. */
const DEMAND_LABELS: Record<string, string> = { as_of: "Ngày nhận", currency: "Đơn vị giá" };

const isDailyOp = (op: EditRequestOp) => op === "daily_report" || op === "daily_move";

const opLabels = (op: EditRequestOp): Record<string, string> => {
  if (isDailyOp(op)) return DAILY_LABELS;
  if (op.startsWith("contract_")) return CONTRACT_LABELS;
  if (op.startsWith("demand_")) return DEMAND_LABELS;
  if (op === "year_plan") return PLAN_LABELS;
  return {};
};

/** Khoá kỹ thuật / số hệ thống tự tính — không đưa ra so sánh. `file`, `filename`… phẳng là bản
 *  sao tương thích ngược của danh sách file (file thật đã hiện qua `FileLeaf`); `delivered` suy từ `delivered_at`. */
const IGNORED = new Set([
  "id", "updated_at", "updated_by", "created_at", "created_by", "stock_signed_undelivered", "delivered",
  "file", "filename", "wh_file", "wh_filename", "inv_file", "inv_filename",
]);

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const asObj = (v: unknown): Obj | null => (isObj(v) ? v : null);

const isFileDoc = (v: Obj): boolean =>
  typeof v.file === "string" && Object.keys(v).every((k) => ["file", "filename", "size"].includes(k));

function flatten(value: unknown, prefix = "", out: Obj = {}): Obj {
  if (Array.isArray(value)) {
    value.forEach((v, i) => flatten(v, `${prefix}[${i}]`, out));
  } else if (isObj(value)) {
    if (prefix && value === CLEAR) { out[prefix] = value; return out; }
    if (prefix && isFileDoc(value)) {
      out[prefix] = { kind: "file", file: value.file, filename: (value.filename as string) || value.file } as FileLeaf;
      return out;
    }
    for (const [k, v] of Object.entries(value)) {
      if (!IGNORED.has(k)) flatten(v, prefix ? `${prefix}.${k}` : k, out);
    }
  } else if (prefix) {
    out[prefix] = value;
  }
  return out;
}

/** Chiếu bản ghi về khuôn so sánh được theo op. `side` = before/current hay payload. */
function project(req: Pick<EditRequest, "op" | "payload">, o: Obj | null, side: "record" | "payload"): Obj | null {
  const p = req.payload;
  switch (req.op) {
    case "daily_report":
      return side === "payload"
        ? { fields: p.fields ?? null, prices: clearZeroPrices(asObj(p.prices)) }
        : o && { fields: o.fields ?? null, prices: pickKeys(asObj(o.prices), asObj(p.prices)) };
    case "daily_move":
      return side === "payload" ? { as_of: p.to_date } : { as_of: o?.fields ? p.as_of : null };
    case "contract_save": {
      // Bản ghi lưu có thêm số suy ra (qty, revenue…) — chỉ so các khoá đơn vị gửi lên.
      const body = normalizeLineSource(p);
      return withSignDefault(side === "payload" ? body : pickKeys(o, body));
    }
    case "contract_delete":
      return side === "payload" ? null : withSignDefault(o);
    case "contract_delivery_type":
      // Chỉ một ô đổi — so nguyên bản ghi thì bảng đầy những dòng không liên quan. Đổi mã sang
      // chữ ngay ở đây (như nhu cầu thị trường) để màn của ĐƠN VỊ cũng đọc được, không phụ thuộc
      // bảng nhãn mà chỉ trang duyệt mới có.
      return side === "payload"
        ? { delivery_type: deliveryLabel(p.delivery_type) }
        : o && { delivery_type: deliveryLabel(o.delivery_type) };
    case "demand_save":
      // Bản ghi có thêm legacy/created_*… — chỉ so các khoá của thân PUT; mã → nhãn cho dễ đọc.
      return labelDemandCodes(side === "payload" ? p : pickKeys(o, p));
    case "demand_delete":
      return side === "payload" ? null : labelDemandCodes(o);
    case "year_plan": {
      // Chỉ so các ô kế hoạch có trong đề nghị (năm + đơn vị là khoá, không phải số liệu).
      const { year: _y, company: _c, ...values } = p;
      return side === "payload" ? values : pickKeys(o, values);
    }
  }
}

/** Dòng HỢP ĐỒNG không khai "Hiệu lực từ" = theo ngày ký → ghi thành chữ, để bảng so sánh đọc là
 *  "15/09/2026 → Theo ngày ký" thay vì "(trống)" (người duyệt không biết trống nghĩa là gì). Chỉ điền
 *  cho dòng CÓ ở bản ghi đó — dòng mới thêm thì bên "trước" vẫn là trống. Đợt giao không có ô này. */
function withSignDefault(o: Obj | null): Obj | null {
  if (!o || o.parent_id || !Array.isArray(o.lines)) return o;
  return {
    ...o,
    lines: o.lines.map((l) => (isObj(l) ? { ...l, from_date: l.from_date || SIGN_DATE_TEXT } : l)),
  };
}
const SIGN_DATE_TEXT = "Theo ngày ký";

/** Đơn giá 0 = xoá ô giá (luật `upsert_record`) → đổi thành dấu XOÁ để so như trống. */
function clearZeroPrices(prices: Obj | null): Obj | null {
  if (!prices) return null;
  return Object.fromEntries(Object.entries(prices).map(([k, v]) => [k, v === 0 ? CLEAR : v]));
}

/** Giữ các khoá của `src` có mặt trong `keysOf` (giá thu mua: chỉ khoá gửi lên mới ghi). */
function pickKeys(src: Obj | null, keysOf: Obj | null): Obj | null {
  if (!src || !keysOf) return null;
  return Object.fromEntries(Object.keys(keysOf).map((k) => [k, src[k] ?? null]));
}

const norm = (v: unknown): string | null => {
  if (v === null || v === undefined || v === "" || v === CLEAR) return null;
  if (isObj(v) && (v as FileLeaf).kind === "file") return `file:${(v as FileLeaf).file}`;
  return String(v);
};
const same = (a: unknown, b: unknown) => norm(a) === norm(b);

/** Nhãn đường dẫn: bỏ tiền tố `fields.`/`prices.`, nối nhãn từng đoạn — `sales[1].qty` → "Tiêu thụ mủ thu mua 2 · Số lượng". */
export function diffLabel(path: string, op: EditRequestOp): string {
  const segs = path.split(".");
  if (segs.length > 1 && (segs[0] === "fields" || segs[0] === "prices")) segs.shift();
  const extra = opLabels(op);
  return segs.map((seg) => {
    const m = seg.match(/^(.*?)(?:\[(\d+)\])?$/);
    const key = m?.[1] ?? seg;
    const name = extra[key] ?? COMMON_LABELS[key] ?? fieldLabel(key);
    return m?.[2] != null ? `${name} ${Number(m[2]) + 1}` : name;
  }).join(" · ");
}

/** Các dòng khác biệt. `withCurrent` = trang duyệt (3 cột); không có = đơn vị xem (lúc gửi ↔ đề nghị). */
export function buildEditRequestDiff(
  req: Pick<EditRequest, "op" | "payload" | "before">, current?: Obj | null, withCurrent = false,
): DiffRow[] {
  const b = flatten(project(req, req.before, "record"));
  const c = withCurrent ? flatten(project(req, current ?? null, "record")) : {};
  const p = flatten(project(req, null, "payload"));
  const paths = [...new Set([...Object.keys(b), ...Object.keys(c), ...Object.keys(p)])];
  const rows: DiffRow[] = [];
  for (const path of paths) {
    const differs = !same(b[path], p[path]) || (withCurrent && (!same(c[path], p[path]) || !same(b[path], c[path])));
    if (!differs) continue;
    rows.push({
      path, label: diffLabel(path, req.op), before: b[path], current: c[path], proposed: p[path],
      highlight: !same(withCurrent ? c[path] : b[path], p[path]),
    });
  }
  return rows;
}

/** Giá trị hiển thị: nhãn server tra sẵn (`labels[khoá cuối][giá trị]`, vd id khách → tên khách),
 *  thiếu thì nhãn dự phòng (mã nguồn tiêu thụ) · dấu XOÁ → "(xoá)" · ngày ISO → dd/mm/yyyy · số kiểu
 *  vi-VN · còn lại theo `fmtValue`. */
export function displayValue(v: unknown, path?: string, labels?: Record<string, Record<string, string>>): string {
  if (v === CLEAR) return "(xoá)";
  const key = path?.split(".").pop()?.replace(/\[\d+\]$/, "");
  const named = key && v != null && v !== ""
    ? labels?.[key]?.[String(v)] ?? FALLBACK_VALUE_NAMES[key]?.[String(v)]
    : undefined;
  if (named) return named;
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)) return dmy(v);
  return fmtValue(v);
}

export const isFileLeaf = (v: unknown): v is FileLeaf => isObj(v) && (v as FileLeaf).kind === "file";
