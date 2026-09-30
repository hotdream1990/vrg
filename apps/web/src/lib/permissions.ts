/* Quyền theo mục dữ liệu (phân quyền chuyên viên nhập liệu). Khớp backend app/core/permissions.py.
   admin = tất cả (mức Sửa) · executive (Lãnh đạo Tập đoàn) = EXECUTIVE_CAPS mức Xem ·
   editor = theo danh sách · viewer (Người xem) = không có mục nào.

   Hai cấp: các mục NHẬP LIỆU (SPLIT_CAPS) tách Xem / Sửa. Dạng lưu trong `permissions`:
     "physical"       → mức Sửa (xem + nhập/sửa/xoá)
     "physical:view"  → mức Xem (chỉ đọc)
   Mục ngoài SPLIT_CAPS (màn phân tích/bản tin) chỉ 1 cấp — luôn quy về Sửa.
   Key trần = mức Sửa nên dữ liệu cũ giữ nguyên quyền (không cần migration). */

export type Cap =
  | "market_quote" | "raw_material" | "floor" | "physical"
  | "inventory" | "member_unit" | "auto_data" | "market_demand" | "unit_daily"
  | "sales_contract" | "edit_request"
  | "floor_suggest" | "bulletin_daily" | "bulletin_weekly" | "market_movement" | "assistant"
  | "support" | "audit" | "smart_factory";

export type CapLevel = "view" | "edit";

/** Danh sách quyền + nhãn hiển thị (trang Quản trị người dùng, theo thứ tự này). */
export const DATA_CAPS: { key: Cap; label: string; hint?: string }[] = [
  { key: "market_quote", label: "Báo giá mủ thị trường", hint: "gồm Mục 6 giá mủ tư nhân" },
  { key: "raw_material", label: "Giá mủ nguyên liệu" },
  { key: "floor", label: "Giá sàn Tập đoàn" },
  { key: "physical", label: "Giá Physical" },
  { key: "inventory", label: "Tồn kho" },
  { key: "member_unit", label: "Đơn vị thành viên" },
  { key: "auto_data", label: "Số liệu tự động", hint: "Bảng tính giá các sàn · Tỷ giá · Quét đa sàn" },
  { key: "market_demand", label: "Nhu cầu thị trường", hint: "nhu cầu của mọi đơn vị" },
  { key: "unit_daily", label: "Báo cáo đơn vị theo ngày", hint: "thu mua · tồn kho (mọi đơn vị)" },
  { key: "sales_contract", label: "Hợp đồng & khách hàng", hint: "hợp đồng · đợt giao · danh mục khách (mọi đơn vị)" },
  { key: "edit_request", label: "Duyệt đề nghị sửa số liệu của đơn vị", hint: "nhận email · duyệt/từ chối đề nghị sửa ngày đã khoá" },
  { key: "floor_suggest", label: "Gợi ý giá sàn", hint: "màn phân tích" },
  { key: "bulletin_daily", label: "Bản tin ngày", hint: "màn phân tích" },
  { key: "bulletin_weekly", label: "Báo cáo tuần", hint: "màn phân tích" },
  { key: "market_movement", label: "Bản tin biến động", hint: "màn phân tích" },
  { key: "assistant", label: "Trợ lý AI", hint: "hỏi đáp số liệu + tư vấn giá sàn" },
  { key: "support", label: "Hỗ trợ & Thông báo", hint: "hộp thư với lãnh đạo đơn vị + nhắc lịch" },
  { key: "audit", label: "Nhật ký hoạt động + Lịch sử truy cập", hint: "xem vết chỉnh sửa số liệu và lịch sử đăng nhập/vào trang của mọi người dùng" },
  { key: "smart_factory", label: "Nhà máy thông minh", hint: "chỉ số điện · nước · số bành từ SCADA" },
];

export const CAP_KEYS: Cap[] = DATA_CAPS.map((c) => c.key);
const CAP_SET = new Set<string>(CAP_KEYS);

/** Các mục nhập liệu có tách 2 cấp Xem/Sửa (khớp SPLIT_CAPS ở backend). */
export const SPLIT_CAPS = new Set<Cap>([
  "market_quote", "raw_material", "floor", "physical", "inventory",
  "member_unit", "auto_data", "market_demand", "unit_daily", "sales_contract", "support",
]);

