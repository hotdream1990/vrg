# Code Review: assistant_tools/contract_tools.py (gói "Hợp đồng & khách hàng")

**Ngày**: 10/09/2026 · **Reviewer**: code-review agent (tự chạy DB local, không đoán)
**Phạm vi**: `apps/api/app/services/assistant_tools/contract_tools.py` (378 dòng, 5 tool) +
đăng ký gói `contract` trong `assistant_tools/__init__.py`.
**Đã đọc**: AGENTS.md, `docs/project/tro-ly-ai-kha-nang.md`, `sales_contract_report.py` (533 dòng),
`master_contract_repo.py`, `unit_report_query.py`, `_common.py`, `permissions.py`, `test_assistant.py`,
report kiểm thử trước đó `plans/reports/test-contract-pack.md` (kết luận "sẵn sàng deploy", KHÔNG
test input lỗi/ngày hỏng — xem phát hiện 🔴 bên dưới, đúng chỗ report kia bỏ sót).

⚠ Lưu ý: `assistant_tools/__init__.py` bị một tiến trình khác sửa (thêm `LIMITS`/`_short_desc`/mở
rộng `pack_summary`) trong lúc tôi đang review — không đụng logic đăng ký gói `contract`
(`cap: "sales_contract"`, `core: False` vẫn nguyên), nên không ảnh hưởng kết luận dưới đây.

## Tóm tắt

Đã CHẠY THỰC (không đoán) trên DB local (clone prod, 6.280 hợp đồng, 3.197 hợp đồng gốc, 3 hồ sơ
mẹ, 4 cặp đơn vị sáp nhập):
- Đối chiếu số `get_contract_summary`/`get_undelivered_volume` với công thức độc lập viết lại bằng
  Python (không dùng lại code của tool) — **khớp chính xác từng đồng/từng tấn**.
- Kiểm tra kiến trúc chống đếm-trùng (hợp đồng mẹ, đợt giao) tại **lớp ghi dữ liệu**
  (`sales_contract_clean.py:140-141`), không chỉ tin comment.
- Đo giờ chạy thật + kiểm cơ chế cảnh báo khi chạm trần 5.000 dòng bằng cách hạ trần giả lập.
- Bắn input lỗi (ngày sai định dạng, ngày lộn ngược, tên đơn vị mơ hồ) qua `run_tool()` thật.

Kết quả: **số liệu đúng, kiến trúc chống đếm-trùng vững** — nhưng có 1 lỗi xử lý input thật (không
phải suy đoán) khiến lộ nguyên văn câu SQL + tên toàn bộ cột bảng `sales_contract` ra khung chat khi
LLM (hoặc người dùng gõ trực tiếp qua API) đưa ngày sai định dạng.

## 🔴 CHẶN DEPLOY (nên vá trước, fix nhỏ/nhanh)

### 1. Ngày không hợp lệ → lộ nguyên văn SQL + toàn bộ schema bảng ra chat

**File**: `contract_tools.py:65-67` (`_undelivered_volume`), `:104-107` (`_contract_deliveries`),
`:163-166` (`_contract_summary`). Gốc: `_common.py:98-106` (`clamp_from`) bắt `ValueError` khi
`date.fromisoformat()` hỏng rồi **trả nguyên `date_from` không hợp lệ**, không báo lỗi — 3 hàm trên
không tự validate thêm, thả thẳng chuỗi xuống `CAST(:df AS date)`.

**Bằng chứng đã chạy** (`run_tool("get_contract_summary", {"date_from": "not-a-date", ...})`):
```
{'error': 'Lỗi khi chạy \'get_contract_summary\': (psycopg.errors.InvalidDatetimeFormat)
invalid input syntax for type date: "not-a-date"\n...[SQL: WITH parent AS (SELECT id, company,
parent_id, master_id, code, customer_id, delivery_type, contract_type, sign_date, expiry_date,
start_date, lines, delivered, delivered_at, channel, to_company, invoice_no, ... FROM
sales_contract WHERE ...) ... ORDER BY sign_date DESC ...]'}
```
Toàn bộ câu SQL nhiều CTE (~3.000 ký tự, đủ tên cột nội bộ + comment nghiệp vụ) lọt vào field
`summary.error` — thứ LLM đọc thấy và **có thể lặp lại nguyên văn cho người dùng cuối** trong khung
chat. Tái hiện với `get_undelivered_volume(as_of="banana")`,
`get_contract_deliveries(date_from="2026-13-40")` — cả 3 đều lộ y hệt.

