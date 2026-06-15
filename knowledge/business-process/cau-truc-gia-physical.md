---
title: Cấu trúc file giá Physical (giao ngay) theo tháng
type: process
tags: [physical, gia-giao-ngay, reuters, rss3, str20, smr20, sir20, latex]
source: docs/bieu-mau/Tâm/Giá Physical/
updated: 2026-06-15
---

# Cấu trúc file Giá Physical (giao ngay) theo tháng

> File lưu **giá cao su giao ngay (physical) châu Á** thu thập **hàng ngày** từ Reuters
> ("Asian physical rubber prices"). Bổ trợ cho `data-sources/lay-gia-cac-san.md` — đây là
> mô tả **cấu trúc lưu trữ thực tế** của chuyên viên Tâm.

## Tổ chức thư mục & file
- Thư mục theo năm: `Giá Physical/Năm 2025/`, `Năm 2026/`.
- Mỗi tháng 1 file: `PHYSICAL-MM.YYYY.xlsx` (vd `PHYSICAL-05.2026.xlsx`).
- **Mỗi sheet = 1 ngày giao dịch**, tên sheet dạng `DD.M` (vd `04.5`, `29.5`, `28.11`).
  Một tháng có ~20 sheet (ngày làm việc).

## Cấu trúc 1 sheet (1 ngày)
Mỗi sheet là 1 bản snapshot Reuters, gồm:
- Tiêu đề `Asian physical rubber prices` + dòng `Published on MM/DD/YYYY`.
- Nguồn: **Reuters** · chỉ số tham chiếu `S&P GSCI Agriculture Index`.
- Bảng 2 cột: **Grade | Price(s)**.

### Các Grade (chủng loại) theo dõi
| Grade | Ý nghĩa | Đơn vị giá điển hình |
|---|---|---|
| **Thai RSS3** | Cao su tờ xông khói loại 3 (Thái) | baht/kg |
| **Thai STR20** | TSR20 Thái Lan | baht/kg |
| **Thai 60% Latex** | Latex 60% (bulk/Centrifuged) | baht/kg |
| **Malaysia SMR20** | SMR20 Malaysia | USD/kg ($x.xx/kg) |
| **Indonesia SIR20** | SIR20 Indonesia | USD/kg |

## Quy ước giá trị
- Giá kèm **tháng kỳ hạn** trong ngoặc: vd `Thai RSS3 (December)`, `Malaysia SMR20 (June)`.
- Đơn vị **không đồng nhất**: Thái yết **baht/kg**, Malaysia/Indonesia yết **USD/kg**
  (`$2.37/kg`) → cần quy đổi về cùng đơn vị (USD/tấn) khi dùng cho phân tích.
- Khi không có giá: ghi `NA`, `N/A`, `NON`, hoặc `(paywalled)` (SIR20 thường bị giới hạn).
- Định dạng và tiêu đề **thay đổi nhẹ theo thời gian** (vd 2025 có thêm dòng "Reporting by…",
  2026 rút gọn) → parser cần linh hoạt, dò theo nhãn Grade thay vì vị trí ô cố định.

## Lưu ý số hóa
- Đây là **giá giao ngay (spot)**, khác giá phái sinh (future) của các sàn → dùng cho bảng
  **3.2 Thị trường giao ngay** trong báo cáo phân tích thị trường tuần.
- Nguồn Reuters cần quy đổi tiền tệ (baht→USD) bằng tỷ giá USD/THB (xem `lay-gia-cac-san.md`).
- Khi tự động hóa: ingest theo (năm → tháng → ngày), chuẩn hóa đơn vị về USD/tấn, giữ
  trường "kỳ hạn" và cờ "không có giá" để không làm sai lệch thống kê.
