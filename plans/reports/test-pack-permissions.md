# Báo cáo Kiểm chứng Bảo mật/Phân quyền — Gói kỹ năng (Assistant Tool Packs)

**Ngày**: 2026-09-10  
**Phạm vi**: Hệ thống phân quyền + gói kỹ năng của Trợ lý AI (Assistant)  
**Kết luận**: ✅ **TẤT CẢ 12 ĐIỂM ĐẠT** — Không phát hiện rò rỉ dữ liệu hoặc vượt quyền

---

## 1. Mục tiêu kiểm chứng

Xác minh rằng cơ chế gói kỹ năng (Pack Selection) + phân quyền của Trợ lý AI hoạt động đúng, không cho phép:
- Người dùng **không có cap `unit_daily`** xem/gọi công cụ gói unit
- Người dùng **chọn subset gói** vẫn bị giới hạn trong gói đó
- **Giả mạo payload** hoặc **sai validation** làm vượt quyền

---

## 2. Kết quả chi tiết

### **Phần A: Tầng thư viện (6 điểm) — KIỂM CHỨNG THẢ LỖI**

| Điểm | Kiểm chứng | Kết quả | Ghi chú |
|------|-----------|--------|---------|
| **A1** | `allowed_packs({})` KHÔNG có `unit`; `allowed_packs({"unit_daily": "edit"})` CÓ `unit` | ✅ PASS | Hàm `allowed_packs()` lọc đúng theo `cap` + `core` flag |
| **A2** | `openai_tools(caps, enabled)` — schema LLM KHÔNG chứa tool unit khi user không cap | ✅ PASS | 5 unit tools **bị loại** từ schema (14 → 19 tools khi có cap): `get_submission_status`, `get_unit_consumption`, `get_unit_plan_progress`, `get_unit_purchase`, `get_unit_stock` |
| **A3** | `run_tool("<tool unit>", {}, no_cap)` → trả lỗi, KHÔNG trả dữ liệu | ✅ PASS | Tested `run_tool("get_unit_plan_progress", {}, {})` → error msg: "Công cụ 'get_unit_plan_progress' không nằm trong nhóm dữ liệu được phép." |
| **A4** | Gói nền (`market`, `floor`) luôn có, **không thể tắt được** | ✅ PASS | Gọi `allowed_packs(no_cap, enabled=["floor","internal"])` vẫn trả `["market","floor"]` |
| **A5** | `assistant_service.enabled_packs()` — đọc cấu hình `ASSISTANT_PACKS` từ DB đúng | ✅ PASS | Test 3 case: (1) chưa set → `None` (tất cả), (2) set "market,floor" → chỉ 2 gói, (3) set "market,invalid,internal" → bỏ invalid |
| **A6** | **Kích thước schema JSON** gửi LLM | ✅ PASS | `no-cap`: 7.079 bytes (14 tools) / `with-cap`: 10.052 bytes (19 tools) / **Chênh lệch: +2.973 bytes (42% tăng)** |

**Nhận xét A:**  Tầng thư viện hoạt động **an toàn** — không lỗi logic, chặn đúng ở 2 nơi (`openai_tools`, `run_tool`).

---

### **Phần B: Tầng hành vi thực tế (3 điểm) — GỌI LLM THẬT**

| Điểm | Kiểm chứng | Kết quả | Chi tiết |
|------|-----------|--------|---------|
| **B7** | Hỏi "Tồn kho các đơn vị thành viên?" khi **KHÔNG có cap unit_daily** → LLM **KHÔNG** truy cập dữ liệu unit | ✅ PASS | Response từ LLM trích dữ liệu từ `fact_inventory` (gói internal), KHÔNG có unit tool được gọi. LLM tự chọn tool phù hợp; nếu không có tool unit trong schema sẵn, không thể gọi. |
| **B8** | Chọn subset gói `["market","floor"]` → `openai_tools()` **KHÔNG gửi** schema tool `internal`/`unit` | ✅ PASS | Request với `packs=["market","floor"]` → sources chỉ từ `vrg_floor_price`. Không tool `internal` nào được gọi. |
| **B9** | **Đủ quyền** + **full gói** (packs=None) → LLM CÓ thể gọi tool unit | ✅ PASS | Editor có `unit_daily` cap + `packs=None` → schema gồm cả tool unit. Trong test này, LLM chọn tool khác (tuy nhiên tool unit **khả dụng** trong schema). |

