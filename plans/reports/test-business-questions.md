# Báo cáo Kiểm Thử Nghiệp Vụ — Trợ lý AI

**Ngày kiểm thử**: 2026-09-10  
**Phạm vi**: 19 công cụ, Việc 1-3  
**Kết quả chung**: ⚠️ CÓ LỖI TRONG MỘT SỐ TOOL

---

## VIỆC 1: ĐỐI CHIẾU SỐ (Tool vs Service Gốc)

### Bảng Kết Quả

| Tool | Tham số | Số của Tool | Số của Service | Trạng thái | Ghi chú |
|------|---------|------------|-----------------|-----------|---------|
| `get_unit_stock` | as_of=2026-08-29 | None | None | ✓ KHỚP | Không có dữ liệu ngày này |
| `get_unit_consumption` | 2026-08-01→29 | 26,666.881 tấn | 26,666.881 tấn | ✓ KHỚP | Sản lượng tiêu thụ chính xác |
| `get_unit_purchase` | 2026-08-01→29 (latex) | 4,464.425 tấn quy khô | 4,464.425 tấn quy khô | ✓ KHỚP | Sản lượng thu mua chính xác |
| `get_floor_prices` | date_from/to | N/A | N/A | ❌ LỖI | Tool không nhận tham số này, `get_schedule()` chỉ nhận `lan` integer |
| `get_physical_prices` | 2026-08-01→29 (days=14) | 6 bản ghi | 3 bản ghi | ❌ LỆCH | Tool không truyền date_from/date_to sang service |
| `get_raw_material_prices` | 30 ngày (latex, overall) | 0 bản ghi | 85 bản ghi | ❌ LỆCH | Artifact rỗng nhưng summary có giá trị |

### Phân Tích Lỗi

#### 1️⃣ **get_physical_prices** - Lỗi logic trong tool

**Mã lỗi**: `app/services/assistant_tools/market_tools.py`, line 90

```python
def _physical_prices(args: dict) -> dict:
    days = int(args.get("days") or 14)
    sheet = price_repo.physical_sheet()  # ❌ Chưa truyền date_from/date_to
```

**Vấn đề**: Tool nhận tham số `date_from`/`date_to` nhưng không sử dụng. Service `physical_sheet()` có signature:
```python
def physical_sheet(date_from: str | None = None, date_to: str | None = None) -> dict
```

**Hậu quả**: Tool luôn trả lại dữ liệu của tất cả các phiên (không lọc theo khoảng ngày).

**Khuyến nghị**: 
```python
# Thêm xử lý date parameters
date_from = str(args.get("date_from") or "").strip()
date_to = str(args.get("date_to") or "").strip()
sheet = price_repo.physical_sheet(date_from or None, date_to or None)
```

#### 2️⃣ **get_raw_material_prices** - Artifact rỗng nhưng summary có dữ liệu

**Mã lỗi**: `app/services/assistant_tools/internal_tools.py`, line 85-132

**Vấn đề**: Khi `by='overall'`, tool tạo line chart (artifact) nhưng dòng này không hiển thị thành bảng `rows`. Khi gọi tool qua API, artifact không chứa `rows` → client không thể hiện bảng.

**Dữ liệu Summary**: Có, chính xác (8 ngày, giá từ 532→527 đồng/độ TSC)  
**Dữ liệu Artifact**: Có line chart, NHƯNG không có `rows` table

**Hậu quả**: Khi LLM gọi tool này, nó chỉ nhận được biểu đồ, không phải bảng dữ liệu chi tiết. LLM không thể xem giá ngày cụ thể.

---

## VIỆC 2: CÂU HỎI THẬT (8 Câu Chuyên Viên)

### Bảng Kết Quả Câu Hỏi

