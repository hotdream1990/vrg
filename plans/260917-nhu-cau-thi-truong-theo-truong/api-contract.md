# Hợp đồng API — Nhu cầu thị trường theo trường (phiếu có tình trạng)

Nguồn sự thật chung cho nhánh Backend (A) và Web (B). Đổi gì ở đây thì báo agent chính.

## 1. Bảng dữ liệu (DDL thêm vào `apps/api/app/core/db.py`, ngay sau khối `market_demand`)

```sql
-- Nhu cầu thị trường THEO TRƯỜNG (17/09/2026): mỗi dòng = MỘT nhu cầu của MỘT chủng loại, có tình
-- trạng cập nhật về sau. Thay cho ô chữ tự do `market_demand` (bảng cũ giữ lại để tra lịch sử).
CREATE TABLE IF NOT EXISTS market_demand_item (
    id                bigserial PRIMARY KEY,
    company           text NOT NULL,                 -- đơn vị thành viên ghi nhận
    as_of             date NOT NULL,                 -- ngày nhận nhu cầu
    customer          text NOT NULL,                 -- khách hỏi mua (gõ tự do)
    grade             text NOT NULL,                 -- chủng loại (UNIT_GRADES)
    qty               numeric,                       -- số lượng (không bắt buộc)
    qty_unit          text NOT NULL DEFAULT 'ton',   -- ton | container
    price             numeric,                       -- đơn giá (không bắt buộc)
    currency          text NOT NULL DEFAULT 'VND',   -- VND = triệu đồng/tấn · USD = USD/tấn
    price_provisional boolean NOT NULL DEFAULT false,-- giá tạm tính
    delivery_place    text NOT NULL DEFAULT '',
    delivery_from     date,
    delivery_to       date,
    status            text NOT NULL DEFAULT 'open',  -- open | signed | failed
    contract_no       text NOT NULL DEFAULT '',
    contract_date     date,
    note              text NOT NULL DEFAULT '',
    source_key        text,                          -- khoá chống nhập trùng khi chuyển dữ liệu cũ
    created_at        timestamptz NOT NULL DEFAULT now(),
    created_by        text,
    updated_at        timestamptz NOT NULL DEFAULT now(),
    updated_by        text
);
CREATE INDEX IF NOT EXISTS ix_mdi_company_date ON market_demand_item (company, as_of DESC);
CREATE INDEX IF NOT EXISTS ix_mdi_date ON market_demand_item (as_of DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_mdi_source_key ON market_demand_item (source_key)
    WHERE source_key IS NOT NULL;
```
⚠ KHÔNG viết `:tên` trong comment SQL (SQLAlchemy `text()` hiểu là bind parameter → hỏng `ensure_schema`).

## 2. Danh mục (backend `apps/api/app/core/market_demand_meta.py`, web `apps/web/src/lib/market-demand-meta.ts`)

| Khoá | Giá trị → nhãn |
|---|---|
| `QTY_UNITS` | `ton` → "tấn" · `container` → "container" |
| `CURRENCIES` | `VND` → "triệu đồng/tấn" · `USD` → "USD/tấn" |
| `STATUSES` | `open` → "Đang đàm phán" · `signed` → "Đã ký hợp đồng" · `failed` → "Không thành" |
| Chủng loại | `market_meta.UNIT_GRADES` (server trả trong `grades`) |
| Trần giá | VND ≤ 1000 (triệu đ/tấn) · USD ≤ 20000 — vượt ⇒ 400 "Đơn giá tính bằng TRIỆU đồng/tấn (vd 40 = 40 triệu)" / "…USD/tấn" |

**Ô NỘI DUNG** (bị cửa sổ nhập liệu chặn): `company, as_of, customer, grade, qty, qty_unit, price,
currency, price_provisional, delivery_place, delivery_from, delivery_to`.
**Ô THEO DÕI** (sửa bất cứ lúc nào, MIỄN cửa sổ): `status, contract_no, contract_date, note`.

## 3. Kiểu dữ liệu

`DemandItem` (server trả):
```json
{"id": 12, "company": "Công ty Cổ phần Cao Su Tây Ninh", "as_of": "2026-09-17",
 "customer": "Công ty TNHH Cao Su Anh Dũng", "grade": "LATEX",
 "qty": 100.0, "qty_unit": "ton", "price": 40.0, "currency": "VND", "price_provisional": false,
 "delivery_place": "Tại kho", "delivery_from": null, "delivery_to": "2026-11-30",
 "status": "signed", "contract_no": "1752", "contract_date": "2026-09-17",
 "note": "", "legacy": false,
 "created_at": "…", "created_by": "…", "updated_at": "…", "updated_by": "…"}
```
`legacy` = `source_key IS NOT NULL` (dòng chuyển từ bản chữ cũ).

`DemandItemIn` (thân PUT; `id` rỗng = thêm mới) — đủ các ô trên trừ `legacy/created_*/updated_*`.
Ngày dạng `YYYY-MM-DD`. Luật (400 kèm câu tiếng Việt):
- `customer` bỏ khoảng trắng, không rỗng, ≤ 200 · `grade` ∈ UNIT_GRADES · `qty`, `price` ≥ 0 hoặc null
- `delivery_place` ≤ 200 · `note` ≤ 2000 · `contract_no` ≤ 60
- `as_of` không ở tương lai (kể cả admin) · `delivery_to` ≥ `delivery_from` khi có cả hai
- `status = signed` ⇒ bắt buộc `contract_no` + `contract_date` (ngày ký không ở tương lai)
- `status ≠ signed` ⇒ server XOÁ `contract_no`/`contract_date` trước khi lưu
- Trần giá theo §2

