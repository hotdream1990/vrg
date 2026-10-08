# Sơ đồ vận hành v2 — Frontend (01/10/2026)

Trạng thái: **xong** · `npx tsc --noEmit -p .` PASS · `pnpm build` PASS · không commit.
Kiểm trên dev (web 5390 · API 8390, bố cục v2 THẬT của backend, factory 68) bằng Playwright + Chrome.

## Đã làm
- **Kiểu dữ liệu** (`lib/smart-factory-client.ts`): node `info_xy` `temps_xy` `temps_cols` `variant`; decor `badge`, `text_xy`; area `usage_box`, `hidden`.
- **Khối nhãn** (`PlantNode.tsx`): có `info_xy`/`temps_xy` → đặt đúng toạ độ (nhãn canh trái như RELCO); không có → giữ logic cũ. Ô số căn giữa, viền đậm. Băng tải và vít tải có thêm đèn "!" ở dòng A: xanh khi chạy, đỏ khi dừng.
- **Biểu tượng**:
  - `plant-icons-crushers.tsx` (mới): `mill` = tháp cán (phễu teal, rô-to cánh xoáy xanh, giá 4 chân); `creper` = máy 2 trục (thân teal, 2 trục lớn, tâm trục + mô-tơ đổi màu). Không khai `variant` thì giữ dáng cũ.
  - `plant-icons-machines.tsx`: bể QM vẽ lại (thành đứng, đáy vát có ống xả, lược khuấy ngang, mô-tơ giữa).
  - `plant-icons.tsx`:
    - MLM: cánh lớn, gối đỡ teal.
    - Băng tải nghiêng: mô-tơ tròn trên giá phía trên đầu băng.
    - VT: ống thép có sọc chéo xanh tươi.
- **Màu chạy = xanh neon RELCO** (#39F02A/#2EE62E, viền #0B8A0B). Thân tháp CM và máy CCS/C3T giữ màu teal. Dừng = xám thép.
- **Trang trí** (`PlantDecor.tsx`):
  - `badge` "pID".
  - `arrow_text`: ống nhỏ + đầu tam giác rỗng ở điểm cuối, xoay theo đoạn cuối (chỉ trái được).
  - `text_xy`: chữ đặt đúng điểm, neo trái.
- **Tiêu thụ trong ngày**: đã tách hook `use-plant-daily-usage.ts` (dùng chung, không nhân bản). Bảng trong SVG ở `PlantUsageBox.tsx`.
- **Trang**:
  - Hàng trên chỉ còn tiêu đề · nhà máy · giờ cập nhật.
  - Thanh tab luôn hiện (theo yêu cầu đổi), kể cả khi chỉ còn 1 khu.
  - Khu `hidden` bị lọc ở web.
  - Nền khung xám #d3d8d3.
  - Thanh điện đã chuyển xuống dưới sơ đồ, kiểu thanh đáy RELCO.
- **TẠM ẨN thanh điện + tiêu thụ**: dùng hằng `SHOW_POWER_AND_USAGE = false` trong `PlantDiagramPage.tsx`. Khi ẩn thì không gọi `/meters/daily` (đã đo: 0 lượt gọi). Đã thử bật tạm → hiện đúng, xem ảnh `bat-lai-dien-tieu-thu-1920`.

## Ảnh (plans/260930-nha-may-thong-minh-scada/visuals/v2-frontend/)
- `so-sanh-relco-vs-v2.jpg`: ảnh RELCO (trên) đặt cạnh web v2 (dưới) — trạng thái chạy/dừng và số đúng như ảnh RELCO.
- `v2-chay-1920.jpg` (giả lập đang chạy) · `v2-that-1920.jpg` (số thật lúc 06:2x, máy nghỉ) · `v2-chay-390.jpg` (điện thoại: cuộn ngang trong khung, trang không tràn).
- `zoom-cm1` · `zoom-qm1-vt1` · `zoom-creper` · `zoom-c3t1`: cắt cận từng cụm, trái = RELCO, phải = web.
- Script `shoot_v2.py`: sửa phản hồi `/plant/live` ngay trong Playwright (route). Không có mock trong code.

## Ghi chú cho backend (quy ước web đang hiểu)
- Khối nhãn `info_xy`: rộng ≈ 98 (đèn 15 + ô 58 + 3 + đơn vị 22), cao 17 + số dòng × 21. Ô nhiệt độ 58×18 + đơn vị 22; 2 cột cách nhau 6.
- `text_xy` = mép trái chữ, **giữa theo chiều dọc** (dominant-baseline central).
- `badge` (x, y) = góc trên-trái; cao 20, rộng ≈ 8 × số ký tự + 10.
- "Từ vít tải ngang": điểm cuối hiện ở phía BC1 nên đầu mũi tên nằm cạnh BC1. Muốn giống RELCO (đầu mũi ở sát chữ, chỉ trái) thì khai `points` `[[1145,793],[1602,793],[1586,793]]` và `text_xy` `[1610,793]`.
- Ống hồi lớn bên trái (vào BTCS1): RELCO có đầu mũi tên rỗng. Có thể khai `arrow_text` không có `text` thay cho `pipe`.
- `/plant/layout` vẫn trả 3 khu `hidden: true`. Web đã lọc, không lỗi.

## File sửa / tạo
Sửa:
- `apps/web/src/lib/smart-factory-client.ts`
- `plant/PlantDiagramPage.tsx`
- `plant/PlantAreaDiagram.tsx`
- `plant/PlantNode.tsx`
- `plant/PlantDecor.tsx`
- `plant/PlantDailyUsage.tsx`
- `plant/PlantPowerBar.tsx`
- `plant/plant-defs.tsx`
- `plant/plant-icon-parts.tsx`
- `plant/plant-icons.tsx`
- `plant/plant-icons-machines.tsx`
- `plant/plant.css`
- `plant/plant-devices.css`

Tạo:
- `plant/plant-icons-crushers.tsx`
- `plant/PlantUsageBox.tsx`
- `plant/use-plant-daily-usage.ts`

Mọi file < 200 dòng. Không sửa `apps/api`.
