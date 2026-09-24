# Bản nháp giá sàn trong Trợ lý AI + lưu bản nháp tờ trình

Ngày: 24–25/09/2026 · Nhánh: `feature/master-contract` · Trạng thái: xong code + kiểm thử, chưa commit/deploy

## Mục tiêu (chủ dự án yêu cầu, "cho nó linh động")
1. Trong phiên chat, người dùng hỏi số liệu giá sàn rồi bảo "tăng lên tí xíu" → Trợ lý chỉnh
   **phương án giá sàn nháp của PHIÊN** (không ghi số liệu thật), hiện lên UI để sửa tiếp bằng tay.
2. Từ phương án → **xem trước tờ trình** (mẫu tờ trình sẵn có, khối 3 thay bằng số phương án).
3. **Lưu bản nháp** → mở lại, sửa tay (số + đoạn diễn giải), lưu tiếp, in PDF. Tách hẳn biểu giá sàn
   chính thức (`vrg_floor_price` KHÔNG bị đụng).

## Quyết định đã chốt (đề xuất mặc định, chủ dự án "ok, linh động")
- Điểm xuất phát: mức mô hình (tư vấn "Theo mô hình"/"Có điều chỉnh"); "Chỉ tra số" → giá hiện hành.
- Bản nháp lưu ẢNH CHỤP cố định số thị trường lúc lưu (văn bản trình duyệt).
- Lưu nháp: quyền `floor_suggest`. Lãnh đạo Tập đoàn chỉ xem.
- Chưa có nút "chuyển thành giá sàn chính thức".
- Phép tính do SERVER làm (AI không tự cộng/làm tròn — 4 lần dính bẫy số).
- "Tí xíu/chút/nhẹ" = 1 bước ban hành (5 USD/tấn FOB · 50.000 đ/tấn nội địa). % → làm tròn theo bước.
  Số tuyệt đối/đặt mức → giữ đúng số người dùng nói, gắn cờ `off_step` nếu không phải bội bước.
- FOB đổi → nội địa tự tính lại theo tỉ lệ (prev_vnd × fob / prev_fob, làm tròn 50.000) trừ khi
  nội địa đã sửa tay (`vnd_manual`).

## HỢP ĐỒNG API (backend ↔ frontend)

### Kiểu dữ liệu
```ts
type ProposalRow = {
  grade: string;              // khoá hệ thống, vd "SVR 10 / CSR 10" (đúng VRG_FLOOR_GRADES)
  label: string;              // tên trên tờ trình, vd "SVR10"
  unit: "USD/T" | "VNĐ/T";    // đơn vị chính; "VNĐ/T" = chỉ nội địa (Skim Block, fob luôn null)
  prev_fob: number | null;  prev_vnd: number | null;   // lần ban hành trước (server nạp lại từ DB)
  model_fob: number | null; model_vnd: number | null;  // mức mô hình (null = chưa đủ dữ liệu)
  fob: number | null;       vnd: number | null;        // mức trong phương án (SỬA ĐƯỢC)
  vnd_manual: boolean;        // true = nội địa đặt tay, không tự tính theo FOB
  origin: "model" | "current" | "ai" | "manual";      // ai đặt mức hiện tại
  fob_delta: number | null; fob_delta_pct: number | null;   // so lần trước (server tính)
  vnd_delta: number | null; vnd_delta_pct: number | null;
  off_step: boolean;          // mức không phải bội bước ban hành
  warning: string | null;     // cảnh báo của dòng (lệch > 20% so lần trước…)
};
type ProposalLog = { at: string; by: "ai" | "manual" | "system"; text: string };  // + `before` (nội bộ, FE giữ nguyên, không hiển thị)
type Proposal = {
  version: 1;
  as_of: string;              // ngày phương án = ngày tờ trình (YYYY-MM-DD)
  prev_as_of: string | null;  // lần ban hành gần nhất trước as_of
  model: string;              // "v2" | "v1" | "v1i" | "v1f"
  base: "model" | "current";
  rows: ProposalRow[];        // 14 dòng ĐÚNG THỨ TỰ tờ trình (CV50 → SkimBlock) — KHÔNG sort
  log: ProposalLog[];         // cũ → mới, tối đa 30
};
type ProposalChange = {
  grades?: string[];          // khoá chủng loại và/hoặc nhóm: "all" | "svr" | "svr_cv" | "rss" | "latex" | "skim"
  op: "step" | "amount" | "percent" | "set" | "reset_model" | "reset_current" | "undo";
  value?: number;             // step: số bước ±; amount: ±số tiền; percent: ±%; set: mức mới
  field?: "fob" | "vnd";      // mặc định "fob"; Skim Block luôn "vnd"
};
```
FE gửi nguyên `Proposal` nhận được (kể cả `log[].before`) — không tự tính delta/vnd.

