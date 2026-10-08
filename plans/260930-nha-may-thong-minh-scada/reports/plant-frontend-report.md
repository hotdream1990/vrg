# Báo cáo Frontend — Sơ đồ vận hành (mimic SCADA) · 30/09/2026

Trạng thái: **xong**. `npx tsc --noEmit -p .` **PASS** · `pnpm build` **PASS** (chỉ còn cảnh báo chunk > 500 kB, có từ trước).
Không commit. Không để mock trong code.

## File
| File | Dòng | Ghi chú |
|---|---|---|
| `apps/web/src/lib/smart-factory-client.ts` | 173 | type Plant* + `fetchPlantLayout` · `fetchPlantLive`; `FactoryBrief.layout_key?`, `ScadaFactory.layout_key` |
| `pages/smart-factory/plant/PlantDiagramPage.tsx` | 108 | trang: chọn nhà máy · Tabs khu (`?khu=`) · hàng trên · khung sơ đồ |
| `plant/use-plant-setup.ts` | 83 | danh sách nhà máy CÓ `layout_key` (nhớ localStorage `vrg.smart-factory.plant-factory-id`) + tải bố cục (404 → tải lại danh sách) |
| `plant/use-visible-poll.ts` | 40 | hook hỏi theo nhịp: lần đầu luôn đọc, tab ẩn dừng, hiện lại đọc ngay, không chồng lượt |
| `plant/use-plant-live.ts` | 47 | `/plant/live` mỗi 5 s; lỗi → giữ số mờ; 429 → im lặng |
| `plant/PlantPowerBar.tsx` | 27 | Volt/Current/Power từ `layout.power` |
| `plant/PlantDailyUsage.tsx` | 70 | Hôm qua/Hôm nay × Điện · Nước · Bành từ `/meters/daily`, 60 s |
| `plant/PlantAreaDiagram.tsx` | 59 | SVG: decor → links → thiết bị → nhãn/ô số; Tooltip |
| `plant/PlantNode.tsx` | 104 | biểu tượng xoay theo `angle` · ô zone/counter · khối nhãn + đèn + ô số |
| `plant/PlantNodeTip.tsx` | 34 | Tooltip: tag · giá trị · giờ đọc |
| `plant/PlantDecor.tsx` | 58 | basin · pipe · arrow_text |
| `plant/plant-icons.tsx` | 151 | 8 biểu tượng phẳng (mixer, conveyor, screw, crusher, tank, pump, fan, motor) |
| `plant/plant-format.ts` | 90 | định dạng, trạng thái chạy/dừng, màu, hình học khung |
| `plant/plant.css` | 69 | class `pl-` |
| `App.tsx` | +2 | route `/nha-may-thong-minh/so-do-van-hanh` trong RequireCap `smart_factory` |
| `sidebar-menu-builders.tsx` | +6 | "Sơ đồ vận hành" (DeploymentUnitOutlined) — menu thường + Lãnh đạo TĐ |
| `ScadaFactoryFormModal.tsx` · `scada-form-rules.ts` | +5 · +9 | ô chọn "Sơ đồ vận hành": (không) \| Phú Riềng → gửi `layout_key` (null khi không) |

## Diễn giải hợp đồng (backend cần khớp)
1. **Toạ độ node**: `(x, y)` = góc trên-trái khung `w × h`; `angle` (độ) xoay quanh TÂM khung, áp cho mọi `kind`. `links` nối tâm 2 node.
2. **Nhãn + ô số**: khối (nhãn · đèn · ô Hz/A) đặt ở cạnh `label_pos` (mặc định `top`) của khung bao SAU khi xoay; **nhiệt độ ở cạnh đối diện**. Khối rộng ≈ 105 đơn vị, mỗi ô số cao 20, cách dòng 23.
3. **zone**: ô số lớn lấy `temps[0]` (không có thì `metrics[0]`), nhãn nằm trong ô. **Không** tô cam ≥ 70 °C (buồng sấy luôn > 100 °C) — ngưỡng `HOT_TEMP_C = 70` chỉ áp cho nhiệt độ thiết bị (`temps` của máy cán/băm…).
4. **counter**: `metrics[0]`, số nguyên, đơn vị theo `unit` của metric.
5. **arrow_text**: `points` (≥ 2 điểm) = thân mũi tên, đầu mũi ở điểm cuối; không có `points` → mũi tên ngang từ `(x, y)` dài `w` (mặc định 40). Chữ nối tiếp sau đầu mũi theo hướng đoạn cuối. **basin** dùng x/y/w/h; **pipe** dùng `points`.
6. **Trạng thái**: status ≥ 0,5 = chạy (xanh VRG); < 0,5 = dừng (xám); không có tag trạng thái/chưa có số → thân xám, đèn rỗng nét đứt; mọi tag của node đều trống → viền nét đứt. `kind` lạ → vẽ như motor.
7. **Số lẻ**: ô thiết bị 2 số (vi-VN: `41,56`); thanh điện 1 số (như màn RELCO); tiêu thụ kWh/m³ 2 số, bành nguyên.
8. **Live**: đổi khu → thanh điện giữ số cũ (tag điện chung), sơ đồ Spin tới khi có số khu mới; lỗi gắn theo khu (đổi khu thì thôi báo lỗi cũ). `/meters/daily` bị 429 → hỏi lại sau 5 s.
9. **Co giãn**: SVG rộng 100% card, không thu nhỏ dưới 0,65 × `width` khu (chữ còn đọc được) → card hẹp thì cuộn ngang trong khung, trang không tràn.

## Đã kiểm tra
Chạy trên web dev (tab riêng, giả API bằng cách vá `window.fetch` trong trình duyệt — không đụng code): 4 khu, `?khu=` đổi theo tab, Tooltip trên SVG, đèn/viền nét đứt, nhiệt ≥ 70 tô cam, 502 → số mờ + "Mất kết nối", 429 im lặng, không nhà máy có sơ đồ → Alert + nút Cấu hình (admin), menu chọn đúng mục, ô chọn sơ đồ trong form admin.

## Việc cho backend / câu hỏi mở
- `/api/smart-factory/factories` phải trả `layout_key` (lúc test API đang chạy chưa có → trang báo "Chưa có sơ đồ vận hành"); admin PUT/POST nhận `layout_key`.
- Danh sách bố cục trong form admin đang cố định (`LAYOUT_OPTIONS` = phu_rieng) — thêm bố cục mới phải sửa cả web.
- Bảng cấu hình SCADA (`ScadaFactoryPanel.tsx`) chưa có cột "Sơ đồ" (ngoài phạm vi file được giao).
- Khu 1800 đơn vị trên màn laptop 1500 px có sidebar sẽ cuộn ngang ~10%; nếu chủ dự án muốn xem trọn khu cỡ lớn → cân nhắc nút Toàn màn hình.
- Xác nhận: zone không tô cam ≥ 70 °C (mục 3) có đúng ý chủ dự án?
