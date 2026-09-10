# Báo cáo: Gói kỹ năng "Hợp đồng & khách hàng" cho Trợ lý AI

- File duy nhất sửa: `apps/api/app/services/assistant_tools/contract_tools.py` (378 dòng, mới hoàn
  toàn thay khung `TOOLS = {}`).
- Không sửa file nào khác. `__init__.py` đã đăng ký sẵn gói `contract` (cap `sales_contract`) từ
  trước — đúng như đề bài mô tả, không cần đụng vào.
- `ruff check` sạch. `pytest tests/test_assistant.py -q` → 4 passed.

## 5 công cụ

| Tool | Tham số | Nguồn số | Đơn vị |
|---|---|---|---|
| `get_undelivered_volume` | `as_of` (mặc định hôm nay), `group_by`: total/company/grade | `sales_contract_report.undelivered_on` + `unit_report_query.roll_by_company` | tấn quy khô |
| `get_contract_deliveries` | `date_from/date_to` (mặc định 30 ngày, lọc NGÀY GIAO), `group_by`: total/company/grade/customer | `sales_contract_report.consumption` + `roll_by_company` | tấn quy khô · VNĐ · triệu đồng/tấn |
| `get_contract_summary` | `date_from/date_to` (lọc NGÀY KÝ), `group_by`: total/company | `sales_contract_report.parents_with_progress` | tấn quy khô · VNĐ |
| `get_top_customers` | `date_from/date_to` (lọc NGÀY GIAO), `limit` (mặc định 10) | `sales_contract_report.deliveries` + `customer_repo.names_by_id` | tấn quy khô · VNĐ |
| `get_master_contracts` | `company` (tuỳ chọn, gõ tắt được), `limit` (mặc định 10) | `master_contract_repo.list_masters` + `parents_with_progress(master_ids=...)` | tấn quy khô |

KHÔNG viết SQL mới ở bất kỳ tool nào — toàn bộ số đọc qua 4 hàm public của
`sales_contract_report.py` (`undelivered_on`, `consumption`, `deliveries`, `parents_with_progress`)
và `master_contract_repo.list_masters`, đúng những hàm router `sales_contracts.py` đang dùng cho
màn hình thật.

## Output thật trên DB local (hôm nay 2026-09-10, dữ liệu clone prod)

```
get_undelivered_volume {} →
  tong_khoi_luong_chua_giao_tan=47872.002 tấn, so_hop_dong_con_hang=451, so_don_vi_con_hang=42

get_undelivered_volume {group_by: company} → top: Dầu Tiếng 4.690,56 · Bình Thuận 4.427,33 · ...
get_undelivered_volume {group_by: grade}   → top: SVR 10/CSR10 23.168,8 · SVR 3L 10.721,3 · ...

get_contract_deliveries {} (30 ngày, lọc NGÀY GIAO) →
  tong_san_luong_tan=14403.382, so_lan_giao=261, tong_doanh_thu_vnd=838274497300,
  don_gia_binh_quan_trieu_dong_tan=58.2

get_contract_summary {} (30 ngày, lọc NGÀY KÝ) →
  so_hop_dong=132, tong_cam_ket_tan=12327.999, da_giao_tan=862.224, con_phai_giao_tan=11465.775,
  doanh_thu_hop_dong_vnd=697673216865, ghi_chu: "1 hợp đồng thiếu đơn giá/tỷ giá — KHÔNG nằm
  trong doanh thu hợp đồng ở trên."

get_top_customers {limit:5} → HG EXPRO CO., LTD 525 tấn/28,54 tỷ; VRG JSC 420 tấn; ...

get_master_contracts {limit:3} → 3 hồ sơ demo (HĐNT/HĐDH), 0 phụ lục mỗi hồ sơ (dữ liệu test,
  chưa có hồ sơ mẹ nào gắn phụ lục thật trên bản clone prod hiện tại — trung thực báo 0, không bịa).
```
(output đầy đủ — mọi group_by, mọi tool — đã chạy sạch, không exception nào trên dữ liệu thật;
tổng hợp rút gọn ở trên cho gọn báo cáo)

