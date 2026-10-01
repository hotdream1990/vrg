/* Loại nhập liệu của tài khoản đơn vị + nhóm người nhận thẻ Hỗ trợ & Thông báo (chốt 01/10/2026).
   Bản sao của backend `app/core/entry_types.py` — sửa một bên thì sửa cả hai.
   Tài khoản `member` được giao một hoặc nhiều loại; server chặn GHI ngoài loại được giao,
   giao diện ẩn màn ngoài phần việc. */

export type EntryType = "purchase" | "stock" | "contract";
export type Audience = "leader" | EntryType;

export const ENTRY_TYPES: EntryType[] = ["purchase", "stock", "contract"];

export const ENTRY_TYPE_LABEL: Record<EntryType, string> = {
  purchase: "Thu mua",
  stock: "Tồn kho",
  contract: "Hợp đồng & tiêu thụ",
};

export const AUDIENCES: Audience[] = ["leader", ...ENTRY_TYPES];

export const AUDIENCE_LABEL: Record<Audience, string> = {
  leader: "Lãnh đạo đơn vị",
  purchase: "CV Thu mua",
  stock: "CV Tồn kho",
  contract: "CV Hợp đồng & tiêu thụ",
};

/** Thẻ không ghi nhóm người nhận (dữ liệu cũ) = chỉ lãnh đạo. */
export const DEFAULT_AUDIENCE: Audience[] = ["leader"];
