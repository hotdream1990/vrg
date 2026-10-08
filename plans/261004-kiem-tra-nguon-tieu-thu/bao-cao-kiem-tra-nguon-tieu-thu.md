# Kiểm tra chức năng Nguồn tiêu thụ (Khai thác / Thu mua) — 04/10/2026

**Bản kiểm:** 0.4.108 (đang chạy trên prod).
**Môi trường:** bản sao số liệu prod sáng 04/10, dựng thành DB riêng `vrg_prod_1004` trên máy dev. Bản sao đã tắt job, SMTP và Web Push để không gửi gì cho người dùng thật. Không ghi gì lên prod.
**Tài khoản thử:** đơn vị Cao su Dầu Tiếng (`drc.kd@…`) và tài khoản Ban (admin).
**Ảnh:** thư mục `visuals/`.
**Báo cáo rà code chi tiết:**
- `plans/reports/261004-consumption-source-correctness-audit.md`
- `plans/reports/261004-consumption-source-report-coverage.md`

## 1. Kết luận nhanh

- **Phần nhập liệu chạy đúng: 25/26 kịch bản đạt.**
  - Có ngày giao thì bắt buộc chọn nguồn. Giá trị lạ bị chặn.
  - Hợp đồng giao nhiều lần khai nguồn ở từng đợt giao. Hoàn thành hợp đồng cũng hỏi nguồn.
  - Đổi nguồn của lần giao đã quá hạn sửa thì phải gửi đề nghị sửa; Ban duyệt xong mới đổi.
  - Kịch bản không đạt là lỗi F2 ở mục 4.
- **Số trên báo cáo khớp nhau.** Đối chiếu 62 đơn vị từ đầu năm:
  - Khai thác + Thu mua = tổng tiêu thụ.
  - Tổng theo nguồn = tổng theo hình thức.
  - Lọc Khai thác cộng lọc Thu mua = không lọc.
- **3 vấn đề lớn cần anh quyết** (chi tiết ở mục 3 và 4):
  1. Dữ liệu cũ bị gán nhầm "Khai thác".
  2. Báo cáo tổng hợp — Biểu (2) Thu mua có 3 cột "tiêu thụ mủ thu mua" vẫn trống cả năm.
  3. Dashboard đơn vị chưa tách nguồn.

## 2. Những chỗ đã thay đổi theo 2 nguồn (đã kiểm)

| # | Màn | Thay đổi | Ảnh |
|---|---|---|---|
| 1 | Hợp đồng / đợt giao (form) | Ô **Nguồn tiêu thụ** cạnh Hình thức tiêu thụ, kèm lời dặn đỏ. Thiếu nguồn thì báo "Chọn nguồn tiêu thụ (khai thác hay thu mua)" | 01 |
| 2 | Chi tiết hợp đồng giao nhiều lần | Bảng đợt giao có cột **Nguồn**. Đợt chưa giao hiện "—" | 03 |
| 3 | Hoàn thành hợp đồng chưa có ngày giao | Hỏi **Nguồn tiêu thụ \***, thiếu thì chặn | 04 |
| 4 | Báo cáo tiêu thụ (web + Excel) | Thêm 2 cột **Nguồn khai thác · Nguồn thu mua**. Excel: thêm cột *Nguồn tiêu thụ* ở sheet theo hợp đồng và sheet chi tiết | 05 |
| 5 | Lịch sử đợt giao | Thêm cột **Nguồn** | 06 |
| 6 | Thống kê tiêu thụ (web + Excel) | Lọc theo nguồn, nhóm theo nguồn, 2 cột Nguồn KT / TM | 07 |
| 7 | Duyệt đề nghị sửa | Hiện dòng "Nguồn tiêu thụ: Khai thác → Thu mua". Duyệt xong số đổi và đợt chốt liên quan được gỡ | 08 |

## 3. Dữ liệu cũ bị gán "Khai thác" — quan trọng nhất

Lúc lên bản, mọi lần giao đã có ngày giao đều được gán **Khai thác**. Đo trên số liệu prod:

| Nhóm lần giao cũ | Số lần giao | Sản lượng (≈ tấn) | Đơn vị | Khôi phục được? |
|---|---:|---:|---:|---|
| Chuyển từ biểu tiêu thụ cũ, ghi rõ **"mủ thu mua"** | 394 | 22.500 | 20 | **Được**: nguồn còn ghi trong ghi chú bản ghi |
| Chuyển từ biểu cũ, ghi **"khai thác/thu mua"** (gộp) | 119 | 11.280 | 17 | Không tách được, đơn vị phải tự rà |
| Nhập thẳng trên hợp đồng 30/07 → 02/10 | 1.987 | — | 62 | Không có dấu vết, đơn vị phải tự rà |

**Hệ quả:** cột "Nguồn thu mua" lũy kế năm 2026 hiện gần như **bằng 0** trên mọi báo cáo (ảnh 07). Đề xuất:
1. Khôi phục **Thu mua** cho 394 lần giao bằng một lệnh SQL, sao lưu trước khi chạy.
2. Báo các đơn vị rà phần còn lại.

