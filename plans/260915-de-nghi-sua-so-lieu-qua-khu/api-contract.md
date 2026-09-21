# Hợp đồng API — Đề nghị sửa số liệu quá khứ

Nguồn sự thật cho cả backend lẫn web. Đổi gì ở đây phải báo agent chính.

## 0. Tín hiệu "bị hàng rào thời gian chặn"
Hai hàng rào hiện có ném `HTTPException(403, <câu tiếng Việt như cũ>)`. Bổ sung **header**
`X-Edit-Blocked: window` (cửa sổ sửa — `edit_window.assert_editable`, nhánh 403) hoặc
`X-Edit-Blocked: lock` (chốt số liệu — `data_lock.assert_not_locked`). `detail` giữ nguyên chuỗi
(test cũ + mọi màn đang đọc chuỗi). CORS `expose_headers=["X-Edit-Blocked"]`.

Web: `apiFetch` ném `ApiError extends Error { status: number; blocked: "window" | "lock" | null }`.

## 1. Op và payload
Payload = đúng body của API ghi gốc (để web gửi lại y nguyên thứ nó định lưu).

| op | payload | dates (ngày số liệu bị ảnh hưởng) | target_key (chống trùng) |
|---|---|---|---|
| `daily_report` | `{kind, company, as_of, fields, prices?, create_only?}` — `prices` chỉ khi kind=`purchase`: `{purchase?: number, purchase_cup?: number, purchase_lace?: number}`; chỉ key có mặt mới ghi; `0` = xoá ô giá (đúng luật `upsert_record`) | `[as_of]` | `daily:{kind}:{as_of}` |
| `daily_move` | `{kind, company, as_of, to_date}` | `[as_of, to_date]` | `daily_move:{kind}:{as_of}` (không đè đề nghị sửa nội dung cùng ngày) |
| `market_demand` | `{company, as_of, content, create_only?}` — **không** thuộc chốt số liệu: duyệt không gỡ chốt | `[as_of]` | `demand:{as_of}` |
| `contract_save` | body của `PUT /api/sales-contracts` (`ContractIn`) | ngày giao cũ + mới (khác null) | `contract:{id}` · thêm mới: `contract:new:{parent_id or 0}:{code chữ thường}` |
| `contract_delete` | `{id}` | ngày giao đang lưu | `contract:{id}` |
| `contract_delivery_type` | `{id, delivery_type}` — ô «Loại giao» là ô CHỈ XEM trên form nên đi bằng thao tác riêng (đổi loại giao còn dời lần giao xuống đợt giao đầu tiên) | ngày giao đang lưu | `contract:{id}` |

`create_only: true` (nút Thêm) chỉ kiểm LÚC GỬI, không lưu vào `payload` của đề nghị: ngày đó đã có
số ⇒ `409` đúng câu của API ghi thẳng — biểu ngày: "Đơn vị này đã có số liệu cho ngày này — vui lòng
dùng chức năng Sửa."; nhu cầu: "Đơn vị này đã có nhu cầu cho ngày này — vui lòng dùng chức năng Sửa."

Hợp đồng/đợt giao đang sửa-xoá hoặc hợp đồng cha đã **hoàn thành** ⇒ `400` ngay lúc gửi, đúng câu của
repo ("Hợp đồng … đã hoàn thành ngày … — bấm “Mở lại hợp đồng” trước khi …").

Chống trùng: đã có đề nghị `pending` cùng `(company, target_key)` ⇒ **ghi đè** đề nghị đó (op,
payload, reason, before, dates, blocked, updated_at) và trả `replaced: true` — không báo lỗi.

