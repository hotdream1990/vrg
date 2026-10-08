# Sửa frontend sau review — Nhà máy thông minh (SCADA) · 30/09/2026

Trạng thái: **xong** · `pnpm build` (tsc + vite) **PASS** · không đụng `apps/api` · chưa commit · chưa kiểm trên trình duyệt.

## File đã sửa (số dòng)
| File | Dòng | Việc |
|---|---|---|
| `apps/web/src/lib/smart-factory-client.ts` | 116 | + `days_complete`, `server_time`, `warnings`; Excel dùng lại `downloadAuthed`; bỏ `errorDetail`/`fileNameOf`; regex slug viết `̀-ͯ` |
| `pages/smart-factory/FactoryMetersPage.tsx` | 169 | M1 · M2 · M6 · 429; icon tiêu đề → `ControlOutlined` |
| `pages/smart-factory/FactoryMeterAlerts.tsx` (**mới**) | 56 | Tách `NoFactory` · `NoTags` · `LoadErrorAlert` để trang chính < 200 dòng |
| `pages/smart-factory/FactoryMeterKpis.tsx` | 70 | TB/ngày theo `days_complete` + ghi chú; nhãn định mức |
| `pages/smart-factory/FactoryMeterTable.tsx` | 129 | Dòng "TB/ngày đủ số"; ghi chú dưới bảng; `upperFirst` dùng chung |
| `pages/smart-factory/FactoryMeterCharts.tsx` | 75 | `dm` của `lib/date.ts`; `upperFirst` dùng chung |
| `pages/smart-factory/FactoryMeterToolbar.tsx` | 56 | `disabledDate` chặn tương lai + kỳ > 92 ngày |
| `pages/smart-factory/smart-factory-format.ts` | 131 | + `errText`, `upperFirst`, `stampWithZone`, `disabledRangeDate`; bỏ `ddmm` (dùng `dm`/`dmy`) |
| `pages/smart-factory/scada-form-rules.ts` | 122 | 4 ô R0–R3, luật khai dở, trùng tag, mật khẩu khi đổi máy chủ |
| `pages/smart-factory/ScadaFactoryFormModal.tsx` | 119 | Thay Select tags bằng 4 ô cố định; luật mật khẩu |
| `pages/smart-factory/ScadaTestResultModal.tsx` | 70 | `server_time` + `warnings`; ok + cảnh báo → Result "warning" |
| `pages/smart-factory/ScadaConfigPage.tsx` | 163 | Chỉ đổi sang `errText` dùng chung (giữ cột "Tag Historian" + Thao tác `fixed: "right"`) |
| `pages/smart-factory/smart-factory.css` | +4 dòng | `.sf-kpi-hint`, `.sf-table-note`, `.sf-energy-grid`, `.sf-test-warn` |
| `features/command-center/sidebar-menu-builders.tsx` | 1 dòng + import | Mục chỉ số: `ThunderboltOutlined` → `ControlOutlined` (chưa dùng ở đâu trong menu) |

