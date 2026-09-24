/* Cửa sổ nhập liệu: số liệu ngày D nhập/sửa được đến GIỜ CHỐT (mặc định 11:00, giờ VN) của ngày
   D + N; quá hạn = chỉ xem. Admin luôn sửa được. N và giờ chốt do admin cấu hình.

   Web KHÔNG tự tính giờ: server trả sẵn `editable_from` (ngày cũ nhất còn sửa được, đã tính giờ
   chốt theo đồng hồ server) — kèm payload của từng màn, hoặc qua /api/settings/edit-windows. Đồng
   hồ máy người dùng có thể lệch, và server mới là hàng rào thật. */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../features/auth/AuthContext";
import { type EditWindows, fetchEditWindows } from "./settings-client";

export const DEFAULT_CUTOFF_HOUR = 11;

/** Lùi/tiến `delta` ngày từ 1 ISO date (YYYY-MM-DD) — theo lịch, không lệch múi giờ. */
function shiftISO(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
}

/** N ngày → cụm từ nói rõ GIỜ CHỐT (khớp `edit_window.window_phrase` ở server):
 *  0 → "đến 11:00 cùng ngày", 1 → "đến 11:00 ngày hôm sau", N → "đến 11:00, N ngày sau ngày số liệu".
 *  KHÔNG viết "ngày thứ N" — "ngày thứ 7" đọc thành thứ Bảy. */
export function windowPhrase(days: number, hour: number = DEFAULT_CUTOFF_HOUR): string {
  const hh = `${String(hour).padStart(2, "0")}:00`;
  if (days <= 0) return `đến ${hh} cùng ngày`;
  if (days === 1) return `đến ${hh} ngày hôm sau`;
  return `đến ${hh}, ${days} ngày sau ngày số liệu`;
}

/** Câu luật đầy đủ cho người dùng: "Số liệu mỗi ngày nhập/sửa đến 11:00 ngày hôm sau". */
export function windowRule(days: number, hour: number = DEFAULT_CUTOFF_HOUR): string {
  return `Số liệu mỗi ngày nhập/sửa ${windowPhrase(days, hour)}`;
}

/** Ngày `dateISO` còn trong cửa sổ? (`editableFrom` do server tính; tương lai = không). */
export function inWindow(dateISO: string, editableFrom: string, today: string): boolean {
  return dateISO >= editableFrom && dateISO <= today;
}

/** Các ngày còn nhập được, mới → cũ. RỖNG khi đã qua giờ chốt mà N = 0 (hôm nay cũng đã khoá). */
export function windowDatesOf(editableFrom: string, today: string): string[] {
  const out: string[] = [];
  for (let d = today; d >= editableFrom; d = shiftISO(d, -1)) out.push(d);
  return out;
}

// Một trang có thể mở nhiều hook cùng lúc (bảng + modal + bảng nhắc) → dùng chung một lần gọi.
// Hạn ngắn để trang để mở qua giờ chốt vẫn cập nhật khi người dùng quay lại tab.
const CACHE_MS = 60_000;
// Tải lại sau mốc đổi thêm chút cho chắc server đã qua giờ chốt; sàn chờ tối thiểu chỉ để phòng
// vòng tải lại liên tục (server luôn trả `next_change_at` > `now`, nên bình thường không chạm sàn).
const AFTER_CHANGE_MS = 2_000;
const MIN_RELOAD_MS = 5_000;
type Loaded = { w: EditWindows; at: number };   // at = lúc gửi yêu cầu (đồng hồ máy người dùng)
let cache: { at: number; p: Promise<Loaded> } | null = null;

/** `staleBefore`: bỏ cache gọi TRƯỚC mốc này (đã qua giờ chốt thì số cũ sai). Nhiều hook cùng hẹn
 *  một mốc: hook chạy trước bỏ cache cũ và gọi lại, các hook sau dùng chung lần gọi mới đó. */