## 2. Bản ghi `EditRequest`
```ts
interface EditRequest {
  id: number; company: string;
  op: EditRequestOp; op_label: string;      // "Biểu Thu mua" | "Biểu Tồn kho" | "Đổi ngày biểu …" | "Nhu cầu thị trường" | "Hợp đồng" | "Xoá hợp đồng"
  title: string;                            // "Biểu Thu mua ngày 01/08/2026" | "Hợp đồng HĐ-12/2026" …
  target_key: string; dates: string[];      // 'YYYY-MM-DD'
  payload: Record<string, unknown>;         // nội dung đề nghị (đã chuẩn hoá)
  before: Record<string, unknown> | null;   // ảnh chụp bản ghi LÚC GỬI (null = thêm mới)
  reason: string;
  blocked: string[];                        // câu báo chặn lúc gửi (để người duyệt biết vì sao)
  status: "pending" | "approved" | "rejected" | "cancelled";
  requested_by: string; requested_by_name: string | null; requested_at: string; updated_at: string;
  reviewed_by: string | null; reviewed_by_name: string | null; reviewed_at: string | null;
  review_note: string | null;
  unlocked: { round_id: number; lock_date: string }[] | null;   // đợt chốt đã gỡ khi duyệt
}
type EditRequestOp = "daily_report" | "daily_move" | "market_demand" | "contract_save"
                   | "contract_delete" | "contract_delivery_type";
interface Paged { items: EditRequest[]; total: number; page: number; page_size: number;
                  counts: { pending: number; approved: number; rejected: number; cancelled: number } }
```
`before`/`current` theo op:
- `daily_report`: `{fields: {...payload ngày đó} | null, prices: {purchase?, purchase_cup?, purchase_lace?}}` (giá lớp `vrg_unit`)
- `daily_move`: `{fields: {...payload ngày as_of} | null, to_date_has_entry: boolean}`
- `market_demand`: `{content: string}`
- `contract_save` / `contract_delete` / `contract_delivery_type`: bản ghi hợp đồng (`sales_contract_repo.get`) hoặc null

## 3. Phía ĐƠN VỊ — `get_unit_user` (leader chỉ GET)
| Method | Path | Body / query | Trả |
|---|---|---|---|
| POST | `/api/member/edit-requests` | `{op, payload, reason}` | `{request, replaced}` |
| GET | `/api/member/edit-requests` | `status?=pending\|approved\|rejected\|cancelled\|all` (mặc định all), `page=1`, `page_size=20` (≤100) | `Paged` (chỉ đơn vị được gán) |
| GET | `/api/member/edit-requests/{id}` | | `{request}` |
| POST | `/api/member/edit-requests/{id}/cancel` | | `{request}` |

Lỗi khi gửi: `400` op/payload/lý do không hợp lệ (lý do trim ≥ 5 ký tự, ≤ 2000) hoặc số liệu sai
(ValueError của lớp chuẩn hoá) hoặc hợp đồng đã hoàn thành; `403` đơn vị ngoài quyền; `409`
`create_only` mà đã có số (mục 1); `409` **không bị hàng rào nào chặn** —
"Bản ghi này vẫn sửa trực tiếp được — không cần gửi đề nghị."; `409` huỷ đề nghị không còn chờ duyệt.

## 4. Phía BAN — `require_cap("edit_request")` (quản trị luôn có)
| Method | Path | Body / query | Trả |
|---|---|---|---|
| GET | `/api/edit-requests` | `status` (mặc định `pending`, có `all`), `company?`, `op?`, `q?` (tìm trong đơn vị/tiêu đề/lý do), `page`, `page_size` | `Paged` |
| GET | `/api/edit-requests/pending-count` | | `{count}` |
| GET | `/api/edit-requests/{id}` | | `{request, current, changed_since_submit: boolean, still_blocked: boolean \| null, labels: Record<field, Record<rawValue, label>>, lock: {locked_until: string \| null, will_unlock: {round_id, lock_date}[]}}` |
| POST | `/api/edit-requests/{id}/approve` | `{note?: string, expected_updated_at: string, accept_changed?: boolean}` | `{request}` |
| POST | `/api/edit-requests/{id}/reject` | `{note: string, expected_updated_at: string}` (note bắt buộc, trim ≥ 3) | `{request}` |
| GET | `/api/edit-requests/{id}/file/{name}` | `filename?` | file hợp đồng — CHỈ khi `name` xuất hiện trong payload hoặc before của đề nghị |

Chi tiết:
- `still_blocked`: `null` = không kiểm được (vd tài khoản người gửi bị khoá, bản ghi đã mất).
- `labels` (chỉ op hợp đồng; op khác `{}`): `customer_id` → tên khách, `parent_id`/`master_id` → số HĐ,
  `delivery_type`/`contract_type`/`channel` → nhãn tiếng Việt; `to_company` giữ nguyên. Khoá giá trị là chuỗi (`String(value)`).
- `lock.will_unlock` rỗng khi đề nghị không còn chờ hoặc op không thuộc chốt (`market_demand`). Ngày tính gỡ
  chốt = `request.dates` ∪ ngày tính lại trên bản ghi hiện tại (khi duyệt, `dates` của đề nghị được cập nhật theo).