## 4. Endpoint

### Tài khoản đơn vị (`/api/member/market-demand`, `get_unit_user`, lãnh đạo đơn vị chỉ GET)
| Method | Path | Mô tả |
|---|---|---|
| GET | `/items?date_from&date_to&status&grade&q` | Phạm vi ĐỌC = `_scope(member)` (gồm đơn vị đã sáp nhập vào). Mặc định `date_from` = hôm nay − 90, `date_to` = hôm nay. `q` tìm trong khách hàng/ghi chú/số HĐ (không phân biệt hoa thường). |
| PUT | `/items` | Ghi 1 phiếu. `company` phải ∈ đơn vị ĐƯỢC GÁN (403). Sửa phiếu có sẵn: phiếu đó cũng phải thuộc đơn vị được gán. |
| DELETE | `/items/{id}` | Xoá 1 phiếu (403/404 tương tự). |

GET trả: `{units, view_only_units, today, edit_window_days, grades, items}`.

### Chuyên viên (`/api/market-demand`, đọc `require_cap("market_demand")`, ghi `require_cap_edit`)
| Method | Path | Mô tả |
|---|---|---|
| GET | `/items?date_from&date_to&company&status&grade&q` | mọi đơn vị |
| PUT | `/items` | `company` ∈ `member_unit_repo.active_names()` |
| DELETE | `/items/{id}` | |

GET trả: `{units, today, edit_window_days, grades, items}` (`edit_window_days` = cửa sổ chuyên viên).

PUT trả `{"item": DemandItem}` · DELETE trả `{"ok": true}`. Bỏ hẳn các endpoint chữ cũ
(`GET/PUT /api/market-demand`, `/api/market-demand/timeline`, `GET/PUT /api/member/market-demand`,
`/api/member/market-demand/timeline`).

### Hàng rào thời gian (cả hai router)
- Thêm mới: `security.assert_edit_window(username, as_of)`.
- Sửa: nếu CHỈ đổi ô THEO DÕI (so ảnh chụp ô NỘI DUNG cũ/mới giống hệt) ⇒ bỏ qua hàng rào; ngược lại
  kiểm cửa sổ cho CẢ `as_of` cũ lẫn `as_of` mới.
- Xoá: kiểm cửa sổ theo `as_of` cũ.
- Bị chặn ⇒ 403 kèm header `X-Edit-Blocked: window` (đã có sẵn trong `assert_editable`) → web mời
  gửi Đề nghị sửa. Nhu cầu KHÔNG nằm trong chốt số liệu.
- Admin miễn (đã có trong `assert_edit_window`).

## 5. Đề nghị sửa số liệu

Op mới (file `apps/api/app/services/edit_request_ops_demand.py`, đăng ký trong `edit_request_ops._registry`):
| op | payload | target_key | blocked | apply |
|---|---|---|---|---|
| `demand_save` | đúng `DemandItemIn` | `demand:{id}` hoặc `demand:new:{company}:{as_of}:{customer.lower()}:{grade}` | `[]` nếu chỉ đổi ô theo dõi; ngược lại cửa sổ ĐƠN VỊ cho `as_of` cũ + mới | ghi phiếu, `updated_by` = người gửi |
| `demand_delete` | `{"id": 12}` | `demand:{id}` | cửa sổ đơn vị theo `as_of` cũ | xoá phiếu |

`lockable=False`, `label` = "Nhu cầu thị trường" / "Xoá nhu cầu thị trường",
title = `"Nhu cầu {customer} · {grade} ngày {dd/mm/yyyy}"` (xoá: `"Xoá nhu cầu …"`).
Op chữ cũ `market_demand` BỎ khỏi backend lẫn web (prod không có đề nghị nào dùng op này).

## 6. Nhật ký hoạt động
`audit_repo.log("market_demand", create|update|delete, key=str(id), before, after, as_of, company)`.
Nhãn ô mới thêm vào `apps/web/src/lib/audit-diff.ts` (`LABELS`): customer "Khách hàng",
qty_unit "Đơn vị số lượng", price_provisional "Giá tạm tính", delivery_place "Giao tại",
delivery_from "Giao từ ngày", delivery_to "Giao đến ngày", status "Tình trạng",
contract_no "Số hợp đồng", contract_date "Ngày ký hợp đồng", customer… (đã có: price, currency,
qty, grade, note, as_of).

## 7. Web — hiển thị
- `qty`: "100 tấn" · "3 container" · null → "—" (số kiểu vi-VN).
- `price`: VND → "40 triệu đ/tấn" · USD → "2.380 USD/tấn"; `price_provisional` → thêm " (tạm tính)".
- Giao: `delivery_from`+`delivery_to` → "01/08 – 30/09/2026"; chỉ `to` → "đến 30/11/2026";
  chỉ `from` → "từ 06/08/2026"; bằng nhau → "06/08/2026".
- Tình trạng: Tag màu (open = xanh dương · signed = xanh lá · failed = xám); signed kèm
  "HĐ 1752 · 17/09/2026".