**Kịch bản hỏng cụ thể**: người dùng gõ tự nhiên kiểu "từ Tết tới giờ" / "quý vừa rồi", LLM tính sai
định dạng ISO (vd thiếu số 0, hoặc kiểu `2026-13-01`) → thay vì một câu báo lỗi gọn, khung chat tư
vấn giá sàn nhận nguyên trang SQL nội bộ. Không sai SỐ (an toàn ở khía cạnh quyết định giá sàn — lỗi
được `run_tool()` bắt, không sập lượt hỏi) nhưng vi phạm rõ nguyên tắc bảo mật "không lộ chi tiết lỗi
nội bộ" và làm phình token mỗi lượt (chuỗi lỗi ~3.000 ký tự nạp lại vào ngữ cảnh LLM).

**Đối chiếu chuẩn đã có trong CHÍNH bộ này**: `floor_tools.py:90-93` và `:119-123` đã bọc
`try/except Exception` quanh lời gọi service rồi trả `err(f"Không tính được gợi ý: {exc}")` —
`market_tools.py:47-50` bọc `date.fromisoformat` trong try/except riêng. `contract_tools.py` là
module DUY NHẤT trong gói không theo mẫu này — thiếu sót, không phải khác biệt thiết kế có chủ đích.

**Cách sửa**: thêm 1 hàm dùng chung ở `_common.py` (vd `safe_date(s, default) -> str | None`, trả
`None` khi hỏng) rồi ở đầu mỗi hàm: `if date_from and not safe_date(date_from): return
err(f"Ngày '{date_from}' không đúng định dạng YYYY-MM-DD.")`. Rẻ, không đụng service gốc.

## 🟡 NÊN SỬA

### 2. Doanh thu "thiếu tỷ giá" xử lý KHÔNG NHẤT QUÁN giữa 2 tool trong CÙNG gói

**File**: `contract_tools.py:116-117` (`_contract_deliveries`) vs `:174-192` (`_contract_summary`,
tái dùng `_totals()` ở `sales_contract_report.py:520-533`).
- `get_contract_deliveries`: **1 đơn vị** thiếu tỷ giá → `total_revenue = None` cho TOÀN BỘ Tập đoàn
  (all-or-nothing, đã verify: `missing = [...]; total_revenue = None if missing else sum(...)`).
- `get_contract_summary`: cộng PHẦN BIẾT ĐƯỢC, nêu số hợp đồng thiếu trong `ghi_chu` (partial-sum +
  note) — do tái dùng đúng `_totals()` của màn hình gốc (hành vi màn hình cố ý, xem comment dòng
  520-526 của `sales_contract_report.py`).

Không phải bug (mỗi bên đều CÓ LÝ: một bên bọc đúng màn hình cũ để "không lệch số với UI", một bên
là phép cộng MỚI viết riêng cho tool nên chọn an toàn tối đa) — nhưng người hỏi so 2 câu trả lời từ
2 tool khác nhau trong CÙNG một phiên chat sẽ thấy một câu "doanh thu = None (không biết)" và một
câu "doanh thu = X, kèm ghi chú thiếu Y hợp đồng" cho cùng khái niệm "thiếu tỷ giá". Nên thống nhất
1 quy tắc cho cả gói, hoặc chí ít nói rõ trong system prompt rằng 2 tool có quy ước khác nhau.

### 3. `get_contract_summary(group_by=company)`: cờ "thiếu tỷ giá" chỉ báo Ở MỨC TOÀN TẬP ĐOÀN, không theo từng đơn vị