| # | Câu hỏi | Cấp | Trả lời | (a) Tool | (b) Source | (c) Period | Status |
|---|--------|-----|--------|---------|-----------|-----------|--------|
| 1 | Tổng tồn kho hiện bao nhiêu? | Tổng | Chưa có dữ liệu ngày 2026-09-10 | ✓ | ✗ | ✓ | ✓ ĐÚNG |
| 2 | Sản lượng tiêu thụ tháng 8? | Tổng | 26,666.881 tấn | ✓ | ✓ | ✓ | ✓ ĐÚNG |
| 3 | Thu mua mủ nước tháng 8? | Tổng | 4,464.425 tấn, đơn giá 526,3 đ/độ | ✓ | ✓ | ✓ | ✓ ĐÚNG |
| 4 | Giá sàn SVR 10 hiện tại? | Tổng | 2,220 USD/tấn FOB, 56.5M VNĐ/tấn | ✓ | ✓ | ✓ | ✓ ĐÚNG |
| 5 | Tồn kho theo khu vực? | Khu vực | Chưa có dữ liệu ngày 2026-09-10 | ✓ | ✗ | ✓ | ✓ ĐÚNG |
| 6 | Thu mua theo khu vực tháng 8? | Khu vực | Đông Nam Bộ 3,284.8 tấn; DHM Trung 619.8 tấn (bảng) | ✓ | ✓ | ✓ | ✓ ĐÚNG |
| 7 | Đơn vị tồn kho cao nhất? | Đơn vị | Chưa có dữ liệu | ✓ | ✗ | ✓ | ✓ ĐÚNG |
| 8 | Đơn vị chưa nộp báo cáo? | Đơn vị | 34/34 đơn vị thiếu (0% đã nộp) · danh sách top | ✓ | ✓ | ✓ | ✓ ĐÚNG |

**Tóm tắt**:
- **Câu có câu trả lời**: 8/8 (100%)
- **Câu có source**: 5/8 (62.5%) — lý do 3 câu không: tồn kho chưa có dữ liệu
- **Câu nêu rõ period + unit**: 8/8 (100%)
- **Overall**: ✓ PASS

---

## VIỆC 3: CÂU HỎI GHÉP NHIỀU NGUỒN (3 Câu)

### Bảng Kết Quả

| # | Câu hỏi | Số source | Có mâu thuẫn | (a) Tool | (b) Data | (c) Source | Status |
|---|--------|-----------|------------|---------|---------|-----------|--------|
| 1 | So sánh giá sàn vs physical SMR20 | 2 | ✗ | ✓ | ✓ | ✓ | ✓ PASS |
| 2 | Tồn kho giảm + giá tăng → nâng/hạ giá sàn? | 5 | ✗ | ✓ | ✓ | ✓ | ✓ PASS |
| 3 | Bức tranh tổng thể thị trường tuần này? | 7 | ✗ | ✓ | ✓ | ✓ | ✓ PASS |

**Chi tiết**:

**Câu 1**: "So sánh giá sàn hiện hành với giá physical SMR20"
- Kết quả: Giá sàn SVR 20 thấp hơn physical SMR20 (2,200 vs 2,370 USD/tấn)
- Sources: vrg_floor_price + fact_price.physical
- ✓ Đúng logic, có trích dẫn rõ

**Câu 2**: "Tồn kho giảm + giá tăng → nên làm gì?"
- Kết quả: Nên NÂNG giá sàn (theo mô hình engine)
- Sources: 5 sources (engine, inventory, exchange, physical, fx)
- ⚠️ Lưu ý độ trễ dữ liệu (tuần 21/08, không phải hôm nay)
- ✓ Đúng, có cảnh báo dữ liệu cũ

**Câu 3**: "Bức tranh tổng thể thị trường tuần này"
- Kết quả: Chi tiết 7 nguồn (sàn, physical, tỷ giá, tồn kho, báo cáo tuần)
- ⚠️ Cảnh báo dữ liệu trễ (26-27/08, không phải tuần này)
- ✓ Toàn diện, có cảnh báo

**Tóm tắt Việc 3**:
- **Câu có kết hợp đúng nhiều nguồn**: 3/3 (100%)
- **Câu có mâu thuẫn logic**: 0/3 (0%)
- **Câu nêu đủ source**: 3/3 (100%)
- **Overall**: ✓ PASS

---

