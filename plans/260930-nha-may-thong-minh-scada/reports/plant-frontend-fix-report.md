# Báo cáo sửa FRONTEND "Sơ đồ vận hành" sau review (mục 1–10)

Trạng thái: **xong** · `npx tsc --noEmit -p .` PASS · `pnpm build` PASS · không commit · không đụng `apps/api`.

## File (số dòng)
Gốc: `apps/web/src/features/command-center/pages/smart-factory/`

| File | Dòng | Ghi chú |
|---|---|---|
| `use-visible-poll.ts` (chuyển từ `plant/`) | 42 | dùng chung; `tick(alive)` báo kết quả về muộn |
| `use-factory-picker.ts` (mới) | 53 | hook chọn nhà máy dùng chung (mục 8) |
| `FactoryLiveKpis.tsx` | 55 | dùng `useVisiblePoll` (hết setInterval chồng lượt) |
| `FactoryMetersPage.tsx` | 127 | dùng `useFactoryPicker` (−36 dòng) |
| `ScadaFactoryFormModal.tsx` | 144 | Select sơ đồ nạp từ `/admin/layouts` |
| `scada-form-rules.ts` | 125 | bỏ `LAYOUT_OPTIONS` |
| `smart-factory-format.ts` | 134 | thêm `hms` |
| `plant/PlantDiagramPage.tsx` | 114 | số cũ/xám · `?khu=` · đổi nhà máy bỏ khu |
| `plant/PlantLiveStamp.tsx` (mới) | 27 | dòng giờ 5 trạng thái |
| `plant/PlantAreaDiagram.tsx` | 66 | co vừa card; `--pl-min-w` chỉ ≤ 768px |
| `plant/PlantDailyUsage.tsx` | 75 | ngày VN · lỗi theo nhà máy · `memo` |
| `plant/PlantPowerBar.tsx` | 29 | prop `dim` |
| `plant/use-plant-live.ts` | 53 | `fetchedAt` · 404 → ngừng + `onGone` |
| `plant/use-plant-setup.ts` | 43 | `usePlantFactories` = `useFactoryPicker` + lọc có sơ đồ |
| `plant/plant-format.ts` | 84 | bỏ `fmtNum`/`hms`/`Tone`; thêm `isStale` |
| `plant/PlantNode.tsx` · `PlantNodeTip.tsx` | 117 · 34 | class run/stop/empty; đèn "R" |
| `plant/plant-defs.tsx` (mới) | 46 | `<defs>` 1 lần/SVG: marker + 8 gradient |
| `plant/plant-icon-parts.tsx` (mới) | 70 | Spin · RoundMotor · Fins · Roll |
| `plant/plant-icons.tsx` | 126 | mixer · conveyor · screw · fan |
| `plant/plant-icons-machines.tsx` (mới) | 126 | crusher (máy băm đứng / máy cán) · tank · pump · motor |
| `plant/PlantDecor.tsx` | 80 | máng inox · ống thép 2 nét |
| `plant/plant.css` · `plant/plant-devices.css` (mới) | 64 · 74 | tách màu/chuyển động thiết bị |
| `apps/web/src/lib/smart-factory-client.ts` | 178 | `fetched_at` + `fetchPlantLayouts()` |