**File**: `contract_tools.py:199-227`. Vòng lặp gom `revenue_missing` mỗi đơn vị (`a["revenue_missing"]
+= 1`, dòng 207-208) nhưng khi xuất bảng (`rows_out`, dòng 213-215) KHÔNG đưa cờ này vào từng dòng —
chỉ cộng dồn thành 1 số `total_missing` duy nhất ở `ghi_chu` chung cho cả bảng (dòng 225-227).

**Kịch bản hỏng cụ thể**: hỏi "đơn vị nào doanh thu cao nhất kỳ này?", bảng trả về Đơn vị A đứng đầu
với doanh thu X — nhưng nếu chính A là đơn vị có hợp đồng thiếu tỷ giá (trong số các đơn vị bị đếm
vào `total_missing`), con số X của A thực chất là THIẾU, không phải đầy đủ như của các đơn vị khác
trong cùng bảng — người đọc/LLM không có cách nào biết THIẾU Ở ĐÂU chỉ từ bảng, phải tự suy diễn từ
1 câu ghi chú chung. Rủi ro: so sánh nhầm giữa các đơn vị (đơn vị B đứng thứ 2 trong bảng nhưng thực
ra doanh thu thật cao hơn A nếu A được cộng đủ).

**Cách sửa**: thêm field `thieu_ty_gia: int` (số HĐ thiếu) vào mỗi dòng `rows_out`, hoặc tối thiểu
liệt kê TÊN đơn vị có hợp đồng thiếu trong `ghi_chu` thay vì chỉ đếm tổng.

### 4. Không có test tự động cho đúng phần rủi ro cao nhất (đếm-trùng, sáp nhập, missing-revenue)