### Endpoint phương án (không ghi DB) — quyền: `assistant` HOẶC `floor_suggest`
| Method | Path | Body | Trả |
|---|---|---|---|
| POST | `/api/floor-proposal/create` | `{as_of?, base?: "model"\|"current", model?}` | `Proposal` |
| POST | `/api/floor-proposal/apply` | `{proposal, changes: ProposalChange[], by?: "manual"}` | `{proposal, applied: string[], warnings: string[]}` · 400 nếu thay đổi sai |
| POST | `/api/floor-proposal/preview` | `{proposal, n1?: string[], n2?: string[], draft_id?: number}` | `text/html` tờ trình (draft_id → dùng ảnh chụp số thị trường của nháp) |

### Endpoint bản nháp (ghi DB) — quyền: `floor_suggest`
| Method | Path | Body | Trả |
|---|---|---|---|
| GET | `/api/floor-proposal/drafts?page=1&page_size=25` | — | `{items: DraftSummary[], total, page, page_size}` |
| GET | `/api/floor-proposal/drafts/{id}` | — | `Draft` |
| POST | `/api/floor-proposal/drafts` | `{title?, note?, source?: "assistant"\|"floor_suggest"\|"manual", proposal?: Proposal, as_of?, model?}` (không có proposal → dựng từ mô hình tại as_of) | `Draft` |
| PUT | `/api/floor-proposal/drafts/{id}` | `{title, note?, proposal, n1: string[], n2: string[]}` | `Draft` |
| DELETE | `/api/floor-proposal/drafts/{id}` | — | `{deleted: 1}` |
| GET | `/api/floor-proposal/drafts/{id}/html` | — | `text/html` tờ trình của bản đã lưu |

```ts
type DraftDoc = { as_of: string; year: number; lan: number; prev_lan: number; t1: string|null; t2: string|null;
                  settlement: any[]; physical: any[]; n1: string[]; n2: string[] };
type Draft = { id: number; as_of: string; title: string; note: string | null;
               source: "assistant" | "floor_suggest" | "manual";
               proposal: Proposal; doc: DraftDoc;
               created_by: string | null; updated_by: string | null; created_at: string; updated_at: string };
type DraftSummary = Omit<Draft, "proposal" | "doc" | "note"> & { lan: number; headline: string }; // headline vd "SVR10 2.360 USD/T (+20)"
```

### Trợ lý AI (`POST /api/assistant/chat`)
- Body thêm `proposal?: Proposal | null` (phương án hiện tại của phiên).
- Trả thêm `proposal: Proposal | null` — **khác null ⇒ FE thay phương án của phiên** bằng bản này.
- Công cụ mới (gói `floor`): `create_floor_proposal`, `adjust_floor_proposal`.

## Phân việc
- Backend (agent chính): `services/floor_proposal*.py`, `services/floor_draft_repo.py`,
  `routers/floor_proposal.py`, `schemas/floor_proposal.py`, `assistant_tools/proposal_tools.py`,
  sửa `assistant_service.py` · `assistant_tools/__init__.py` · `schemas/assistant.py` ·
  `routers/assistant.py` · `to_trinh.py` · `to_trinh_html.py` · `main.py` ·
  `core/executive_readonly_guard.py` + test.
- Frontend (subagent): `lib/floor-proposal-client.ts`, `FloorProposalPanel`, AssistantPage,
  ToTrinhPreview, trang danh sách + soạn bản nháp, route + menu, FloorSuggestPage nút lưu nháp.

## Todo
- [x] Backend logic + API + test (15 test mới; suite đầy đủ xanh trừ 3 test hợp đồng lỗi môi trường cũ)
- [x] Frontend (tsc + build sạch)
- [x] Kiểm thử trình duyệt (chat thật + sửa tay + xem trước + lưu + mở lại + màn hẹp + từ Gợi ý giá sàn)
- [x] Review backend (3 trung bình + 10 thấp — đã sửa) · [x] review frontend (2 cao + 3 TB + 6 thấp — đã sửa, kiểm lại trên trình duyệt)
- [x] Docs (changelog, tro-ly-ai-kha-nang, memory)

## Bổ sung sau review
- PUT bản nháp nhận `base_updated_at` → 409 nếu người khác đã lưu sau mốc đó.
- `create_floor_proposal` từ chối lập đè phương án đã có chỉnh sửa trừ khi `replace=true` (người dùng xác nhận).
- Tự lập phương án khi người dùng bảo "tăng/giảm" → mặc định xuất phát GIÁ HIỆN HÀNH (`base=current`).
- Giao diện: chờ hàng đợi áp số trước khi Lưu / gửi chat (không mất số vừa gõ); hộp thoại 409; cảnh báo rời trang khi chưa lưu (menu · đăng xuất; nút Back trình duyệt CHƯA chặn).
