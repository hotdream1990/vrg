# Checklist Dữ liệu Cần Thu thập

> Nguồn: Kế hoạch Triển khai + `scratchpad.md`. Phân định rõ **VRG cung cấp** vs **Bizino tự thu thập**.

## A. VRG cung cấp (nội bộ)
| # | Dữ liệu | Định dạng | Đầu mối | Ghi chú |
|---|---|---|---|---|
| 1 | Giá sàn / giá tham chiếu Tập đoàn — lịch sử **≥ 3 năm** | Excel/CSV | P. Kinh doanh | Mốc huấn luyện model |
| 2 | BCTM (tồn kho, sản lượng) theo loại mủ SVR10/CV/L/3L/20, RSS3, Latex | Excel | P. KH/SX | Đầu vào dự báo |
| 3 | Physical Price (giá giao dịch thực) | Excel/PDF | Chuyên viên TT (Tâm) | Đối chiếu thị trường |
| 4 | Biểu mẫu báo cáo thị trường hiện hành | Excel/Word | Chuyên viên | Chuẩn hóa đầu ra |
| 5 | Báo cáo mua bản quyền quốc tế / bản tin trả phí | PDF | — | Cho RAG |
| 6 | Email/PDF nội bộ phân tích thị trường | PDF/email | — | Cho RAG |
| 7 | Dữ liệu mùa vụ/khí tượng vùng trồng (cao điểm **T8–T12**, mưa) | Bảng/ghi chú | Chuyên viên | Yếu tố mùa vụ |
| 8 | Số liệu cá nhân chuyên viên đang theo dõi (file tay) | Excel | Triều/Phụng/Tâm/Hạnh | Số hóa kinh nghiệm |

## B. Bizino tự thu thập (không cần VRG)
- 4 sàn quốc tế: **TOCOM** (Nhật), **SICOM/SGX** (Singapore), **SHFE** (Thượng Hải), **AFET** (Thái Lan).
- Vĩ mô: giá dầu **WTI/Brent**, **USD/VNĐ**, **USD Index**, **PMI Trung Quốc**.
- Cách lấy giá chi tiết: [knowledge/data-sources/lay-gia-cac-san.md](../../knowledge/data-sources/lay-gia-cac-san.md).

## C. Tri thức nghiệp vụ cần số hóa
- Quy trình & kinh nghiệm chuyên viên (vd: chọn kỳ hạn có Trading Value lớn nhất khi lấy giá).
- Logic mùa vụ T8–T12, ảnh hưởng mưa tới sản lượng.
- Quy trình tổng hợp báo cáo tuần (input ~50 công ty thành viên → output toàn Tập đoàn).

> **Hành động ngay sau họp**: xác nhận đầu mối từng nhóm dữ liệu + ký NDA trước khi chuyển data thật.
