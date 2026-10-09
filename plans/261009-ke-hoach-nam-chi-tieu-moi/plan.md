# Kế hoạch năm: bộ chỉ tiêu mới (7 nhóm · 25 chỉ tiêu)

Ngày lập: 09/10/2026 · Nhánh: `feature/master-contract` · Trạng thái: **Giai đoạn 1 đã deploy lên prod 0.4.117 (09/10/2026)**

> Tài liệu SỐNG: sau mỗi lần chốt thêm hoặc làm xong một bước, sửa ngay bảng Giai đoạn, mục
> "Nhật ký quyết định" và "Việc chờ trả lời" ở dưới. Người đọc sau chỉ cần file này để biết đang ở đâu.

## Bối cảnh
Ban Kế hoạch Tập đoàn gửi file `KH_UTH_2026_chuan_phan_mem_QLDT_V1_061026.xlsx` (tab 1, 72 công ty × 19 cột).
Mục tiêu của chủ dự án: **Ban nạp kế hoạch 2026 vào phần mềm → đơn vị vào xác nhận → làm mốc so sánh thực hiện**.
Màn "Kế hoạch năm" hiện chỉ có 8 ô; file có nhiều chỉ tiêu hơn nên phải mở rộng ô trước, rồi mới nạp/so sánh.

## Yêu cầu đã chốt (chủ dự án, 08–09/10/2026)
1. **Nhượng quyền bỏ khỏi chỉ tiêu**, số cộng vào khai thác (khai thác lấy cột E = F + G).
2. **Chế biến giữ 3 ô** (mủ khai thác · mủ thu mua · tổng): nhập để có mốc so sánh về sau.
3. **Hàng hóa tách riêng** khỏi thu mua ở Tiêu thụ và Doanh thu (phần mềm đã tách nguồn).
4. **Thêm nhóm Tồn kho thành phẩm**: khai thác · thu mua · hàng hóa + tổng.
5. **Mọi dòng tổng tự cộng**, đơn vị chỉ nhập các mục con.
6. Làm **màn hình nhập kế hoạch trước** (Giai đoạn 1); nạp từ file, xác nhận, so sánh làm sau.

## Giai đoạn
| # | Giai đoạn | File | Trạng thái |
|---|---|---|---|
| 0 | Bảng 23 chỉ tiêu + ánh xạ cột file (nguồn sự thật) | [phase-00](phase-00-bang-chi-tieu-final.md) | Xong (còn 4 câu chờ) |
| 1 | **Màn hình nhập kế hoạch năm** (DB · API · web · Excel mẫu) | [phase-01](phase-01-man-hinh-nhap-ke-hoach.md) | **Đã deploy 0.4.117** |
| 2 | Ban nạp kế hoạch từ file Excel | [phase-02](phase-02-nap-ke-hoach-tu-file.md) | Chưa làm |
| 3 | Đơn vị xác nhận kế hoạch | [phase-03](phase-03-xac-nhan-ke-hoach.md) | Chưa làm |
| 4 | So sánh thực hiện trên Dashboard (chỉ tiêu đã có số) | [phase-04](phase-04-so-sanh-thuc-hien.md) | Chưa làm |
| 5 | Bổ sung số thực hiện còn thiếu (khai thác · chế biến · tồn kho theo nguồn) | [phase-05](phase-05-bo-sung-so-thuc-hien.md) | Chưa làm |

## Tóm tắt thiết kế (chi tiết ở phase-00)
- **19 cột lưu** trong `unit_purchase_plan` (8 cũ + 11 mới); **6 tổng tính khi đọc** (thu mua, chế biến, tiêu thụ, tồn kho, HĐ dài hạn, HĐ chuyến).
- `plan_revenue_ty` GIỮ nguyên cột và tên để mọi nơi đang đọc (Dashboard, báo cáo kỳ, cảnh báo, trợ lý AI) không đổi;
  nhưng giá trị do **server cộng từ 3 mục con doanh thu** mỗi lần lưu.
- Ô mới đều tuỳ chọn, **chưa tính vào cảnh báo "thiếu kế hoạch"** cho tới khi Ban chốt (xem phase-01).

## Tài liệu liên quan
- Bảng đối chiếu cột (Excel, 3 tab): [`../reports/261007-doi-chieu-cot-ke-hoach-file-voi-phan-mem.xlsx`](../reports/261007-doi-chieu-cot-ke-hoach-file-voi-phan-mem.xlsx)
- Phân tích gốc (khớp 60/72 công ty, số đã nhập lệch file…): [`../reports/261007-phan-hoi-dat-ke-hoach-va-dashboard-doanh-thu.md`](../reports/261007-phan-hoi-dat-ke-hoach-va-dashboard-doanh-thu.md)
- Bộ nhớ dự án: `plan-2026-file-column-decisions`, `revenue-plan-year`.

## Việc chờ trả lời (cập nhật khi có đáp án)
| # | Câu hỏi | Ảnh hưởng | Mặc định tạm dùng |
|---|---|---|---|
| Q1 | KH doanh thu lấy cột S (26.936 tỷ) hay "DT bán hàng" dòng 57 (27.902 tỷ)? | Phase 2 | Cột S |
| Q2 | Ô "KH tiêu thụ HĐ chuyến": giữ song song với 4 ô tiêu thụ mới hay thay? | Phase 1, 4 | Giữ song song |
| Q3 | Tách hàng hóa: file không có số → ước tính hay nhờ Ban bổ sung? | Phase 2 | Ước tính (tiêu thụ: J; doanh thu: chia W theo tấn) |
| Q4 | KH tồn kho thành phẩm tính tại thời điểm nào, ai nhập? | Phase 1 (nhãn) | Cuối năm 31/12, đơn vị/Ban nhập |
| Q5 | Lộc Ninh: DT nhượng quyền 238,8 tỷ nhưng SL/tiêu thụ nhượng quyền = 0 — có đúng không? | Phase 2 | Cứ cộng vào khai thác như file |
| Q6 | 3 công ty chưa có đơn vị (Quanvan, CP Quasa Geruco (VN), CP Cao su Việt Lào (VN)): tạo không? | Phase 2 | Chưa tạo |
| Q7 | Đơn vị thấy KH sai: gửi đề nghị Ban duyệt hay tự sửa? % thực hiện tính trên mọi KH đã nạp hay chỉ đã xác nhận? | Phase 3 | Đề nghị Ban duyệt |
| Q8 | Ai được nhập 11 ô mới? Mặc định loại nhập liệu "Hợp đồng" như các ô còn lại, chỉ KH thu mua thuộc loại "Thu mua". Lưu ý có loại thứ ba "Tồn kho": 3 ô tồn kho thành phẩm có thể thuộc loại này, nhưng khi đó tài khoản chỉ có loại Tồn kho hiện không vào được màn Kế hoạch năm (màn chỉ mở cho loại Thu mua/Hợp đồng) | Phase 1 | Loại Hợp đồng cho cả 11 ô |

## Nhật ký thay đổi tài liệu
- 09/10/2026 (chiều): chủ dự án thêm 2 dòng tổng ở nhóm Hợp đồng — «Tổng HĐ dài hạn / HĐ chuyến thực hiện trong năm» = hợp đồng của năm + năm trước chuyển sang → 25 chỉ tiêu (chỉ web, đã deploy 0.4.117).
- 09/10/2026: lập kế hoạch từ các quyết định 07–09/10; làm xong Giai đoạn 1 (code + review + kiểm tay); luật doanh thu cuối ghi ở phase-01 mục 2.
