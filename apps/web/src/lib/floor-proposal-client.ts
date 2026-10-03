/* Client API Phương án giá sàn (nháp, KHÔNG ghi biểu giá sàn chính thức) + Bản nháp tờ trình.
   Hợp đồng: plans/260924-ban-nhap-gia-san-tro-ly/plan.md. Mọi phép tính (delta, nội địa theo FOB,
   làm tròn bước, hoàn tác) do SERVER làm — FE chỉ gửi nguyên `Proposal` nhận được (kể cả
   `log[].before`) cùng thay đổi người dùng muốn, rồi thay bằng bản server trả về. */

import { authHeaders, onUnauthorized } from "./auth-token";
import type { Memo, Sheet, Stage, StageMove } from "./floor-draft-flow-client";
import type { FloorModel } from "./floor-suggest-client";
import { API, apiFetch } from "./http";

export type ProposalUnit = "USD/T" | "VNĐ/T";
/** Ai đặt mức hiện tại của dòng: mô hình · giá hiện hành · Trợ lý AI chỉnh · người dùng sửa tay. */
export type ProposalOrigin = "model" | "current" | "ai" | "manual";
export type ProposalBase = "model" | "current";

export type ProposalRow = {
  grade: string;              // khoá hệ thống, vd "SVR 10 / CSR 10"
  label: string;              // tên trên tờ trình, vd "SVR10"
  unit: ProposalUnit;         // "VNĐ/T" = chỉ nội địa (Skim Block, fob luôn null)
  prev_fob: number | null; prev_vnd: number | null;   // lần ban hành trước
  model_fob: number | null; model_vnd: number | null; // mức mô hình (null = chưa đủ dữ liệu)
  fob: number | null; vnd: number | null;             // mức trong phương án (sửa được)
  vnd_manual: boolean;        // nội địa đặt tay, không tự tính theo FOB
  origin: ProposalOrigin;
  fob_delta: number | null; fob_delta_pct: number | null;
  vnd_delta: number | null; vnd_delta_pct: number | null;
  off_step: boolean;          // mức không phải bội bước ban hành
  warning: string | null;
};

/** `before` là ảnh chụp nội bộ để server hoàn tác — FE giữ nguyên, không đọc, không hiển thị. */
export type ProposalLog = { at: string; by: "ai" | "manual" | "system"; text: string; before?: unknown };

export type Proposal = {
  version: 1;
  as_of: string;              // ngày phương án = ngày tờ trình (YYYY-MM-DD)
  prev_as_of: string | null;  // lần ban hành gần nhất trước as_of
  model: string;
  base: ProposalBase;
  rows: ProposalRow[];        // đúng thứ tự tờ trình — KHÔNG sort
  log: ProposalLog[];         // cũ → mới
};

export type ProposalOp = "step" | "amount" | "percent" | "set" | "reset_model" | "reset_current" | "undo";
export type ProposalChange = {
  grades?: string[];          // khoá chủng loại và/hoặc nhóm: "all" | "svr" | "svr_cv" | "rss" | "latex" | "skim"
  op: ProposalOp;
  value?: number;
  field?: "fob" | "vnd";
};
export type ApplyResult = { proposal: Proposal; applied: string[]; warnings: string[] };

export type DraftSource = "assistant" | "floor_suggest" | "manual";
export type DraftDoc = {
  as_of: string; year: number; lan: number; prev_lan: number; t1: string | null; t2: string | null;
  settlement: unknown[]; physical: unknown[]; n1: string[]; n2: string[];
};
export type Draft = {
  id: number; as_of: string; title: string; note: string | null; source: DraftSource;
  proposal: Proposal; doc: DraftDoc;
  stage: Stage; sheet: Sheet | null; memo: Memo | null; history: StageMove[];
  sig: string;                // chữ ký số phương án — khác memo.ai.sig ⇒ số đã đổi sau khi AI soạn
  created_by: string | null; updated_by: string | null; created_at: string; updated_at: string;
};
export type DraftSummary = Omit<Draft, "proposal" | "doc" | "note" | "sheet" | "memo" | "history" | "sig">
  & { lan: number; headline: string };
export type DraftPage = { items: DraftSummary[]; total: number; page: number; page_size: number };

