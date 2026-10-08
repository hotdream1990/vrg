# Sơ đồ vận hành v2 — bám sát màn RELCO "KHU MỦ VÀO" (01/10/2026)

Chủ dự án: CHỈ hiện Khu mủ vào (ẩn 3 khu kia, giữ dữ liệu), vẽ GIỐNG ảnh gốc hơn.
Ảnh gốc: `plans/260930-nha-may-thong-minh-scada/visuals/relco-khu-mu-vao.webp` (2000×1113 px).
Khung sơ đồ RELCO trong ảnh ≈ x 110→1900, y 140→1000 ⇒ quy đổi sang viewBox 1800×900 của khu:
**X = x_ảnh − 110 · Y = (y_ảnh − 140) × 1.047** (gần như 1:1).

## Bổ sung vào schema bố cục (tương thích ngược — trường mới đều tuỳ chọn)
Khu (area):
- `hidden: true` → backend BỎ khu khỏi `/plant/layout`, `/plant/live?area=` khu ẩn → 404, `all_tags` không đọc tag khu ẩn.
- `usage_box: {x, y, w, h}` → web vẽ bảng **"THỐNG KÊ TIÊU THỤ TRONG NGÀY"** (cột Điện (kWh) · Nước (m3) · Bành mủ;
  dòng Hôm qua · Hôm nay) NGAY TRONG SVG tại hình chữ nhật đó (nền trắng viền đậm như RELCO, số xanh đậm).
  Có `usage_box` thì KHÔNG hiện ô tiêu thụ ở hàng trên nữa.

Thiết bị (node):
- `info_xy: [x, y]` → góc trên-trái khối nhãn (mã in đậm) + đèn "R" + ô Hz/A, toạ độ TUYỆT ĐỐI trong viewBox (không xoay).
  Có `info_xy` thì bỏ qua `label_pos` cho khối này. Khối kiểu RELCO: nhãn ở trên, mỗi dòng [đèn] [ô số] [đơn vị].
- `temps_xy: [x, y]` → góc trên-trái khối nhiệt độ (tuyệt đối). `temps_cols: 1 | 2` (mặc định 2 nếu 4 ô, còn lại 1).
- `variant: "mill" | "creper"` cho `crusher`: `mill` = tháp cán cao (CM1–CM3: phễu teal trên đỉnh, thân có rotor tròn
  xanh khi chạy, khung thép 4 chân xuống đất); `creper` = máy 2 trục (CCS1–2, C3T1). Không có → như cũ (theo tỉ lệ khung).
- `tank` (QM1, QM2) vẽ lại: BỂ DÀI PHẲNG thành xiên, chân đỡ, thanh khuấy NGANG kiểu lược dọc mép trên (xanh khi chạy),
  motor khối nhỏ giữa mép trên.

Trang trí (decor):
- `badge: {x, y, text}` → ô chữ nhỏ bo góc viền đậm (vd "pID" cạnh máy cán).
- `arrow_text` thêm `text_xy: [x, y]` (tuỳ chọn) → chữ đặt ĐÚNG điểm đó (neo trái). Đầu mũi tên LUÔN ở điểm cuối và
  xoay theo hướng đoạn cuối (được phép chỉ sang TRÁI như "Từ Vít Tải Ngang").

Trang:
- Chỉ còn 1 khu hiện → ẩn thanh tab.
- Thanh điện (Volt AB/BC/CA · Current A/B/C · Power) đặt DƯỚI sơ đồ, một hàng kiểu thanh đáy RELCO.