## Đối chiếu số (bắt buộc theo yêu cầu)

Gọi thẳng service gốc, không qua tool, rồi so với output tool ở trên — **khớp tuyệt đối**:

```python
# 1) get_undelivered_volume (total) vs undelivered_on() trực tiếp
rolled = roll_by_company(undelivered_on('2026-09-10'))
→ total=47872.002, n_items=451, n_units=42        # ĐÚNG BẰNG output tool

# 2) get_contract_summary (total) vs parents_with_progress() trực tiếp
res = parents_with_progress(None, date_from='2026-08-12', date_to='2026-09-10', limit=1)
→ so_hop_dong=132
→ totals={'qty': 12327.999, 'delivered_qty': 862.224, 'pending_qty': 0.0,
          'remaining_qty': 11465.775, 'revenue': 697673216865.068,
          'delivered_revenue': 45560905828.716, 'revenue_missing': 1}
                                                   # ĐÚNG BẰNG output tool (làm tròn hiển thị)

# 3) get_contract_deliveries (total) vs consumption() trực tiếp
rolled2 = roll_by_company(consumption('2026-08-12','2026-09-10'))
→ qty=14403.382, deliveries=261, revenue=838274497300.0, missing=[]
                                                   # ĐÚNG BẰNG output tool
```

## Bẫy đếm-trùng đã xử lý thế nào

1. **2 cấp hợp đồng / đợt giao**: mọi tool gọi thẳng `deliveries()` / `consumption()` /
   `undelivered_on()` / `parents_with_progress()` — 4 hàm này đã tự đảm bảo mỗi lần giao chỉ được
   đếm đúng MỘT LẦN (đọc kỹ comment quanh `_fetch`, `_BLOCK3_SQL`, `remaining_qty` CASE-WHEN trong
   `sales_contract_report.py` trước khi viết). Không tool nào tự cộng `qty` của hợp đồng cha VỚI
   `qty` của các đợt giao con.
2. **Hợp đồng MẸ không vào sản lượng**: `get_master_contracts` CHỈ lấy `annexes`/`annex_qty` (đã
   tính sẵn trong `master_contract_repo`, chỉ đếm phụ lục `parent_id IS NULL` — không đếm đợt giao
   con của phụ lục) cho "đã ký"; và gọi `parents_with_progress(master_ids=[...])` (đọc từ
   `sales_contract`, KHÔNG đọc `master_contract`) cho "đã giao/còn lại". Trường "cam kết trên hồ
   sơ mẹ" CỐ Ý không đưa vào summary/bảng để tránh người đọc cộng nhầm nó vào sản lượng — ghi_chu
   nói thẳng "Hợp đồng MẸ chỉ là hồ sơ liên kết, TỰ NÓ KHÔNG có sản lượng".
3. **Doanh thu thiếu tỷ giá = KHÔNG BIẾT, không phải 0**: mọi tool giữ đúng quy ước None-khi-thiếu
   của `sales_contract_report`/`sales_contract_calc` và nói rõ số dòng/hợp đồng bị loại trong
   `ghi_chu`, không tự cộng phần còn lại rồi báo như đủ.
4. **Sáp nhập đơn vị**: `get_undelivered_volume`, `get_contract_deliveries`, `get_contract_summary`
   đều chạy qua `unit_report_query.roll_by_company()` trước khi nhóm/xếp hạng theo đơn vị — đơn vị
   đã sáp nhập cộng vào đơn vị hiện hành đúng quy ước dự án.
5. **Khách hàng chưa gán**: `get_top_customers` tách riêng sản lượng `customer_id` rỗng/0 thành
   `san_luong_chua_gan_khach_hang_tan`, KHÔNG gộp vào bảng xếp hạng khách hàng (tránh hiểu nhầm là
   một khách hàng thật).
6. **Không carry-forward**: `get_undelivered_volume` là ẢNH CHỤP đúng tại `as_of`, không lấy ngày
   khác đắp vào — và có `ghi_chu` nhắc rõ khác với "còn phải giao" (tính tại hiện tại) của
   `get_contract_summary`, để LLM không lẫn hai khái niệm.