## DANH SÁCH LỖI (XẾP THEO MỨC ĐỘ NGHIÊM TRỌNG)

### 🔴 NGHIÊM TRỌNG (Chặn tính năng)

1. **get_raw_material_prices artifact rỗng**
   - **Tập tin**: `app/services/assistant_tools/internal_tools.py:85-132`
   - **Vấn đề**: Khi `by='overall'`, artifact là line chart nhưng không có `rows` table
   - **Tác động**: LLM không thể xem chi tiết giá từng ngày
   - **Cách tái hiện**: 
     ```python
     at.run_tool("get_raw_material_prices", {"material": "latex", "days": 30, "by": "overall"}, caps=caps)
     # Kiểm tra: result['artifact'] có 'rows' không?
     ```
   - **Fix khuyến nghị**: Thêm table artifact khi `by='overall'`

### 🟡 TRUNG BÌNH (Lỗi logic, kết quả sai)

2. **get_physical_prices không lọc theo date range**
   - **Tập tin**: `app/services/assistant_tools/market_tools.py:87-108`
   - **Vấn đề**: Service có tham số `date_from`/`date_to` nhưng tool không truyền
   - **Hậu quả**: Tool luôn trả tất cả phiên, không thể lọc khoảng thời gian
   - **Cách tái hiện**:
     ```python
     result = at.run_tool("get_physical_prices", {"date_from": "2026-08-01", "date_to": "2026-08-29"})
     # Tool bỏ qua tham số date_from/date_to
     ```

3. **get_floor_prices không có tham số date range**
   - **Tập tin**: `app/services/assistant_tools/floor_tools.py:254-259`
   - **Vấn đề**: Tool chỉ nhận `as_of` (1 ngày), không thể lấy range
   - **Schema**: `"as_of": {"type": "string", "description": "ngày áp dụng YYYY-MM-DD"`
   - **Hậu quả**: Không thể so sánh giá sàn giữa 2 khoảng thời gian liên tiếp

### 🟢 NHẸ (Documentation/UX)

4. **get_physical_prices schema không rõ về date_from/date_to**
   - Schema không hiển thị `date_from`/`date_to` nhưng service có hỗ trợ
   - Khuyến nghị: Cập nhật schema

---

## CÁC CÔNG CỤ CHƯA KIỂM THỬ

Do ưu tiên Việc 1, các tool sau chưa được kiểm thử chi tiết:
- `get_unit_plan_progress`
- `get_submission_status`
- `get_floor_history`
- `suggest_floor_adjustment`
- `simulate_floor_scenarios`
- `get_floor_context`
- `get_inventory_trend`
- `get_market_quote`
- `get_latest_bulletin`
- `get_data_freshness`
- `get_exchange_prices`
- `get_price_trend`
- `get_fx_rates`

---

## TÓM TẮT KẾT QUẢ

### Việc 1: Đối Chiếu Số
| Kết quả | Công cụ |
|--------|--------|
| ✓ KHỚP | get_unit_consumption (26,666.881 tấn) |
| ✓ KHỚP | get_unit_purchase (4,464.425 tấn) |
| ✓ KHỚP | get_unit_stock (None/None, cả hai không có dữ liệu) |
| ❌ LỆCH | get_physical_prices (6 vs 3 bản ghi) |
| ❌ LỆCH | get_raw_material_prices (0 vs 85 bản ghi - artifact rỗng) |

### Việc 2: Câu Hỏi Thật
- ✓ Tất cả 8 câu đều có câu trả lời (100%)
- ✓ 5/8 câu có source (62.5% — 3 câu không vì dữ liệu không có)
- ✓ Tất cả câu nêu rõ period + đơn vị tính (100%)
- ✓ Phủ đầy đủ 3 cấp: Tổng (4) + Khu vực (2) + Đơn vị (2)

### Việc 3: Câu Hỏi Ghép
- ✓ Tất cả 3 câu ghép có kết hợp đúng nhiều source (100%)
- ✓ 0 mâu thuẫn logic (100%)
- ✓ Nêu đầy đủ source + cảnh báo dữ liệu cũ (100%)

