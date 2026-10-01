/* Lõi gọi API dùng chung cho mọi client.
   Tập trung xử lý: gắn Bearer token · 401 (hết phiên → về /login) · 403 (không đủ quyền)
   · lỗi kết nối · đọc message lỗi (`detail`) từ FastAPI. Sửa 1 chỗ, mọi client hưởng. */

import { authHeaders, onUnauthorized } from "./auth-token";

export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8390";

/** Hàng rào thời gian đã chặn lần ghi: `window` = cửa sổ sửa N ngày · `lock` = chốt số liệu.
 *  Server gắn qua header `X-Edit-Blocked` (xem api-contract Đề nghị sửa số liệu). */
export type EditBlockedKind = "window" | "lock";

/** Lỗi gọi API — vẫn là `Error` (message giữ nguyên câu tiếng Việt) nên mọi màn cũ đọc
 *  `e.message` không đổi gì; thêm `status` (0 = không kết nối được) và `blocked`. */
export class ApiError extends Error {
  status: number;
  blocked: EditBlockedKind | null;

  constructor(message: string, status: number, blocked: EditBlockedKind | null = null) {
    super(message);
    this.status = status;
    this.blocked = blocked;
  }
}

/** Lần ghi bị hàng rào thời gian chặn (cửa sổ sửa / chốt số liệu) — đơn vị có thể gửi Đề nghị sửa. */
export function isEditBlocked(e: unknown): e is ApiError {
  return e instanceof ApiError && e.blocked != null;
}

function blockedKind(res: Response): EditBlockedKind | null {
  const v = res.headers.get("X-Edit-Blocked");
  return v === "window" || v === "lock" ? v : null;
}

/** Lỗi 422 của FastAPI: `detail` là MẢNG {loc, msg} → gộp thành câu đọc được.
 *  Không dịch được thì vẫn hơn hẳn "HTTP 422" trơ trọi — người dùng biết ô nào sai. */
function validationMessage(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const parts = detail.slice(0, 3).map((d) => {
    const item = d as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(item.loc) ? String(item.loc[item.loc.length - 1] ?? "") : "";
    return field ? `${field}: ${item.msg ?? ""}`.trim() : (item.msg ?? "");
  }).filter(Boolean);
  return parts.length ? `Số liệu gửi lên không hợp lệ — ${parts.join("; ")}` : null;
}

/** Lấy `detail` (message tiếng Việt từ FastAPI) trong body lỗi; fallback `HTTP <status>`. */
async function errorMessage(res: Response, fallback?: string): Promise<string> {
  const base = fallback ?? `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
    return validationMessage(body?.detail) ?? base;
  } catch {
    /* body không phải JSON — dùng fallback */
  }
  return base;
}

/** Gọi API + parse JSON. Ném `ApiError` với message thân thiện cho mọi nhánh lỗi. */
export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: { ...authHeaders(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(`Không kết nối được máy chủ (${API}) — kiểm tra mạng hoặc thử lại.`, 0);
  }
  if (res.status === 401) {
    dropPushSubscription();
    onUnauthorized();
    throw new ApiError("Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại.", 401);
  }
  if (res.status === 403) {
    const msg = await errorMessage(res, "Bạn không có quyền thực hiện thao tác này.");
    throw new ApiError(msg, 403, blockedKind(res));
  }
  if (!res.ok) {
    throw new ApiError(await errorMessage(res), res.status, blockedKind(res));
  }
  if ((init?.method ?? "GET") !== "GET") notifyDataSaved(path);
  return (await res.json()) as T;
}

/** Hết phiên ⇒ huỷ đăng ký Web Push của trình duyệt này: máy dùng chung, người sau không được nhận
 *  thông báo của người trước. Nạp động (push-client dùng lại http → tránh vòng import); cố gắng hết
 *  sức, không bao giờ ném lỗi, không giữ chân lần chuyển về /login. */
function dropPushSubscription(): void {
  import("./push-client").then((m) => m.unsubscribeBrowserOnly()).catch(() => undefined);
}

/** Sự kiện "vừa ghi số liệu" — phát ở ĐÂY thay vì ở từng màn nhập, để bảng nhắc việc của đơn vị
 *  không bao giờ nhắc thứ vừa được nhập xong. Gắn tay vào từng chỗ lưu là kiểu gì cũng sót một chỗ. */
export const DATA_SAVED_EVENT = "vrg:data-saved";

function notifyDataSaved(path: string): void {
  if (path.startsWith("/api/member/checklist")) return;   // tránh vòng lặp tự kích hoạt
  window.dispatchEvent(new CustomEvent(DATA_SAVED_EVENT, { detail: { path } }));
}