function loadEditWindows(staleBefore = 0): Promise<Loaded> {
  if (!cache || cache.at < staleBefore || Date.now() - cache.at > CACHE_MS) {
    const at = Date.now();
    const p = fetchEditWindows().then((w) => ({ w, at })).catch((e) => { cache = null; throw e; });
    cache = { at, p };
  }
  return cache.p;
}

/** Mốc đổi cửa sổ theo đồng hồ máy người dùng. Tính bằng HIỆU hai mốc giờ server (`next_change_at`
 *  − `now`) cộng vào lúc gọi ⇒ đồng hồ máy người dùng có lệch cũng không hẹn sai giờ. */
function changeAt({ w, at }: Loaded): number {
  return at + Date.parse(w.next_change_at) - Date.parse(w.now);
}

/** Tải cấu hình cửa sổ; nạp lại khi người dùng quay lại tab, và HẸN GIỜ nạp lại đúng mốc giờ chốt
 *  kế tiếp — tab để mở suốt qua 11:00 thì ô vừa hết hạn tự khoá, khỏi gõ xong mới nhận 403. */
function useEditWindows(): EditWindows | null {
  const [w, setW] = useState<EditWindows | null>(null);
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = (staleBefore = 0) => {
      loadEditWindows(staleBefore).then((r) => {
        if (!alive) return;
        setW(r.w);
        const due = changeAt(r);
        clearTimeout(timer);
        if (!Number.isFinite(due)) return;   // server cũ chưa trả mốc → chỉ còn nạp lại khi quay lại tab
        timer = setTimeout(() => load(due), Math.max(due - Date.now() + AFTER_CHANGE_MS, MIN_RELOAD_MS));
      }).catch(() => {});
    };
    const onVisible = () => { if (document.visibilityState === "visible") load(); };
    load();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, []);
  return w;
}

/** Giờ chốt (0–23) để dựng câu nhắc ở màn đã có `editable_from` riêng trong payload. */
export function useCutoffHour(): number {
  return useEditWindows()?.cutoff_hour ?? DEFAULT_CUTOFF_HOUR;
}

/** Hook cửa sổ sửa của chuyên viên. `isEditable(dateISO)`: admin→luôn true; còn lại→so `editable_from`.
 *  `windowDates` = các ngày còn sửa được (mới → cũ) để lưới hiện sẵn dòng trống cho nhập. */
export function useEditorWindow() {
  return useWindow("editor");
}

/** Cửa sổ sửa theo VAI TRÒ — đơn vị thành viên có thông số riêng với chuyên viên.
 *  Dùng cho màn DÙNG CHUNG (Quản lý hợp đồng): cả hai vai trò vào cùng một bộ endpoint nên không
 *  chọn cứng một thông số được, phải khớp với `security.assert_edit_window` ở server. */
export function useEditWindow() {
  const { isUnitAccount } = useAuth();
  return useWindow(isUnitAccount ? "member" : "editor");
}

function useWindow(kind: "member" | "editor") {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const r = useEditWindows();
  const days = r ? (kind === "member" ? r.member_days : r.editor_days) : null;
  const editableFrom = r ? (kind === "member" ? r.member_editable_from : r.editor_editable_from) : null;
  const today = r?.today ?? null;
  const cutoffHour = r?.cutoff_hour ?? DEFAULT_CUTOFF_HOUR;

  const isEditable = (dateISO: string): boolean => {
    if (isAdmin) return true;
    if (!editableFrom || !today) return true; // chưa tải xong → tạm cho (backend vẫn là hàng rào thật)
    return inWindow(dateISO, editableFrom, today);
  };

  const windowDates = useMemo(
    () => (editableFrom && today ? windowDatesOf(editableFrom, today) : []),
    [editableFrom, today],
  );

  return {
    isEditable, days, today, editableFrom, cutoffHour, windowDates, ready: !!r, isAdmin,
    /** Câu "đến 11:00 ngày hôm sau"… theo đúng thông số của vai trò. */
    phrase: windowPhrase(days ?? 7, cutoffHour),
  };
}