export type DraftCreate = {
  title?: string; note?: string; source?: DraftSource; proposal?: Proposal; as_of?: string; model?: FloorModel;
};
export type DraftUpdate = {
  title: string; note?: string | null; proposal: Proposal;
  n1?: string[]; n2?: string[];   // diễn giải kiểu cũ — không gửi = giữ nguyên
  sheet?: Sheet; memo?: Memo;     // chỉ sửa được ở đúng bước (server chặn)
  /** `updated_at` của bản đang sửa — người khác đã lưu sau mốc này thì server trả 409, không lưu đè. */
  base_updated_at?: string;
};

export const DRAFT_SOURCE_LABEL: Record<DraftSource, string> = {
  assistant: "Trợ lý AI", floor_suggest: "Gợi ý giá sàn", manual: "Thủ công",
};

const jsonInit = (method: string, body: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

/** Endpoint trả `text/html` (tờ trình) — không đi qua apiFetch vì apiFetch parse JSON. */
async function fetchHtml(path: string, init?: RequestInit): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { ...init, headers: { ...authHeaders(), ...(init?.headers ?? {}) } });
  } catch {
    throw new Error(`Không kết nối được máy chủ (${API}) — kiểm tra mạng hoặc thử lại.`);
  }
  if (res.status === 401) { onUnauthorized(); throw new Error("Phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại."); }
  if (!res.ok) {
    let msg = res.status === 403 ? "Bạn không có quyền thực hiện thao tác này." : `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") msg = body.detail;
    } catch { /* body không phải JSON — giữ câu mặc định */ }
    throw new Error(msg);
  }
  return res.text();
}

/* ── Phương án (không ghi DB) ─────────────────────────────────────────────────────────────── */

export const createProposal = (opts: { as_of?: string; base?: ProposalBase; model?: FloorModel } = {}) =>
  apiFetch<Proposal>("/api/floor-proposal/create", jsonInit("POST", opts));

export const applyProposal = (proposal: Proposal, changes: ProposalChange[], by: "manual" = "manual") =>
  apiFetch<ApplyResult>("/api/floor-proposal/apply", jsonInit("POST", { proposal, changes, by }));

/** Tờ trình dựng từ phương án đang sửa (kể cả thay đổi chưa lưu). `draft_id` → dùng ảnh chụp số
 *  thị trường của bản nháp thay vì số hôm nay. */
export const previewProposalHtml = (body: { proposal: Proposal; n1?: string[]; n2?: string[]; memo?: Memo; draft_id?: number }) =>
  fetchHtml("/api/floor-proposal/preview", jsonInit("POST", body));

/* ── Bản nháp tờ trình (ghi DB) ───────────────────────────────────────────────────────────── */

export const listDrafts = (page: number, pageSize: number) =>
  apiFetch<DraftPage>(`/api/floor-proposal/drafts?page=${page}&page_size=${pageSize}`);

export const getDraft = (id: number) => apiFetch<Draft>(`/api/floor-proposal/drafts/${id}`);

export const createDraft = (body: DraftCreate) =>
  apiFetch<Draft>("/api/floor-proposal/drafts", jsonInit("POST", body));

export const updateDraft = (id: number, body: DraftUpdate) =>
  apiFetch<Draft>(`/api/floor-proposal/drafts/${id}`, jsonInit("PUT", body));

export const deleteDraft = (id: number) =>
  apiFetch<{ deleted: number }>(`/api/floor-proposal/drafts/${id}`, { method: "DELETE" });

export const fetchDraftHtml = (id: number) => fetchHtml(`/api/floor-proposal/drafts/${id}/html`);

/** Phương án nháp của phiên Trợ lý AI giữ ở sessionStorage theo khoá `<tiền tố><username>`. */
export const SESSION_PROPOSAL_PREFIX = "vrg.assistant.proposal:";

/** Đăng xuất → xoá mọi phương án nháp của phiên (máy dùng chung: người sau không đọc được). */
export function clearSessionProposals(): void {
  try {
    const keys: string[] = [];
    for (let i = 0; i < sessionStorage.length; i += 1) {
      const k = sessionStorage.key(i);
      if (k?.startsWith(SESSION_PROPOSAL_PREFIX)) keys.push(k);
    }
    keys.forEach((k) => sessionStorage.removeItem(k));
  } catch {
    /* trình duyệt chặn bộ nhớ → không có gì để xoá */
  }
}

/** Đường dẫn màn soạn bản nháp — dùng chung cho link/điều hướng. */
export const draftPath = (id: number) => `/goi-y-gia-san/ban-nhap/${id}`;
export const DRAFT_LIST_PATH = "/goi-y-gia-san/ban-nhap";
