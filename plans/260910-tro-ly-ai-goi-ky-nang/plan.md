# Trợ lý AI — Gói kỹ năng & mở rộng truy vấn

**Mục tiêu:** Trợ lý AI truy vấn được **nhiều nhóm số liệu hơn** và **tư vấn điều chỉnh giá sàn
bằng suy luận liên kết** (thị trường ↔ nội bộ ↔ đơn vị thành viên), có **bật/tắt theo gói**.

**Chốt với chủ dự án 10/09/2026:** chỉ Tập đoàn dùng (không mở cho đơn vị) · ưu tiên gói
Đơn vị thành viên sau khi lấp đủ Thị trường/Giá sàn/Nội bộ · **CHỈ ĐỌC**, không hành động ghi.

Hiện trạng trước–sau + ranking yếu tố ảnh hưởng giá sàn:
[docs/project/tro-ly-ai-kha-nang.md](../../docs/project/tro-ly-ai-kha-nang.md)

## Kiến trúc

`app/services/assistant_tools.py` (1 file, 6 tool) → **package `assistant_tools/`**:

| File | Gói | Nội dung |
|---|---|---|
| `_common.py` | — | helper artifact + quy ước (No Trading · đơn vị tính · không carry-forward) |
| `__init__.py` | — | `PACKS`, registry, `openai_tools(caps, packs)`, `run_tool(name, args, caps, packs)` |
| `market_tools.py` | market | sàn quốc tế · diễn biến · **tỷ giá** · **physical** |
| `floor_tools.py` | floor | giá sàn hiện hành · **lịch sử ban hành** · gợi ý · **kịch bản** |
| `internal_tools.py` | internal | tồn kho · báo giá mủ · **giá mủ nguyên liệu** · **bản tin** · **độ tươi dữ liệu** |
| `unit_tools.py` | unit | **thu mua · tiêu thụ · tồn kho · kế hoạch năm · tình trạng nộp** (tổng/khu vực/đơn vị) |

**Ba tầng lọc tool** (giao nhau): gói admin bật (`ASSISTANT_PACKS` ở Cấu hình) ∩ quyền của tài
khoản (`PACKS[x].cap`, vd gói `unit` cần `unit_daily`) ∩ gói người dùng chọn trong phiên chat.
Gói `market` + `floor` là **gói nền**, luôn bật.

## Phase

| # | Nội dung | Trạng thái |
|---|---|---|
| 1 | Tài liệu hiện trạng TRƯỚC + ranking yếu tố (đo trên 80 lần ban hành) | ✅ |
| 2 | Tách package + cơ chế gói/quyền + config key + router `/packs` | ✅ |
| 3 | Gói `market` (4 tool) + `floor` (4 tool) | ✅ đã chạy thật trên DB |
| 4 | Gói `internal` (5 tool) | ✅ |
| 5 | Gói `unit` (5 tool) | ✅ |
| 6 | System prompt suy luận liên kết + nhúng ranking yếu tố | ✅ |
| 7 | Frontend: 2 công tắc (Nguồn tham chiếu · Mức tư vấn) + chip nâng cao | ✅ |
| 8 | `get_floor_context` — tín hiệu bối cảnh có hướng tác động tính sẵn | ✅ |
| 9 | Mức tư vấn `data`/`model`/`adjusted` (giới hạn AI) | ✅ |
| 10 | Nhật ký hỏi–đáp + trang Lịch sử + xoá log | ✅ |
| 11 | Test đa nhánh (3 mức · chống bịa số · phân quyền · nghiệp vụ) | ✅ |
| 12 | Review code + deploy | ⏳ |

## Ràng buộc bắt buộc (đã đưa vào `_common.py` và system prompt)

1. Không bịa số — mọi con số từ tool; tool báo thiếu thì nói thiếu.
2. **Không carry-forward**: không lấy số ngày khác đắp cho ngày được hỏi.
3. Giá 0 = *No Trading* (sàn) hoặc *không có giá* (thu mua) — không vào phép tính trung bình.
4. Luôn kèm **đơn vị tính**; LLM không được tự quy đổi.
5. Tổng hợp theo đơn vị phải qua service sẵn có (đã xử lý **sáp nhập đơn vị**, quy khô, loại tiền).

## Sau khi deploy

- Admin cấp cap `unit_daily` cho chuyên viên nào cần Trợ lý đọc số liệu đơn vị.
- Tuỳ chọn: đặt `ASSISTANT_PACKS` ở Cấu hình hệ thống nếu muốn tắt bớt nhóm dữ liệu.