## Đối chiếu 12 mục
1. **M1**: `shown = null` khi `data.factory.id !== factoryId` (cả khi `noTags`/kỳ sai) → đổi nhà máy hiện Skeleton, không lộ số nhà máy cũ; đổi kỳ vẫn giữ số cũ mờ dưới Spin. Nút Excel cũng theo `shown`.
2. **M2**: `factory.metrics` rỗng → Alert info "Nhà máy chưa khai tag nào" (admin có nút "Cấu hình kết nối"), không gọi `/meters/daily`. Bỏ Alert chết cũ.
3. **M3**: 4 ô `Input` nhãn R0 (cao nhất, ×2⁴⁸) · R1 (×2³²) · R2 (×65.536) · R3 (thấp nhất, ×1). Hợp lệ: đủ 4 · chỉ R0 · trống cả 4; khác → lỗi ở ô trống "Điền đủ 4 ô R0–R3, hoặc chỉ ô R0 nếu tag đã là kWh". Ghi chú đỏ công thức giữ nguyên (`.form-note`). Gửi `energy_tags` = ô đã điền theo thứ tự R0→R3.
4. **H1**: sửa mà host/cổng/tài khoản khác bản gốc và mật khẩu trống → lỗi tại ô mật khẩu đúng câu của server. Thêm mới: mật khẩu vẫn bắt buộc.
5. **Trùng tag**: 6 ô tag (R0–R3, nước, số bành) so không phân biệt hoa thường → "Trùng tag với ô …"; các ô tag `dependencies` lẫn nhau nên sửa ô này thì ô kia kiểm lại.
6. **M6/429**: 404 → hiện lỗi + tải lại danh sách (nhà máy biến mất → tự chuyển nhà máy còn lại / hiện "Chưa có nhà máy"). 429 → Alert **warning** "SCADA của nhà máy đang bận đọc số liệu" + `detail` + Thử lại.
7. **KPI**: "TB/ngày (N ngày đủ số): …"; khi `days_complete < days_with_data` thêm dòng nhỏ "không tính hôm nay và ngày thiếu số"; `avg_per_day` null → "—". Định mức: "Chỉ tính ngày đủ số của cả hai chỉ số".
8. **Kiểm tra kết nối**: dòng "Giờ máy chủ SCADA" = cắt chuỗi, giữ múi → `15:39:12 30/09/2026 (UTC+07:00)`; mỗi `warnings[i]` một Alert warning; ok + có warnings → Result `warning` "Kết nối được — có điểm cần kiểm tra".
9. **RangePicker**: `disabledDate` chặn tương lai + (panel ngày, khi có `info.from`) chặn ngày cách ≥ 92 ngày. Gõ tay/preset cũng qua cùng hàm (rc-picker kiểm `isInvalidateDate`).
10. **Icon**: `ControlOutlined` (grep toàn `src`: chưa dùng ở đâu).
11. **DRY**: Excel → `downloadAuthed` (`lib/weekly-report-client.ts`); ngày dd/MM → `dm`, dd/MM/yyyy → `dmy` (`lib/date.ts`); `errText`/`upperFirst` gom vào `smart-factory-format.ts`.
12. Ghi chú dưới bảng: "Số hôm nay và hôm qua có thể còn thay đổi nhẹ khi SCADA đồng bộ muộn."

## Chỗ diễn giải
- **Thử lại / Tải lại** giờ tải lại CẢ danh sách nhà máy (rẻ) → admin vừa khai tag/tắt nhà máy thì màn tự cập nhật, xử lý luôn trường hợp danh sách cũ khiến server trả 400 "chưa khai tag".
- **Tên file Excel**: `downloadAuthed` không đọc `Content-Disposition` → web tự đặt `chi-so-dien-nuoc-banh_<slug>_<from>_<to>.xlsx` (slug khớp cách server đặt). Lỗi hiện câu `detail` của server.
- **Cờ `reset`**: đổi Tooltip thành "Chỉ số bị giảm trong ngày (đồng hồ bị đặt lại hoặc đọc lỗi) — không tính tiêu thụ" cho khớp luật mới của backend.
- Dòng Tổng dưới bảng đổi nhãn "TB/ngày" → "TB/ngày đủ số" (mỗi chỉ số có `days_complete` riêng nên không ghi N ở dòng này).
- Form thêm mới vẫn điền sẵn 4 tag điện + tag nước mặc định như trước (L9 không nằm trong danh sách sửa).
- Backend chưa trả `days_complete` thì KPI chỉ ghi "TB/ngày:" (không vỡ).

## Việc cho agent chính
- Kiểm trên trình duyệt: đổi nhà máy (Skeleton), nhà máy không tag, form 4 ô R0–R3 (khai dở / trùng / đổi host không mật khẩu), modal kiểm tra khi có `warnings`, lịch chặn > 92 ngày.
- Không có câu hỏi treo.
