# Tách nhóm HĐ nguyên tắc (HĐNT) khỏi chuyến / dài hạn — 01/10/2026

Phản ánh: Dashboard đơn vị Dầu Tiếng Việt Lào hiện "Dài hạn 420 · chuyến 5.794" trong khi đơn vị
không có HĐDH nào — 10 đơn hàng ĐHT đều thuộc 3 HĐNT với Camel nhưng 7 cái lưu "HĐ chuyến" (gắn HĐNT
bằng nút "Gắn hợp đồng có sẵn"), 3 cái lưu "Phụ lục". Đơn vị xác nhận: cả 10 phải ghi nhận là HĐNT.

## Chốt của chủ dự án (01/10/2026)
1. Xếp nhóm theo HỒ SƠ MẸ: gắn HĐNT → **HĐ nguyên tắc**; gắn HĐDH → **HĐ dài hạn**; không gắn hồ sơ →
   theo loại tự khai (chuyến · phụ lục cũ chưa gắn hồ sơ = dài hạn · trống = chưa khai).
2. Màn hình tách 3 nhóm. **Biểu Excel mẫu Ban TTKD** (Báo cáo kỳ, Biểu tổng hợp) giữ 2 cột: HĐNT
   **gộp vào cột HĐ chuyến**.
3. KH "Tiêu thụ HĐ chuyến" so với **HĐ chuyến thật** (không gồm HĐNT) — DTVL 4.413,6 / 7.200 = 61,3%.
4. Sửa ở MỌI màn đang tách chuyến/dài hạn. Kỳ đã chốt số liệu giữ ảnh chụp cũ.
5. 76 HĐ chuyến đang gắn hồ sơ mẹ → đổi loại sang "Phụ lục hợp đồng mẹ" (SQL một lần lúc deploy);
   nút "Gắn hợp đồng có sẵn" từ nay tự đổi loại sang Phụ lục.

## Hợp đồng API (khoá nhóm: `spot` · `principle` · `long_term` · `""`)
- Thống kê tiêu thụ / Dashboard consumption / Chỉ số đơn vị: thêm `qty_principle` (tấn, null khi 0).
  `qty_spot` = HĐ chuyến không gắn hồ sơ; `qty_long_term` = gắn HĐDH + phụ lục chưa gắn hồ sơ.
  Meta `contracts` thêm `{value:"principle", label:"HĐ nguyên tắc"}`; dòng chi tiết `contract` có thể = `principle`.
- Báo cáo kỳ (`period_report` rows, PeriodReportPage, bảng chốt số liệu): thêm `principle_export`,
  `principle_domestic`, `principle_total`; `lt_*`/`spot_*` KHÔNG còn gồm HĐNT. `pct_plan_sales_spot`
  = `spot_total` / KH. Excel mẫu Ban TTKD: cột chuyến = spot + principle.
- Còn phải giao (`/api/sales-contracts/consumption` → `backlog[company]`, outlook `backlog` + `breakdown[]`):
  thêm `principle_undelivered` (HĐNT đã ký chưa giao).
  `to_deliver = spot_undelivered + principle_undelivered + lt_remaining + unknown_undelivered`.

## Phân việc (file không giao nhau)
| Nhánh | File | Trạng thái |
|---|---|---|
| API (agent chính) | `apps/api/app/**`, `apps/api/tests/**` | ✅ |
| Web (agent web) | `apps/web/src/**` | ✅ |
| SQL một lần | `plans/261001-hdnt-nhom-rieng/sql/` | ✅ soạn — chạy SAU deploy |

## Sau review (`plans/reports/261001-hdnt-code-review.md`)
- GỠ hồ sơ → loại về "chưa khai" (không lặng lẽ thành dài hạn); loại cũ ghi nhật ký hoạt động.
- Đổi NHÓM báo cáo (gắn/gỡ hồ sơ · đổi loại · đổi HĐNT↔HĐDH) của hợp đồng có lần giao trong kỳ đã
  chốt → chặn tài khoản đơn vị (`sales_contract_group.assert_regroup_fences`), quản trị không chặn.
- Bảng khu vực của thẻ Tiến độ có cột "HĐ dài hạn còn phải giao" → các cột cộng ra "Còn phải giao".
- Cột "Nhóm HĐ" ở lịch sử đợt giao + 2 sheet chi tiết Excel Báo cáo tiêu thụ.

## Kiểm chứng
- pytest DB sạch: toàn bộ xanh. Bản sao prod (bảng hợp đồng làm mới 01/10): DTVL chuyến 4.413,6 ·
  HĐNT 1.800,5 · dài hạn 0; KH chuyến 61,3%; HĐNT chưa giao 210; Toàn TĐ 12.804 t sang HĐNT (24 đơn vị).