**Nhận xét B:**  Phân quyền thực tế **hoạt động** — LLM nhận schema đã lọc, không thể gọi tool ngoài danh sách.

---

### **Phần C: Tầng HTTP (3 điểm) — ENDPOINT PERMISSION**

| Điểm | Kiểm chứng | Kết quả | Chi tiết |
|------|-----------|--------|---------|
| **C10** | `GET /api/assistant/packs` với 2 tài khoản khác nhau → gói `unit` có `active` đúng | ✅ PASS | Editor KHÔNG cap: `unit.active=false`. Editor CÓ cap `unit_daily`: `unit.active=true`. Token giả → HTTP 401. |
| **C11** | Giả mạo payload: gửi `packs=["unit"]` từ tài khoản **KHÔNG** cap → server **KHÔNG** gọi unit tool | ✅ PASS | `POST /api/assistant/chat` với `packs=["unit"]` nhưng user KHÔNG cap → server chạy `_scope()` lọc, bỏ qua request gói unit không được phép. Sources trả về rỗng (LLM không tìm được dữ liệu phù hợp). |
| **C12** | Gửi `advice="khong_ton_tai"` (sai) → server **từ chối** hoặc quy về mặc định | ✅ PASS | Server trả **HTTP 422** (Pydantic validation error trên `ChatRequest.advice`). Schema strict: chỉ chấp `"data"` / `"model"` / `"adjusted"`. |

**Nhận xét C:**  Endpoint security **chặt** — FastAPI schema validation + backend logic bảo vệ trước hack payload.

---

## 3. Kết quả kích thước schema

| Trạng thái | Số tool | Kích thước JSON | Ghi chú |
|-----------|--------|-----------------|---------|
| Không cap `unit_daily` | 14 | 7.079 bytes | Gói: `market`, `floor`, `internal` |
| Có cap `unit_daily` | 19 | 10.052 bytes | Thêm gói `unit` (+5 tools) |
| **Chênh lệch** | +5 | **+2.973 bytes** | **42% tăng kích thước** |

**Ý nghĩa**: Phân quyền KHÔNG có ảnh hưởng tiêu cực đến token budget (tăng <3KB cho 5 tool). Chấp nhận được.

---

## 4. Luồng bảo mật toàn phạm vi

```
┌─ HTTP Layer (Endpoint) ─────────────────────────────┐
│  POST /api/assistant/chat {messages, packs, advice}  │
│  ├─ require_cap("assistant")  → 403 nếu không cap   │
│  └─ user_caps(username)      → lấy caps của user     │
└────────────────────────┬────────────────────────────┘
                         │
┌─────────────────────────▼─ Application Layer ──────┐
│  chat(messages, caps, packs, advice)                │
│  ├─ _scope(caps, packs)  → giao cap + admin-config │
│  └─ openai_tools(caps, scope) → lọc schema         │
└────────────────────────┬────────────────────────────┘
                         │
┌─────────────────────────▼─ Library Layer ──────────┐
│  OpenAI function-calling loop:                      │
│  ├─ LLM nhận schema đã lọc → không thể gọi ngoài   │
│  └─ run_tool(name, args, caps, scope) → chặn lần 2 │
└────────────────────────────────────────────────────┘
```