## Đã làm
1. Khung SVG co vừa card ở màn > 768px; ≤ 768px mới giữ bề rộng tối thiểu (CSS var) + cuộn trong khung. Kiểm 375px: `scrollWidth` trang = 375, không tràn ngang.
2. Mất kết nối hoặc số cũ (`fetched_at` − `at` mới nhất > 90 s, đọc cả 2 chuỗi như UTC nên không phụ thuộc múi máy người xem) → cả sơ đồ `grayscale(1)` + `opacity .6`, dừng chuyển động, thanh điện mờ. Góc khung: chấm xám + "Mất kết nối" / "Số cũ HH:mm:ss".
3. Đọc được mà mọi tag null → "Không có số" (chấm xám).
4. `/plant/live` 404 → ngừng hỏi (khoá theo khu) + tải lại danh sách nhà máy. Đã đo: 1 lượt 404 → 1 lượt `/factories` → 16 s không hỏi thêm.
5. `?khu=` lạ → thay bằng khu đầu (`replace`); đổi nhà máy → bỏ `khu`. Đã kiểm `?khu=khong-co` → `?khu=khu-mu-vao`.
6. PlantDailyUsage: lỗi gắn theo nhà máy; "hôm nay" = `toLocaleDateString("sv-SE", {timeZone: "Asia/Ho_Chi_Minh"})`; `memo`.
7. Form SCADA: Select = "(không)" + layout từ `/api/smart-factory/admin/layouts` (đã kiểm có "Nhà máy Phú Riềng"). Lỗi tải → chỉ còn "(không)".
8. DRY: plant dùng `fmtNum`/`hms` của `smart-factory-format.ts`. `useVisiblePoll` lên `smart-factory/`, FactoryLiveKpis dùng nó (lần đầu luôn đọc, tab ẩn thì dừng, không chồng lượt). **Có gom** hook chọn nhà máy (`useFactoryPicker(storeKey, only?)`): hành vi giữ nguyên (khoá nhớ riêng từng màn, giữ đang chọn → đã nhớ → đầu danh sách; 404 → tải lại). Đã kiểm lại màn Giám sát chỉ số: KPI vẫn cập nhật.
9. Màn < 576px: ẩn chữ "Cập nhật", chỉ còn giờ.
10. Vẽ lại theo RELCO: nền `#e9ebee`; máng inox gradient + mép sáng + sườn + chân; mixer = hộp motor vuông (vòng bu-lông, chân ∩) + chân vịt 4 cánh; băng tải = khung thép + con lăn + băng xanh có gân chạy + puly + chân thẳng đứng theo góc nghiêng; vít tải = ống + vệt xoắn chéo chạy; máy băm đứng (khung cao, vd CM1/CM2) = phễu trụ teal + cửa sổ rô-to quay + giá 4 chân; máy cán (CCS/C3T/CC) = thân teal, 2 trục cán vành xám quay, phễu thép, chân A, mô-tơ tròn; hồ QM = lòng inox + thanh khuấy răng chạy + mô-tơ trụ; bơm BC; quạt cánh cong quay; zone ô kem/cam; ống thép 2 nét; đèn "R". Chạy = `#22c55e`/viền `#15803d`, dừng = xám thép, không có số = nét đứt. Chuyển động tắt khi `prefers-reduced-motion` và khi sơ đồ xám. Gradient khai 1 lần trong `<defs>`.

Ảnh kiểm (dữ liệu giả TẠM: vá `window.fetch` trong tab, không để mock trong code): `reports/plant-frontend-fix-shots/` — 01 tổng thể chạy/dừng lẫn · 02 máy khuấy · 03 băng tải + máy băm + hồ + vít · 04 máy cán · 05 bơm · 06 hầm sấy · 07 số cũ (xám) · 08 mobile 375.

## Bỏ qua / lệch có chủ đích
- Băng tải: mô-tơ vẽ thành **tang dẫn động lớn liền đầu trên** thay vì mô-tơ treo trên giá như RELCO — treo ra ngoài đè nhãn/ô số của máy kế bên (CM1, CCS1, TL1).
- CM3 (khung 150×130, không "cao") vẽ kiểu máy cán, trong khi RELCO là máy băm đứng như CM1. Muốn đúng cần backend thêm trường kiểu dáng (vd `variant: "mill"`) — không đoán theo tên thiết bị.
- 404 mà danh sách tải lại VẪN còn nhà máy đó (hiếm): màn giữ "Mất kết nối" tới khi tải lại trang — đúng yêu cầu "dừng poll".
- Vít tải: vệt xoắn chạy bằng `stroke-dashoffset` (cùng cơ chế băng tải), không phải quay thật.

## Câu hỏi mở
- Có muốn bỏ hẳn đường nối nét đứt (`links`) cho giống RELCO không? Hiện để rất mờ.