7. **Ngày KÝ vs ngày GIAO**: đây là bẫy đọc-số dễ nhầm nhất giữa 5 tool (summary lọc theo ngày ký,
   deliveries/top_customers lọc theo ngày giao) — mỗi tool đều nói rõ trong `description` (schema)
   VÀ trong field `ghi_chu`/`loc_theo` của summary.

## Quyết định kỹ thuật đáng chú ý

- `get_contract_summary(group_by=company)` phải kéo tối đa `_ROWS_CAP=5000` hợp đồng về Python để
  cộng theo đơn vị (vì `parents_with_progress` chỉ tính TOTAL ở SQL, không có GROUP BY company sẵn
  có trong service). Nếu số hợp đồng khớp lọc > 5000 (khoảng ngày rất rộng), tool tự báo "đã đạt
  trần truy vấn" trong `ghi_chu` thay vì lặng lẽ thiếu — đã test với khoảng 13 tháng
  (2025-08-06→2026-09-10, 3179 hợp đồng) chạy tốt, chưa chạm trần.
- `get_undelivered_volume`/`get_contract_deliveries` KHÔNG kéo rows thô — dùng thẳng hàm đã tổng
  hợp sẵn theo đơn vị (`undelivered_on`, `consumption`), nên rẻ hơn nhiều so với #3.
- `get_master_contracts` gọi thêm 1 truy vấn `parents_with_progress(master_ids=[id])` cho MỖI hồ
  sơ mẹ trả về (bị giới hạn `limit` ≤ 30) — chấp nhận được vì đây là truy vấn nhẹ (limit=1) và số
  hồ sơ mẹ hiện tại còn rất ít (3 bản demo trên toàn hệ thống clone).
- `_resolve_company` (dùng cho `get_master_contracts.company`) tách riêng case "không tìm thấy" và
  "khớp nhiều đơn vị" (trả về danh sách ứng viên trong lỗi) — test thực tế phát hiện gõ "Bà Rịa"
  khớp CẢ "Công ty Cổ phần Cao Su Bà Rịa" LẪN "Công ty TNHH Phát triển Cao su Bà Rịa - Kampong
  Thom", ban đầu bị nuốt thành "không tìm thấy" (sai), đã sửa để báo rõ 2 ứng viên.

## Nghi ngờ còn lại / việc người khác cần làm

1. **Dữ liệu hợp đồng mẹ (`master_contract`) hiện gần như trống trên bản clone prod** (chỉ 3 bản
   ghi demo/thử nghiệm, 0 phụ lục gắn thật) — `get_master_contracts` đã test không lỗi nhưng CHƯA
   được xác nhận trên dữ liệu có phụ lục thật (annexes > 0, có đã giao/còn lại > 0). Khi tính năng
   hợp đồng mẹ được dùng thật trên prod, nên chạy lại tool này để soi trường hợp đó.
2. **`get_contract_summary(group_by=company)` có trần 5000 hợp đồng** — nếu về sau tổng số hợp
   đồng tăng nhiều và người dùng hay hỏi khoảng ngày rất rộng, có thể cần một hàm tổng hợp GROUP BY
   company ở SQL trong `sales_contract_report.py` (ngoài phạm vi file được phép sửa của phase này).
3. Chưa có tool riêng cho "hình thức tiêu thụ" (xuất khẩu/trong nước/nội bộ) hay "loại HĐ" (chuyến/
   phụ lục) dù `consumption()` đã có sẵn `by_channel`/`by_type` — bỏ qua theo YAGNI vì đề bài không
   yêu cầu, nhưng nếu cần mở rộng sau này có thể thêm `group_by=channel|type` vào
   `get_contract_deliveries` mà không phải viết SQL mới.
4. Test tự động: `tests/test_assistant.py` (4 test, không test riêng gói `contract`) vẫn pass —
   chưa có test unit riêng cho 5 tool này (nằm ngoài phạm vi 1-file được giao; nên bổ sung ở phase
   test riêng nếu dự án muốn coverage cho gói này).