/** Lãnh đạo Tập đoàn: mọi mục nghiệp vụ ở mức Xem — bỏ danh mục đơn vị, hộp thư, nhật ký
 *  (khớp EXECUTIVE_CAPS ở backend). */
export const EXECUTIVE_CAPS = new Set<Cap>([
  "market_quote", "raw_material", "floor", "physical", "inventory", "auto_data",
  "market_demand", "unit_daily", "sales_contract",
  "floor_suggest", "bulletin_daily", "bulletin_weekly", "market_movement", "assistant",
  "smart_factory",
]);

/** Mục này có cho chọn mức Xem riêng không (false = chỉ 1 cấp, luôn là Sửa). */
export const isSplitCap = (key: Cap): boolean => SPLIT_CAPS.has(key);

/** Gom quyền thành nhóm cho UI cấp quyền (theo cấu trúc menu — đỡ rối). */
export const CAP_GROUPS: { title: string; keys: Cap[] }[] = [
  { title: "Số liệu thị trường (tự động)", keys: ["auto_data"] },
  { title: "Số liệu thị trường (thủ công)", keys: ["market_quote", "raw_material", "floor", "physical", "inventory"] },
  { title: "Số liệu đơn vị thành viên", keys: ["member_unit", "unit_daily", "market_demand", "edit_request"] },
  { title: "Quản lý hợp đồng", keys: ["sales_contract"] },
  { title: "Nhà máy thông minh", keys: ["smart_factory"] },
  { title: "Phân tích & Bản tin", keys: ["floor_suggest", "bulletin_daily", "bulletin_weekly", "market_movement", "assistant"] },
  { title: "Hỗ trợ đơn vị thành viên", keys: ["support"] },
  { title: "Giám sát", keys: ["audit"] },
];

const RANK: Record<string, number> = { view: 1, edit: 2 };

/** `"physical:view"` → `["physical","view"]`. Key trần → mức Sửa. Sai định dạng → null. */
export function parseCap(entry: string): [Cap, CapLevel] | null {
  const idx = entry.indexOf(":");
  const key = idx < 0 ? entry : entry.slice(0, idx);
  const suffix = idx < 0 ? "" : entry.slice(idx + 1);
  if (!CAP_SET.has(key)) return null;
  const cap = key as Cap;
  if (!SPLIT_CAPS.has(cap) || !suffix) return [cap, "edit"];
  return suffix in RANK ? [cap, suffix as CapLevel] : null;
}

/** Chuẩn hoá về dạng lưu: mức Sửa = key trần, mức Xem = `key:view`. */
export const formatCap = (key: Cap, level: CapLevel): string => (level === "edit" ? key : `${key}:${level}`);

/** Quyền THỰC của tài khoản dạng `{key: level}`: admin→tất cả (Sửa), executive→EXECUTIVE_CAPS (Xem),
 *  editor→theo list, còn lại→rỗng. */
export function effectiveCaps(role: string | undefined, permissions: string[] | undefined): Map<Cap, CapLevel> {
  const out = new Map<Cap, CapLevel>();
  if (role === "admin") {
    for (const k of CAP_KEYS) out.set(k, "edit");
    return out;
  }
  if (role === "executive") {
    for (const k of CAP_KEYS) if (EXECUTIVE_CAPS.has(k)) out.set(k, "view");
    return out;
  }
  if (role !== "editor") return out;
  for (const entry of permissions ?? []) {
    const parsed = parseCap(entry);
    if (parsed && RANK[parsed[1]] > (RANK[out.get(parsed[0]) ?? ""] ?? 0)) out.set(parsed[0], parsed[1]);
  }
  return out;
}

/** Tài khoản có đạt mức quyền yêu cầu cho mục `key` không (mặc định: mức Xem). */
export const hasCap = (caps: Map<Cap, CapLevel>, key: Cap, level: CapLevel = "view"): boolean =>
  (RANK[caps.get(key) ?? ""] ?? 0) >= RANK[level];
