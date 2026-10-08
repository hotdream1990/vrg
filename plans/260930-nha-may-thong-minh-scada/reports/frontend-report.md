# Báo cáo nhánh B — Frontend Nhà máy thông minh (30/09/2026)

Trạng thái: **xong** · `cd apps/web && pnpm build` **PASS** (tsc + vite, không lỗi TS; cảnh báo chunk > 500 kB là có sẵn từ trước).
Chưa chạy với API thật (backend song song). Không commit.

## File
| File | Dòng | Ghi chú |
|---|---|---|
| `apps/web/src/lib/smart-factory-client.ts` | 152 | types + 8 hàm API theo contract, tải .xlsx kèm token |
| `pages/smart-factory/FactoryMetersPage.tsx` | 182 | trang chỉ số (state, tải, trạng thái rỗng/lỗi) |
| `pages/smart-factory/FactoryMeterToolbar.tsx` | 55 | nhà máy · RangePicker preset · Tải lại · Xuất Excel |
| `pages/smart-factory/FactoryMeterKpis.tsx` | 66 | thẻ mỗi chỉ số + thẻ Định mức/bành |
| `pages/smart-factory/FactoryMeterCharts.tsx` | 73 | cột theo ngày, hôm nay tô nhạt, null = trống |
| `pages/smart-factory/FactoryMeterTable.tsx` | 128 | nhóm cột đầu/cuối/tiêu thụ, icon cờ + Tooltip, dòng Tổng + TB/ngày |
| `pages/smart-factory/smart-factory-format.ts` | 111 | định dạng số/giờ, câu giải thích cờ, preset + kiểm kỳ ≤ 92 ngày |
| `pages/smart-factory/ScadaConfigPage.tsx` | 158 | bảng nhà máy, kiểm tra kết nối, sửa, xoá |
| `pages/smart-factory/ScadaFactoryFormModal.tsx` | 117 | form thêm/sửa, ghi chú đỏ `.form-note` |
| `pages/smart-factory/ScadaTestResultModal.tsx` | 60 | kết quả kiểm tra (success/error) |
| `pages/smart-factory/scada-form-rules.ts` | 74 | regex, mặc định, form → body |
| `pages/smart-factory/smart-factory.css` | 41 | class tiền tố `sf-` |
| `apps/web/src/lib/permissions.ts` | +4 | cap `smart_factory` (Cap, DATA_CAPS, EXECUTIVE_CAPS, CAP_GROUPS; không vào SPLIT_CAPS) |
| `apps/web/src/App.tsx` | +7 | `/nha-may-thong-minh/chi-so` (RequireCap) · `/nha-may-thong-minh/cau-hinh-scada` (RequireRole admin) |
| `features/command-center/sidebar-menu-builders.tsx` | +12 | nhóm `smart-factory` sau "Báo cáo & Thống kê" (menu thường + Lãnh đạo TĐ), DEFAULT_OPEN_KEYS |

Icon: nhóm `ClusterOutlined` · chỉ số `ThunderboltOutlined` · cấu hình `ApiOutlined`.

## Chỗ phải diễn giải contract
1. **Thời điểm** (`open_at`, `latest_at`, `fetched_at`, `updated_at`) coi là giờ nhà máy → hiển thị bằng cắt chuỗi, không qua `new Date()`. Giờ chỉ hiện khi khác `00:00` (chữ xám "lúc HH:mm" + Tooltip đủ ngày).
2. **Số bành**: cột/nhãn "Tiêu thụ" đổi thành **"Sản lượng"** (bành là đầu ra, không phải tiêu thụ). Điện/nước giữ "Tiêu thụ".
3. **Số lẻ**: chỉ số lũy kế điện/nước 3 số, tiêu thụ/tổng/TB 2 số, bành nguyên; kWh/bành 2 số, m³/bành 3 số.
4. **Định mức/bành**: thẻ + cột chỉ hiện khi nhà máy có `bales` VÀ có `energy`/`water`; dòng `intensity` null thì ẩn, cả hai null → "—".
5. **Tên file Excel**: đọc `Content-Disposition`; khác origin (dev) header này không được CORS expose → web tự đặt `chi-so-dien-nuoc-banh_<slug>_<from>_<to>.xlsx` (slug bỏ dấu). Prod cùng origin nên dùng đúng tên server. Lỗi tải (502…) hiện `detail`.
6. **Kỳ xem**: web chặn trước (không ngày tương lai, ≤ 92 ngày) → Alert cảnh báo, không gọi API. Server vẫn kiểm lại.
7. **API lỗi** (502/404…) → xoá số cũ, Alert error hiện `detail` + nút Thử lại (không giữ số của lần trước để khỏi đọc nhầm).
8. **Sửa cấu hình**: mật khẩu trống → gửi `password: null` (giữ cũ). `water_tag`/`bales_tag` rỗng → `null`. Tag điện kiểm 0/1/4 phần tử + regex; database/linked server kiểm `^[A-Za-z0-9_]{1,128}$`.
9. **Kiểm tra kết nối**: `ok=false` → Result error + `detail`; lỗi HTTP (403/404/mạng) → toast lỗi.
10. `metrics` rỗng (nhà máy chưa khai tag nào) → Alert info nhắc admin khai tag.

## Việc cho nhánh A / D
- Backend phải thêm `smart_factory` vào `app/core/permissions.py` (CAP list + EXECUTIVE_CAPS, không SPLIT) cho khớp web.
- Nếu muốn tên file Excel đúng cả khi dev khác origin: thêm `Content-Disposition` vào `expose_headers` (không bắt buộc).
- Nhánh D: chạy thử e2e với Historian giả lập để soát hiển thị cờ `partial`/`reset`/`in_progress`.