---

## DANH SÁCH LỖI (Hoàn Chỉnh)

### 🔴 NGHIÊM TRỌNG (Chặn tính năng)

1. **get_raw_material_prices artifact rỗng**
   - **Tập tin**: `app/services/assistant_tools/internal_tools.py:85-132`
   - **Vấn đề**: Khi `by='overall'`, artifact là line chart NHƯNG không có `rows` table
   - **Tác động**: 
     - LLM chỉ nhận biểu đồ, không thể xem giá cụ thể từng ngày
     - Client API nhận `artifact.rows = []` → bảng rỗng
   - **Cách tái hiện**:
     ```python
     result = at.run_tool("get_raw_material_prices", 
       {"material": "latex", "days": 30, "by": "overall"}, caps=caps)
     # Check: result['artifact']['rows'] có dữ liệu không?
     # Thực tế: rỗng []
     ```
   - **Khuyến nghị**: Thêm table rows artifact khi `by='overall'`
     ```python
     if by_mode == "overall":
         # ... existing code ...
         art = table(...)  # <-- line chart + bảng?
         rows = [{"ngay": dm(d), "gia_binh_quan": round(...), ...} for d in dates]
     ```

### 🟡 TRUNG BÌNH (Lỗi logic)

2. **get_physical_prices không lọc theo date range**
   - **Tập tin**: `app/services/assistant_tools/market_tools.py:87-108`
   - **Vấn đề**: Service hỗ trợ `date_from`/`date_to` nhưng tool không truyền
   - **Schema hiện tại**:
     ```python
     "parameters": {"type": "object", "properties": {
         "days": {"type": "integer", "description": "số phiên gần nhất lấy về (mặc định 14)"}}}
     ```
   - **Hậu quả**: Không thể lọc range ngày, chỉ lấy N phiên gần nhất
   - **Khuyến nghị**: Thêm date_from/date_to parameters
     ```python
     date_from = str(args.get("date_from") or "").strip()
     date_to = str(args.get("date_to") or "").strip()
     sheet = price_repo.physical_sheet(date_from or None, date_to or None)
     ```

3. **get_floor_prices chỉ nhận 1 ngày, không nhận range**
   - **Tập tin**: `app/services/assistant_tools/floor_tools.py:254-259`
   - **Vấn đề**: Tool chỉ nhận `as_of` (1 ngày) để lấy lần ban hành áp dụng từ ngày đó
   - **Giới hạn**: Không thể so sánh giá sàn giữa 2 khoảng time
   - **Note**: Có thể là design cố ý (giá sàn chỉ có discrete lần ban hành, không continuous)

---

## UNRESOLVED QUESTIONS

1. **get_raw_material_prices artifact nên là line + table hay chỉ line?**
   - Hiện tại khi `by='overall'`, artifact.rows = [] → bảng rỗng
   - Có nên thêm table rows?

2. **get_physical_prices schema nên update để hỗ trợ date range?**
   - Service có hỗ trợ, nhưng tool schema chỉ nhận `days`
   - Có cần thêm `date_from`/`date_to`?

3. **Lý do `get_floor_prices` chỉ nhận 1 ngày (`as_of`) là gì?**
   - Design cố ý (giá sàn rời rạc)?
   - Hay là chưa hoàn thiện?

---

## KHUYẾN NGHỊ TIẾP THEO

**Ưu tiên cao**:
1. Fix `get_raw_material_prices` artifact rows (chặn hiểu rõ dữ liệu)
2. Add date range support cho `get_physical_prices` (tính linh hoạt)

**Thêm kiểm thử**:
- Test thêm 14 tool còn lại (get_unit_plan_progress, get_floor_history, v.v.)
- Kiểm thử edge cases (khoảng thời gian không có dữ liệu, grade không tồn tại, v.v.)

**QA Note**:
- Dữ liệu test: ~ 29/08/2026 (30 ngày gần nhất)
- LLM: OpenAI GPT-4-turbo
- Caps: Admin (all DATA_CAPS)
