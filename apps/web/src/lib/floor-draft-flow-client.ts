/* Client quy trình bản nháp giá sàn: Nháp → Dự thảo → Tờ trình → Áp dụng.
   Hợp đồng: plans/261003-quy-trinh-gia-san/plan.md. Server chặn sửa sai bước — FE chỉ ẩn/khoá cho gọn. */

import { authHeaders, onUnauthorized } from "./auth-token";
import type { Draft } from "./floor-proposal-client";
import { API, apiFetch } from "./http";

export type Stage = "nhap" | "du_thao" | "to_trinh" | "ap_dung";
export const STAGES: Stage[] = ["nhap", "du_thao", "to_trinh", "ap_dung"];
export const STAGE_LABEL: Record<Stage, string> = {
  nhap: "Nháp", du_thao: "Dự thảo", to_trinh: "Tờ trình", ap_dung: "Áp dụng",
};
export const STAGE_COLOR: Record<Stage, string> = {
  nhap: "default", du_thao: "blue", to_trinh: "purple", ap_dung: "green",
};
/** Áp dụng có trong quy trình nhưng chưa làm (không ghi biểu giá sàn chính thức). */
export const APPLY_READY = false;

export type Para = { lead: string; text: string };
export type Sheet = { vcb_rate: number | null; vcb_time: string; vcb_date: string | null };
export type Signers = {
  left_role: string; left_name: string; right_role: string; right_name: string;
  approver_role: string; approver_name: string;
};
export type MemoAiMeta = { at: string; by: string | null; sig: string; warnings: string[] };
export type Memo = {
  so: string; sign_date: string;
  futures_note: string; futures: Para[];
  physical_title: string; physical_note: string; physical: Para[];
  outlook: Para[]; inventory: Para; intro: string;
  signers: Signers;
  sig: string;                // chữ ký số phương án lúc nội dung được soạn/soát — khác Draft.sig ⇒ cần soát lại
  ai: MemoAiMeta | null;
};
/** Một lần chuyển bước; `note` = lý do (nhất là khi trả về vì lãnh đạo chưa duyệt). */
export type StageMove = { from: Stage; to: Stage; at: string; by: string | null; note?: string | null };

const BASE = "/api/floor-proposal";
const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

/** Tới một nấc, hoặc trả về thẳng bước bất kỳ phía trước (kèm lý do). */
export const moveStage = (id: number, to: Stage, baseUpdatedAt?: string, note?: string) =>
  apiFetch<Draft>(`${BASE}/drafts/${id}/stage`, json({ to, note: note || undefined, base_updated_at: baseUpdatedAt }));

/** AI viết lại phần nhận định từ dữ liệu của bản nháp — trả nội dung mới, KHÔNG lưu. */
export const memoAi = (id: number, memo: Memo) =>
  apiFetch<{ memo: Memo; warnings: string[] }>(`${BASE}/drafts/${id}/memo/ai`, json({ memo }));

export const fetchVcbRate = (date?: string) =>
  apiFetch<{ rate: number | null; date: string }>(`${BASE}/vcb-rate${date ? `?date=${date}` : ""}`);

export type DraftFile = "du-thao.png" | "to-trinh.pdf" | "to-trinh.docx";

/** Tệp dựng ở server từ BẢN ĐÃ LƯU (hình dự thảo · PDF · Word). */
export async function fetchDraftFile(id: number, file: DraftFile): Promise<{ blob: Blob; name: string }> {
  let res: Response;
  try {
    res = await fetch(`${API}${BASE}/drafts/${id}/${file}`, { headers: authHeaders() });
  } catch {
    throw new Error(`Không kết nối được máy chủ (${API}) — kiểm tra mạng hoặc thử lại.`);
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại."); }
  if (!res.ok) {
    let msg = `Không tải được tệp (HTTP ${res.status}).`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") msg = body.detail;
    } catch { /* không phải JSON */ }
    throw new Error(msg);
  }
  const disp = res.headers.get("content-disposition") ?? "";
  const name = decodeURIComponent(disp.match(/filename\*=UTF-8''([^;]+)/)?.[1] ?? file);
  return { blob: await res.blob(), name };
}

export function saveBlob(blob: Blob, name: string): void {
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 60_000);
}

/** Chép ảnh vào bộ nhớ tạm. Truyền Promise<Blob> thẳng vào ClipboardItem để Safari không mất
 *  "thao tác người dùng" trong lúc chờ server dựng ảnh. Trả false nếu trình duyệt không cho chép ảnh. */
export async function copyImage(blob: Promise<Blob>): Promise<boolean> {
  const Item = (window as unknown as { ClipboardItem?: typeof ClipboardItem }).ClipboardItem;
  if (!Item || !navigator.clipboard?.write) return false;
  await navigator.clipboard.write([new Item({ "image/png": blob })]);
  return true;
}
