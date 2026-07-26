# Kế hoạch — Dashboard + biểu mẫu lọc báo cáo theo dõi số liệu đơn vị nhập

**Trạng thái:** ✅ ĐÃ TRIỂN KHAI XONG local (26/07/2026) — 117 test API pass · `pnpm build` sạch · đã
kiểm thực tế trên dữ liệu thật. **Chưa deploy** (feature → gộp đợt sau).
Hậu-deploy: không cần cấp quyền mới (dùng lại cap `unit_daily` mức Xem).
**Phân tích chi tiết:** [phan-tich-du-lieu-va-gap.md](phan-tich-du-lieu-va-gap.md)

## Yêu cầu khách hàng (nguyên văn rút gọn)

| Phần | Bộ lọc | Chân bảng |
|---|---|---|
| 1. Thu mua | đơn vị · khoảng thời gian · **loại mủ thu mua** · khu vực | Tổng sản lượng + **đơn giá thu mua BQ** |
| 2. Tiêu thụ (tách khỏi tồn kho) | công ty · thời gian · khu vực · chủng loại · **loại HĐ** · **hình thức HĐ** | Tổng sản lượng + **giá bán BQ** |
| 3. Tồn kho (để riêng) | công ty · khu vực · thời gian · chủng loại | (tổng tồn theo mốc) |
| 3b. HĐ ký chưa giao | tab riêng | — |

## Phạm vi

- **Có**: 3 màn thống kê có bộ lọc + tab HĐ; dashboard KPI + tình trạng nộp; xuất Excel theo bộ lọc.
- **Không**: đổi biểu mẫu nhập liệu, đổi cấu trúc `unit_daily_report`, bỏ màn `/bao-cao-tong-hop` hiện có.

## Các phase

| # | Phase | Nội dung chính | Trạng thái |
|---|---|---|---|
| 1 | Backend truy vấn | `unit_report_rows.py` (làm phẳng) · `unit_report_query.py` (helper chung) · `unit_report_purchase.py` · `unit_report_consumption.py` · `unit_report_stock.py` | ✅ |
| 2 | API + test | `/api/unit-daily/analytics/{filters,purchase,consumption,stock,status}` + `.xlsx`; `tests/test_unit_analytics.py` (9 test) | ✅ |
| 3 | Web — bộ lọc dùng chung | `AnalyticsFilters.tsx` + `StatsTable.tsx` + `use-stats.ts` + `lib/unit-analytics-client.ts` + `lib/date-presets.ts` (DRY với Báo cáo tổng hợp) | ✅ |
| 4 | Web — 3 màn + tab HĐ | `/thong-ke/thu-mua` · `/thong-ke/tieu-thu` · `/thong-ke/ton-kho`; Thống kê hợp đồng thêm lọc khu vực + chủng loại + cột Khu vực | ✅ |
| 5 | Dashboard | `/thong-ke/tinh-trang-nop` — KPI + ma trận đơn vị × ngày | ✅ |
| 6 | Hoàn thiện | Xuất Excel theo bộ lọc (kèm cột Khu vực), nhóm menu "Thống kê số liệu", changelog | ✅ |

## Quyết định thiết kế đã chốt (26/07/2026)

1. **Loại mủ thu mua** = 3 nhóm: mủ nước · mủ chén · thành phẩm. Chọn "Thành phẩm" mở thêm bộ lọc **chủng loại** (dùng `UNIT_STOCK_GRADES`).
2. **Đơn giá thu mua BQ** = **3 chỉ tiêu tách riêng**, không quy đổi chéo:
   BQ mủ nước (đ/độ TSC) · BQ mủ chén (đ/độ, ghi rõ TSC/DRC) · BQ thành phẩm (triệu đ/tấn).
   Lọc 1 nhóm → chân bảng chỉ hiện chỉ tiêu tương ứng. Tất cả BQ đều **gia quyền theo sản lượng**.
3. **Tồn kho** = tồn tại **một mốc**: chọn khoảng ngày → lấy ngày cuối kỳ **có số liệu của từng đơn vị**, hiển thị cột "Ngày lấy số" cho từng dòng (không cộng dồn, không mượn số ngày khác).
4. **Tiêu thụ** có bộ lọc + cột **Nguồn mủ** (mủ thu mua `sales` / mủ khai thác `sales_own`), mặc định hiện cả hai.
5. **Dashboard** ưu tiên **ma trận tình trạng nộp báo cáo** (đơn vị × ngày: đã nhập / chưa nhập / không tổ chức thu mua), KPI tổng đặt phía trên. → Phase 5 làm trước Phase 4 nếu cần bàn giao sớm.

## Rủi ro

- Trộn TSC/DRC khi tính BQ mủ chén (B2) và dòng USD thiếu tỷ giá (B3) → số BQ sai âm thầm; bắt buộc hiển thị cảnh báo, không tự đoán số.
- Đơn vị Lào/Campuchia dùng giá nội tệ (B4) — báo cáo kỳ hiện tại đang bỏ sót, cần xử lý luôn ở đây.
- Tuân thủ nguyên tắc **không thay dữ liệu ngày này bằng ngày khác**: tồn kho lấy đúng ngày có số liệu và **ghi rõ ngày đó** trên bảng.

## Bổ sung 26/07/2026 (đợt 2 — theo yêu cầu "dashboard có tương tác lớp")

Drill-down cho cả 3 chỉ tiêu, bấm dòng/cột để đi sâu, đường dẫn để quay lại:

| Màn | Chuỗi lớp |
|---|---|
| Thu mua | Toàn Tập đoàn → Khu vực → Công ty → Ngày → Loại mủ |
| Tiêu thụ | Toàn Tập đoàn → Khu vực → Công ty → Ngày → **Từng dòng bán** (số HĐ · xuất kho · hoá đơn) |
| Tồn kho | Toàn Tập đoàn → Khu vực → Công ty → Ngày → Chủng loại |

- Mỗi lớp có KPI tổng + biểu đồ cột (12 nhóm lớn nhất) — bấm cột tương đương bấm dòng.
- Bộ lọc (kỳ · đơn vị · khu vực · chủng loại · loại HĐ · hình thức · nguồn mủ) áp CHỒNG lên nhánh
  đang mở; đổi bộ lọc thì drill quay về lớp ngoài cùng.
- Ô "Nhóm theo" vẫn còn để xem nhanh theo chiều khác (loại HĐ · hình thức · nguồn mủ · chủng loại);
  các chiều ngoài chuỗi thì không bấm sâu tiếp được.
- Tồn kho: thêm `group_by=day` ở backend — mỗi ngày là một ảnh chụp riêng, dòng Tổng cộng lấy ngày
  cuối kèm cảnh báo, tuyệt đối không cộng dồn số thời điểm.
- Ảnh minh hoạ: `visuals/08…12-drill-*.png`.