Duyệt / từ chối — `expected_updated_at` = `request.updated_at` người duyệt đang xem (so theo thời điểm, lệch
< 1 ms coi là một): thiếu/sai định dạng (không có múi giờ) ⇒ `400`; khác ⇒ `409` "Đơn vị vừa cập nhật đề nghị
này — tải lại để xem nội dung mới.". Duyệt khi bản ghi đã đổi kể từ lúc gửi (`changed_since_submit`) mà
không có `accept_changed: true` ⇒ `409` "Số liệu đã thay đổi kể từ lúc đơn vị gửi đề nghị — xem cột Hiện
tại rồi xác nhận ghi đè."

Duyệt: `409` nếu không còn `pending`; áp dụng lỗi (ValueError/HTTPException của repo) ⇒ trả đúng
mã + câu lỗi, đề nghị VẪN `pending` (người duyệt sửa được bằng cách từ chối kèm ghi chú). ⚠ Các bước
ghi không chung một transaction: lỗi giữa chừng thì phần đã ghi không hoàn tác.

## 5. Web — routes & menu
- Đơn vị: `/de-nghi-sua` — "Đề nghị sửa số liệu" (menu đơn vị).
- Ban: `/duyet-de-nghi-sua` (danh sách) + `/duyet-de-nghi-sua/:id` (chi tiết) — `RequireCap edit_request`, menu "Duyệt đề nghị sửa" kèm số đang chờ.
- Link trong email: `{APP_BASE_URL}/duyet-de-nghi-sua/{id}` (Ban) · `{APP_BASE_URL}/de-nghi-sua` (đơn vị).

## 6. Web — giao diện dùng chung cho các màn (phase 3 dùng, phase 2 cung cấp)
```ts
// lib/http.ts
export class ApiError extends Error { status: number; blocked: "window" | "lock" | null }
export function isEditBlocked(e: unknown): e is ApiError   // e instanceof ApiError && e.blocked != null

// lib/edit-request-client.ts — mọi hàm gọi API + type ở mục 2

// lib/use-edit-request.tsx
export interface EditRequestDraft {
  op: EditRequestOp; payload: Record<string, unknown>;
  title: string;        // hiện trong popup: "Biểu Thu mua ngày 01/08/2026"
  company: string; dates: string[];
}
export function useEditRequest(): {
  /** Thử lưu trực tiếp. Tài khoản đơn vị + server chặn vì hàng rào thời gian ⇒ mở popup gửi đề nghị.
   *  Tài khoản khác / lỗi khác ⇒ ném lại như cũ. */
  saveOrRequest(direct: () => Promise<unknown>,
                draft: EditRequestDraft | (() => EditRequestDraft)): Promise<"saved" | "requested" | "cancelled">;
  /** Mở thẳng popup (màn đã biết chắc bản ghi đang khoá). */
  request(draft: EditRequestDraft): Promise<"requested" | "cancelled">;
  modal: React.ReactNode;   // component gọi hook phải render {modal}
};
```
Popup (`components/EditRequestSubmitModal.tsx`): tiêu đề "Gửi đề nghị sửa số liệu", dòng nội dung
`title`, ô **Lý do chỉnh sửa** (bắt buộc), các lưu ý ĐỎ (`.form-note`):
1. "Thay đổi chỉ được áp dụng sau khi Ban duyệt. Trước đó số liệu vẫn giữ nguyên."
2. Nếu đơn vị đã chốt tới ngày ≥ ngày sửa sớm nhất (popup tự gọi `fetchLockCurrent`): "Ngày sửa nằm
   trong kỳ đơn vị đã chốt (đến hết dd/mm/yyyy). Khi Ban duyệt, phần chốt từ ngày dd/mm/yyyy sẽ bị gỡ —
   đơn vị phải rà lại và xác nhận chốt số liệu lần nữa."
   Không bị chốt thì vẫn nhắc ngắn: "Sau khi Ban duyệt, đơn vị tự rà lại số liệu và xác nhận chốt ở đợt chốt kế tiếp."
Gửi thành công ⇒ `message.success("Đã gửi đề nghị — chờ Ban duyệt.")` (replaced ⇒ "Đã cập nhật đề nghị đang chờ duyệt.").
