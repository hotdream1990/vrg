/* So sánh giá trị TRƯỚC / SAU của 1 dòng nhật ký → danh sách ô đã đổi, có nhãn tiếng Việt.

   Payload mỗi nhóm số liệu một khác (số đơn lẻ, jsonb lồng nhau, mảng dòng) nên làm phẳng
   về dạng đường dẫn (`sales[0].qty`) rồi so từng ô — 1 cách dùng cho mọi nhóm. */

import { COLUMNS } from "./unit-daily-fields";

export type FieldChange = { path: string; label: string; from: unknown; to: unknown };

/** Nhãn ô báo cáo tiêu thụ–tồn kho: lấy lại từ nguồn khai báo cột (không khai trùng). */
const UNIT_DAILY_LABELS: Record<string, string> = Object.fromEntries(
  [...COLUMNS.purchase, ...COLUMNS.consumption].map((c) => [c.key, c.label]),
);

/** Nhãn các ô dùng chung ở nhiều nhóm số liệu. Không có trong bảng → hiện đúng tên khoá gốc. */
const LABELS: Record<string, string> = {
  price: "Đơn giá", currency: "Loại tiền", unit: "Đơn vị tính", contract: "Kỳ hạn",
  qty: "Số lượng", grade: "Chủng loại", code: "Số HĐ/PL", ccy: "Loại tiền", fx: "Tỷ giá",
  ton_kho: "Tồn kho thành phẩm", ton_kho_hd: "Tồn kho đã có hợp đồng",
  note: "Ghi chú", content: "Nội dung", source: "Nguồn",
  fob_usd: "Giá FOB (USD)", domestic_vnd: "Giá nội địa (VNĐ)", title: "Tiêu đề",
  dispatch_no: "Số công văn", dispatch_summary: "Trích yếu công văn",
  as_of: "Ngày", start_date: "Ngày bắt đầu tồn kho", delivery_date: "Lịch giao",
  delivered_date: "Ngày giao thực tế", filename: "File đính kèm",
  plan_tonnes: "Kế hoạch thu mua năm", signed_lt_tonnes: "SL đã ký HĐ dài hạn",
  carry_lt_tonnes: "Chuyển sang (HĐ dài hạn)", carry_spot_tonnes: "Chuyển sang (HĐ chuyến)",
  full_name: "Họ tên", role: "Vai trò", is_active: "Đang hoạt động",
  permissions: "Quyền", member_units: "Đơn vị được gán", value: "Giá trị",
  hour: "Giờ chạy", minute: "Phút chạy", enabled: "Bật", order: "Thứ tự",
  rows: "Số bản ghi", sources: "Nguồn dữ liệu", dates: "Ngày",
  ...UNIT_DAILY_LABELS,
};

/** `sales[0].qty` → "Số lượng" (lấy nhãn của đoạn cuối); giữ tiền tố mảng để biết dòng nào. */
export function fieldLabel(path: string): string {
  const last = path.split(".").pop() ?? path;
  const key = last.replace(/\[\d+\]$/, "");
  const idx = last.match(/\[(\d+)\]$/);
  const base = LABELS[key] ?? key;
  return idx ? `${base} (dòng ${Number(idx[1]) + 1})` : base;
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

/** Làm phẳng object/array lồng nhau → { 'đường.dẫn': giá trị nguyên thuỷ }. */
function flatten(value: unknown, prefix = "", out: Record<string, unknown> = {}): Record<string, unknown> {
  if (Array.isArray(value)) {
    value.forEach((v, i) => flatten(v, `${prefix}[${i}]`, out));
  } else if (isObject(value)) {
    for (const [k, v] of Object.entries(value)) flatten(v, prefix ? `${prefix}.${k}` : k, out);
  } else if (prefix) {
    out[prefix] = value;
  }
  return out;
}

const isEmpty = (v: unknown) => v === null || v === undefined || v === "";

/** Ô quan trọng lên trước (Postgres lưu jsonb không giữ thứ tự khoá nên phải tự sắp). */
const PRIORITY = [
  "price", "fob_usd", "domestic_vnd", "ton_kho", "ton_kho_hd", "plan_tonnes",
  "qty", "content", "value", "grade", "code", "role", "is_active",
];
const rank = (path: string): number => {
  const key = (path.split(".").pop() ?? path).replace(/\[\d+\]$/, "");
  const i = PRIORITY.indexOf(key);
  if (i >= 0) return i;
  return ["as_of", "source", "ingested_at"].includes(key) ? 900 : 500;  // ô ngữ cảnh xuống cuối
};

/** Các ô KHÁC nhau giữa trước/sau (bỏ ô cùng trống). Thêm mới/xoá → liệt kê 1 phía. */
export function diffFields(before: unknown, after: unknown): FieldChange[] {
  const a = flatten(before);
  const b = flatten(after);
  const paths = [...new Set([...Object.keys(a), ...Object.keys(b)])];
  const changes: FieldChange[] = [];
  for (const path of paths) {
    const from = a[path];
    const to = b[path];
    if (from === to || (isEmpty(from) && isEmpty(to))) continue;
    changes.push({ path, label: fieldLabel(path), from, to });
  }
  return changes.sort((x, y) => rank(x.path) - rank(y.path) || x.path.localeCompare(y.path));
}

/** Giá trị hiển thị: số theo chuẩn VN, true/false → Có/Không, trống → "(trống)". */
export function fmtValue(v: unknown): string {
  if (isEmpty(v)) return "(trống)";
  if (typeof v === "boolean") return v ? "Có" : "Không";
  if (typeof v === "number") return v.toLocaleString("vi-VN", { maximumFractionDigits: 4 });
  return String(v);
}

/** Tóm tắt 1 dòng theo loại thao tác — nêu GIÁ TRỊ 2 ô đầu rồi liệt kê TÊN các ô còn lại
 *  (thay vì "+N ô khác" chung chung, để đọc log biết ngay đổi những ô nào):
 *  sửa   → "Đơn giá: 385 → 405 · Loại tiền · Đơn vị tính"
 *  thêm  → "Đơn giá: 385 · Loại tiền: VND · Đơn vị tính"  (chưa có gì trước đó nên bỏ mũi tên)
 *  xoá   → "Đơn giá: 405 · Loại tiền: VND · Đơn vị tính"  (số đã bị xoá) */
export function summarize(changes: FieldChange[], action = "update", max = 2): string {
  if (!changes.length) return "";
  const one = (c: FieldChange) => {
    if (action === "create") return `${c.label}: ${fmtValue(c.to)}`;
    if (action === "delete") return `${c.label}: ${fmtValue(c.from)}`;
    return `${c.label}: ${fmtValue(c.from)} → ${fmtValue(c.to)}`;
  };
  const head = changes.slice(0, max).map(one).join(" · ");
  const extra = changes.slice(max);
  if (!extra.length) return head;
  // Nêu TÊN các ô còn lại (cap 4 cho gọn; dư nữa mới gộp số) — rõ hơn "+N ô khác".
  const names = extra.slice(0, 4).map((c) => c.label).join(" · ");
  const more = extra.length - 4;
  return `${head} · ${names}${more > 0 ? ` · +${more} ô` : ""}`;
}
