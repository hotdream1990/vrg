---
title: "HĐ dài hạn theo HĐ mẹ · sản lượng còn phải giao · soát lỗi Dashboard đơn vị"
status: done
priority: P1
branch: feature/master-contract
created: 2026-09-26
---

# Phản hồi 26/09/2026 về Dashboard đơn vị

1. "Biểu đồ, số liệu và ghi chú lệch, không đúng logic" (khối Chỉ tiêu năm, Toàn Tập đoàn).
2. "HĐ dài hạn đã giao bao nhiêu trên số đã ký từ HĐ mẹ, còn lại bao nhiêu, tỷ lệ thực hiện — thêm vào
   dashboard và báo cáo tiêu thụ đơn vị; phần tổng 'đã ký chưa giao' chia ra: HĐ chuyến đã ký chưa giao
   + HĐ dài hạn còn lại phải giao = tổng phải giao đến cuối năm; so với KH bán hàng và doanh thu dự kiến
   so với KH doanh thu (theo khu vực, Tập đoàn; tách khai thác / thu mua)."

## Nguyên nhân mục 1 (đo trên prod 26/09/2026)
| # | Lỗi | Ảnh hưởng |
|---|---|---|
| D1 | Cao su Yên Bái — đợt giao id 11933 (HĐ 6807) nhập đơn giá **56.200** ở ô *triệu đ/tấn* (đồng/kg), sửa lúc 11:44 26/09 | +4.500 tỷ doanh thu → Tập đoàn 129,2%, Miền Núi phía Bắc 1.257%, giá BQ 64,78 (thật ≈ 53,9) |
| D2 | "Hà Tĩnh - Bolikhamxai" quốc gia LA nhưng khu vực = Campuchia | Số của đơn vị Lào nằm ở dòng Campuchia |
| D3 | KH doanh thu nghi sai: Tân Biên 86,8 tỷ (≈ chỉ phần HĐ chuyến) → 485%; C.R.C.K 228,5 tỷ nhưng thực 20,5 tỷ, còn C.R.C.K.2 bán 1.135 tỷ chưa có KH | % đơn vị/khu vực vô nghĩa |
| L1 | Dashboard không phát hiện đơn giá sai đơn vị tính (trang Cảnh báo bất thường có, dashboard không) | Số sai hiện như số thật |
| L2 | Thẻ KPI (cả phạm vi) và khối Chỉ tiêu (chỉ rổ đơn vị có KH) đặt cạnh nhau, nhãn không nói rõ rổ | 26.109 tỷ vs 12.687 tỷ, chuyến 268.909 vs 253.064 |

## Quyết định
| # | Nội dung |
|---|---|
| Q1 | ⚠ **Đổi 28/09/2026: CHỈ HĐDH** — HĐNT không tính, phụ lục của nó theo loại của chính phụ lục (phản ánh Cao su Tây Ninh: 3.427 t HĐNT hiện thành "HĐ dài hạn" dù đơn vị chỉ bán HĐ chuyến). Bản gốc: "HĐ dài hạn theo HĐ mẹ" = mọi hồ sơ `master_contract` (HĐDH + HĐNT) CÓ sản lượng cam kết, hiệu lực chồng lên năm của ngày tính. Cam kết = Σ dòng (quy khô nếu có, không thì SL). Đã giao = mọi lần giao (≤ ngày tính) của phụ lục + đợt giao thuộc hồ sơ, gốc quy khô như tiêu thụ. |
| Q2 | Còn phải giao của một HĐ mẹ = max(cam kết − đã giao, Σ phụ lục đã ký chưa giao); HĐ mẹ đã HẾT HẠN → 0, phần thiếu báo riêng `master_expired_short`. |
| Q3 | Không đếm trùng: hợp đồng thuộc HĐ mẹ có cam kết → tính ở cấp HĐ mẹ; còn lại tính theo khối 3 của chính nó, chia theo `contract_type` (spot · long_term · chưa khai). |
| Q4 | "Tổng phải giao" KHÁC "Đã ký HĐ chưa giao" (khối 3 của biểu Tồn kho): phần dài hạn theo cam kết HĐ mẹ, gồm cả sản lượng chưa ký phụ lục. Giữ nhãn khác nhau. |
| Q5 | Dòng bán có đơn giá quy đổi > trần `ANOMALY_SALE_PRICE_MAX` (mặc định 200 triệu đ/tấn) = nghi sai đơn vị tính → cảnh báo nêu tên đơn vị; % doanh thu để trống như khi thiếu tỷ giá. |

Hợp đồng API: [api-contract.md](api-contract.md).