**Đường sửa cho đơn vị đã thử, chạy được:** Mở lại hợp đồng → Sửa đợt → Lưu → gửi đề nghị sửa → Ban duyệt. Phần lớn hợp đồng cũ đã "hoàn thành" nên đều phải mở lại trước khi sửa. Đường này khá dài nếu đơn vị phải sửa nhiều lần giao.

## 4. Báo cáo / lỗi cần làm tiếp

**Báo cáo chưa tách nguồn mà nên tách**

| Ưu tiên | Màn | Hiện trạng | Đề xuất |
|---|---|---|---|
| **CAO** | Báo cáo tổng hợp — Biểu (2) Thu mua (web + Excel) | 3 cột *SL tiêu thụ mủ thu mua · Doanh thu · Giá bán BQ* đọc ô nhập tay cũ. Ô này 0/6.225 phiếu năm 2026 có số, nên cột luôn "—" (ảnh 09) | Lấy từ các lần giao có nguồn **Thu mua**. Đây đúng là chỉ tiêu 6–8 trong mẫu của khách |
| **CAO** | Dashboard đơn vị — Tiến độ bán hàng năm | Chưa tách. Khách đã hỏi ngày 26/09 | Tách phần "đã giao" theo nguồn. Server đã trả sẵn số, chỉ cần hiện |
| TRUNG | Báo cáo tiêu thụ | Thẻ KPI, doanh thu và giá bán BQ chưa tách theo nguồn | Thêm doanh thu / giá BQ theo nguồn |
| TRUNG | Chỉ số đơn vị · bảng Số liệu chốt · Trợ lý AI | Chưa tách. Trợ lý chưa trả lời được câu "tiêu thụ mủ thu mua bao nhiêu" | Thêm sau |
| THẤP | Danh sách hợp đồng | Có lọc theo Hình thức nhưng chưa lọc / chưa có cột theo Nguồn | Thêm lọc theo Nguồn |

**Lỗi tìm thấy**

| Mức | Lỗi | Cách thấy |
|---|---|---|
| TRUNG | **Thống kê tiêu thụ, nhóm theo Nguồn / Hình thức / Loại HĐ:** bảng mất cột tên nhóm ("Khai thác", "Thu mua"), dòng Tổng cộng lệch 1 cột. Lỗi có từ trước với Hình thức / Loại HĐ, nay lộ thêm ở nhóm Nguồn | Ảnh 07, đã kiểm DOM |
| TRUNG | **F2:** HĐ giao 1 lần chưa giao (đã chọn hình thức / nguồn) chuyển sang giao nhiều lần → tự sinh "Đợt 1" chờ giao bằng 100% sản lượng → thêm đợt thật bị chặn vì vượt 110% | Đã tái hiện (100 t → thêm đợt 40 t bị chặn) |
| THẤP | **F3:** tạo HĐ giao 1 lần, điền ngày giao rồi đổi sang giao nhiều lần → form vẫn đòi nguồn ở ô đã ẩn | Theo rà code |
| THẤP | Lọc Thống kê tiêu thụ theo nguồn nhưng "% KH HĐ chuyến" vẫn chia cho cả chỉ tiêu năm, nên ra thấp | Theo rà code |
| THẤP | Đề nghị sửa gửi trước bản 0.4.108 bị coi là "số liệu đã đổi" khi duyệt | Prod hiện **0** đề nghị bị ảnh hưởng |

## 5. Ngoài phạm vi nhưng cần xử lý ngay

**Dầu Tiếng — HĐ 098/BPL-26-KC, đợt 3** (giao 02/10/2026, SVR 3L, 1,26 tấn): nhập đơn giá **63.417.000** thay vì **63,417** triệu đ/tấn.
- Doanh thu bị đội ~**79.900 tỷ** trên Báo cáo tiêu thụ, Thống kê và Dashboard.
- Màn Thống kê đã có cảnh báo, nhưng form hợp đồng chưa chặn.
- Đơn vị cần gửi đề nghị sửa, hoặc Ban sửa hộ.

## 6. Câu hỏi cần anh chốt

1. Có khôi phục nguồn **Thu mua** cho 394 lần giao cũ (≈22.500 t) không? Có yêu cầu đơn vị rà giai đoạn 30/07 → 02/10 không?
2. Hàng **mua ngoài về bán lại** (hàng hóa — Tân Biên ≈5.000 t/năm) xếp vào nguồn nào? Đề xuất thêm nguồn thứ 3 **"Hàng hóa"**. Nếu không, Biểu (2) sẽ lẫn số.
3. Có so tiêu thụ nguồn khai thác với **KH khai thác** (vốn là kế hoạch sản lượng vườn cây) không, hay chỉ hiện số?
4. Làm các mục **CAO** ở mục 4 + 2 lỗi TRUNG trong một bản phát hành không?