**File**: `tests/test_assistant.py` (126 dòng) — chỉ test structural smoke (tool chạy không sập +
trả `dict`) và phân quyền cap `sales_contract`. KHÔNG có test nào cho: số liệu đúng/sai, merge sáp
nhập đúng công ty, doanh thu None khi thiếu tỷ giá, hay ROWS_CAP. Report kiểm thử trước
(`test-contract-pack.md`) test bằng tay qua chat — không lặp lại được tự động, và **không hề test
input lỗi** (đúng chỗ để lọt phát hiện 🔴 #1). Đề xuất thêm ≥3 test tự động: (a) tổng
`get_undelivered_volume` khớp `undelivered_on()` gọi trực tiếp trên 1 tập dữ liệu cố định, (b) đơn vị
đã sáp nhập không xuất hiện riêng trong `group_by=company`, (c) ngày sai định dạng trả `err()` gọn,
không ném exception thô.

## 🟢 GÓP Ý (không chặn)

### 5. `get_master_contracts`: vòng lặp N+1 gọi `parents_with_progress` mỗi hồ sơ mẹ

**File**: `contract_tools.py:306-317`. Với `limit` tối đa 30, chạy tối đa 30 lượt gọi DB riêng (mỗi
lượt vài CTE). Hiện tại DB chỉ có 3 hồ sơ mẹ nên đo được 0,128s cho `limit=30` — không đáng lo NGAY,
nhưng đây là hồ sơ dài hạn (HĐNT/HĐDH) nên số lượng tăng chậm theo thời gian, rủi ro thấp về lâu dài.
Không cần sửa gấp; nếu sau này hồ sơ mẹ lên tới hàng trăm, cân nhắc mở rộng `parents_with_progress`
để trả tiến độ TÁCH theo từng `master_id` trong 1 lượt gọi thay vì lặp.

### 6. `avg_price_trieu` coi doanh thu = 0 (đúng, không phải thiếu) giống như "chưa biết"

**File**: `contract_tools.py:118-119`: `if total_revenue and total_qty else None` — `0` là falsy
trong Python nên nếu tổng doanh thu tính ra đúng bằng 0 (hợp lệ, không phải `None`), đơn giá bình
quân bị báo `None` thay vì `0`. Biên rất hẹp (cần tổng doanh thu = 0 với sản lượng > 0, gần như không
xảy ra thực tế vì đơn giá luôn > 0 khi đã có tỷ giá) — chỉ nêu để nhất quán, sửa thành so `is not
None` nếu muốn triệt để.

### 7. File 378 dòng — vượt chuẩn "<200 dòng" của AGENTS.md, nhưng khớp thực tế các file cùng lớp

`master_contract_repo.py` 205 dòng, `member_unit_merge.py` 341 dòng, `sales_contract_report.py`
533 dòng — chuẩn <200 dòng không được áp cho tầng service/tool trong thực tế của repo này. Không đề
xuất tách vì 5 hàm đã tách rõ theo từng tool + docstring giải thích VÌ SAO ở đầu file; tách thêm chỉ
tăng số file phải đọc để hiểu 1 luồng.

## Đã KIỂM và XÁC NHẬN ĐÚNG (không phải suy đoán)

1. **Hợp đồng mẹ không vào sản lượng**: xác nhận ở TẦNG DỮ LIỆU — `master_contract` là bảng
   HOÀN TOÀN TÁCH BIỆT với `sales_contract` (`master_contract_repo.py`), không phải quy ước ở tầng
   đọc. Không có đường nào để hồ sơ mẹ lọt vào bất kỳ tổng sản lượng nào.
2. **Đợt giao không đếm 2 lần cùng hợp đồng**: xác nhận ở TẦNG GHI —
   `sales_contract_clean.py:140-141` CHẶN CỨNG việc đánh dấu "đã giao" cho hợp đồng `delivery_type
   = multi` (raise ValueError), nên hàng trong `sales_contract` khớp `delivered AND delivered_at IS
   NOT NULL` chỉ có thể là hợp đồng giao-1-lần hoặc đợt giao con — không bao giờ là cha của đợt.
3. **Sáp nhập đơn vị**: test thật với cặp Bình Long→Lộc Ninh (88 hợp đồng gốc của Bình Long) —
   `get_contract_summary(group_by=company)` và `get_undelivered_volume(group_by=company)` đều gộp
   đúng vào dòng Lộc Ninh, số khớp chính xác với tổng độc lập tính bằng tay (20.518,253 tấn, n=159).
   Bình Long không xuất hiện dòng riêng.
4. **Đối chiếu số độc lập** (không dùng lại code của tool):
   - `tong_cam_ket_tan` (2025-07-27→2026-08-31): tool = 375.682,049 tấn; Python tính lại bằng
     `calc.total_qty` trên từng dòng = 375.682,049 tấn (n=3.181) — khớp tuyệt đối.
   - `doanh_thu_hop_dong_vnd` cùng kỳ: tool = 2,4803357134003132e+16 đ, 18 HĐ thiếu; Python tính
     lại bằng `calc.total_revenue_vnd` = 2,4803357134003132e+16 đ, 18 HĐ thiếu — khớp tuyệt đối.
5. **Trần 5.000 dòng có cảnh báo thật**: hạ `_ROWS_CAP` xuống 100 để ép chạm trần → tool trả đúng
   ghi chú "Chỉ lấy 100/3.181 hợp đồng khớp kỳ (đã đạt trần truy vấn) — số theo đơn vị có thể THIẾU"
   — không lặng lẽ trả số thiếu.
6. **Trần 400 ngày** (`clamp_from`) hoạt động: gửi `date_from` cách hơn 2 năm, tool tự kéo về đúng
   400 ngày trước `date_to` (2025-07-27), không báo lỗi, không tải hết lịch sử.
7. **Tên đơn vị mơ hồ**: `get_master_contracts(company="cao su")` báo đúng "khớp 56 đơn vị... gõ tên
   cụ thể hơn" — không tự chọn bừa 1 đơn vị.
8. **Phân quyền cap `sales_contract`**: test 4 kịch bản qua `run_tool()` thật — không cap (bị chặn
   dù gói bật), cap mức `view` (đủ, vì tool chỉ ĐỌC), admin tắt gói dù có cap (vẫn bị chặn) — đúng cả
   4.
9. **Không viết SQL mới, không SQL nối chuỗi**: xác nhận đọc toàn file — chỉ gọi hàm sẵn có của
   `sales_contract_report`/`master_contract_repo`/`unit_report_query`/`customer_repo`.
10. **Đơn vị tính luôn kèm nhãn**: mọi field số đều có nhãn tấn quy khô/VNĐ/triệu đồng-tấn rõ ràng
    trong `summary` lẫn mô tả schema gửi LLM.
11. **Không carry-forward**: `_undelivered_volume` là ẢNH CHỤP đúng `as_of`, có ghi chú rõ; phân biệt
    đúng với "còn phải giao tại HIỆN TẠI" của `_contract_summary` (2 khái niệm khác nhau, tool nói rõ
    cả 2 chỗ).

## Hiệu năng (đo thật trên DB local, ~2 năm dữ liệu, 3.197 hợp đồng gốc)

| Tool | Kịch bản | Thời gian |
|---|---|---|
| `get_contract_summary(group_by=company)` | ~2 năm | 0,209s |
| `get_contract_summary(group_by=total)` | ~2 năm | 0,056s |
| `get_contract_deliveries` (4 group_by) | 400 ngày (trần) | 0,116–0,201s |
| `get_top_customers` | 400 ngày | 0,125s |
| `get_master_contracts(limit=30)` | 3 hồ sơ hiện có | 0,128s |

Không có vấn đề hiệu năng THỰC ở quy mô dữ liệu hiện tại. Rủi ro trần 5.000 dòng là RỦI RO TƯƠNG LAI
(tăng ~1.600 hợp đồng gốc/năm, còn cách trần khoảng 1,5-2 năm nữa) — đã có cảnh báo đúng khi chạm, đủ
an toàn để deploy ngay, cần theo dõi lại sau 1-2 năm.

## Kết luận: NÊN DEPLOY, kèm điều kiện vá nhanh mục 🔴 #1

Số liệu tài chính (sản lượng, doanh thu, đã ký chưa giao) — thứ ảnh hưởng trực tiếp quyết định giá
sàn — đã kiểm chứng ĐÚNG bằng đối chiếu độc lập, không chỉ tin comment/docstring. Kiến trúc chống
đếm-trùng (2 cấp hợp đồng, sáp nhập đơn vị) vững ở TẦNG GHI DỮ LIỆU, không chỉ ở tầng tool. Phân
quyền đúng. Không có lỗi làm sai số hay sập phiên hỏi.

Lỗi duy nhất đủ nghiêm trọng để nêu ở mức 🔴 (#1 — lộ SQL thô khi ngày sai định dạng) KHÔNG làm sai
số quyết định giá sàn (an toàn về mặt nghiệp vụ) nhưng dễ tái hiện qua hỏi tự nhiên và vi phạm chuẩn
bảo mật đã có sẵn ngay trong cùng bộ tool (`floor_tools.py`). Khuyến nghị: vá bằng 1 hàm validate
ngày dùng chung ở `_common.py` (rẻ, không đụng service gốc) TRƯỚC khi bật gói `contract` cho người
dùng thật — có thể làm trong cùng đợt deploy, không cần lùi lịch.

## Câu hỏi còn treo

1. Quy tắc "thiếu tỷ giá ⇒ tổng None toàn bộ" (dùng ở `get_contract_deliveries`/`get_top_customers`)
   có nên áp luôn cho `get_contract_summary` để nhất quán cả gói, hay giữ nguyên tắc "bọc đúng màn
   hình gốc" như hiện tại? Cần chủ dự án/PO quyết, vì đây là lựa chọn nghiệp vụ chứ không phải bug.
2. Ngưỡng cảnh báo trần 5.000 hợp đồng — có cần hạ xuống sớm hơn (vd cảnh báo ở 80% = 4.000) để có
   thời gian xử lý trước khi thực sự chạm trần?