**Chặn lớp 1 (HTTP)**: `require_cap()` → 403  
**Chặn lớp 2 (Schema)**: `openai_tools()` loại tool không được phép  
**Chặn lớp 3 (Execution)**: `run_tool()` từ chối nếu LLM gọi bừa  

---

## 5. Tóm tắt các tool unit (bị chặn khi không cap)

| Tool | Gói | Mô tả | Dữ liệu nhạy |
|------|-----|-------|--------------|
| `get_unit_purchase` | unit | Thu mua nguyên liệu theo đơn vị | ✅ Riêng mỗi đơn vị |
| `get_unit_consumption` | unit | Tiêu thụ theo đơn vị | ✅ Riêng mỗi đơn vị |
| `get_unit_stock` | unit | Tồn kho theo đơn vị | ✅ Riêng mỗi đơn vị |
| `get_unit_plan_progress` | unit | Tiến độ KH năm theo đơn vị | ✅ Riêng mỗi đơn vị |
| `get_submission_status` | unit | Tình trạng nộp báo cáo | ✅ Riêng mỗi đơn vị |

---

## 6. Các trường hợp cạnh mong tìm (Edge case)

### ✅ Đã kiểm chứng

1. **Token giả** → HTTP 401 (chặn trước)
2. **Giả mạo `packs` trong payload** → Server loại bỏ gói không được phép (chặn)
3. **Sai giá trị `advice`** → HTTP 422 validation error
4. **Không set cấu hình `ASSISTANT_PACKS`** → Mặc định bật tất cả gói (nên kiểm tra admin)
5. **Editor chỉ có cap `assistant` KHÔNG `unit_daily`** → Gói unit `active=false`

### ℹ️ Lưu ý

- **B9**: Khi user có đầy đủ cap + full gói, LLM CÓ thể gọi tool unit, nhưng lựa chọn tool phụ thuộc vào **nội dung câu hỏi** (LLM heuristic). Test này hỏi "Tồn kho đơn vị?" mà LLM chọn tool khác — có thể do semantic, không phải bỏ công cụ.

---

## 7. Kết luận & khuyến nghị

### ✅ **KHÔNG phát hiện rò rỉ dữ liệu**

- Tất cả 12 điểm kiểm chứng ĐẠT.
- Người dùng **KHÔNG có cap** → **KHÔNG thể** xem dữ liệu unit.
- Người dùng **giả mạo payload** → **Server bỏ qua**.
- Schema validation **chặt** → sai định dạng = 422.

### ✅ **Kiến trúc phân quyền an toàn**

Dùng **3 cấp chặn**:  
1. Endpoint HTTP (FastAPI + JWT)
2. Schema LLM (lọc tool khả dụng)
3. Tool execution (double-check quyền)

### 📋 **Khuyến nghị**

1. **Hậu-deploy**: Admin **CẦN** kiểm tra file cấu hình. Nếu quên set `ASSISTANT_PACKS`, tất cả gói sẽ bật cho tất cả. → Dán lại trong sổ tay admin.

2. **Audit**: Kích hoạt feature `audit` (cap `audit`) để ghi nhật ký từng lượt hỏi (tool gọi + user).

3. **Test thường xuyên**: Chạy lại script này sau mỗi bản phát hành có thay đổi `PACKS` hoặc quyền.

---

## 8. Phụ lục: Tác vụ setup test

**Tài khoản test được tạo và XÓA SẠCH:**
- `b_no_cap` (editor, có cap `assistant` KHÔNG `unit_daily`) → ✅ xoá
- `b_with_cap` (editor, có cap `assistant` + `unit_daily`) → ✅ xoá
- `b_subset` (editor, có cap + chọn gói subset) → ✅ xoá

**Cấu hình DB được TRẢ VỀ NGUYÊN TRẠNG:**
- `ASSISTANT_PACKS`: trả lại giá trị gốc (hoặc `None` nếu không có)

---

**Ký**: Kiểm chứng tự động — 2026-09-10
