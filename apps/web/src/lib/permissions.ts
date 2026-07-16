/* Quyền theo mục dữ liệu (phân quyền chuyên viên nhập liệu). Khớp backend app/core/permissions.py.
   admin = tất cả · editor = theo danh sách · viewer (Người xem) = không có mục nào. */

export type Cap =
  | "market_quote" | "raw_material" | "floor" | "physical"
  | "inventory" | "member_unit" | "auto_data" | "market_demand"
  | "floor_suggest" | "bulletin_daily" | "bulletin_weekly" | "market_movement";

/** Danh sách quyền + nhãn hiển thị (trang Quản trị người dùng, theo thứ tự này). */
export const DATA_CAPS: { key: Cap; label: string; hint?: string }[] = [
  { key: "market_quote", label: "Báo giá mủ thị trường", hint: "Mục 1–4 (không gồm giá mủ khu vực)" },
  { key: "raw_material", label: "Giá mủ nguyên liệu", hint: "gồm cả Mục 5 (giá mủ khu vực) trong Báo giá" },
  { key: "floor", label: "Giá sàn Tập đoàn" },
  { key: "physical", label: "Giá Physical" },
  { key: "inventory", label: "Tồn kho" },
  { key: "member_unit", label: "Đơn vị thành viên" },
  { key: "auto_data", label: "Số liệu tự động", hint: "Bảng tính giá các sàn · Tỷ giá · Quét đa sàn" },
  { key: "market_demand", label: "Nhu cầu thị trường", hint: "xem + sửa nhu cầu của mọi đơn vị" },
  { key: "floor_suggest", label: "Gợi ý giá sàn", hint: "màn phân tích" },
  { key: "bulletin_daily", label: "Bản tin ngày", hint: "màn phân tích" },
  { key: "bulletin_weekly", label: "Báo cáo tuần", hint: "màn phân tích" },
  { key: "market_movement", label: "Bản tin biến động", hint: "màn phân tích" },
];

export const CAP_KEYS: Cap[] = DATA_CAPS.map((c) => c.key);
const CAP_SET = new Set<string>(CAP_KEYS);

/** Gom quyền thành nhóm cho UI cấp quyền (theo cấu trúc menu — đỡ rối). */
export const CAP_GROUPS: { title: string; keys: Cap[] }[] = [
  { title: "Quản lý số liệu (tự động)", keys: ["auto_data"] },
  { title: "Quản lý số liệu (thủ công)", keys: ["market_quote", "raw_material", "floor", "physical", "inventory", "member_unit", "market_demand"] },
  { title: "Phân tích & Bản tin", keys: ["floor_suggest", "bulletin_daily", "bulletin_weekly", "market_movement"] },
];

/** Quyền THỰC của tài khoản: admin→tất cả, editor→theo list, viewer→rỗng. */
export function effectiveCaps(role: string | undefined, permissions: string[] | undefined): Set<string> {
  if (role === "admin") return new Set<string>(CAP_KEYS);
  if (role === "editor") return new Set((permissions ?? []).filter((c) => CAP_SET.has(c)));
  return new Set();
}
