# Web — tách nhóm HĐ nguyên tắc (HĐNT) · 01/10/2026

Kết quả: `tsc --noEmit` sạch (exit 0) · `vite build` thành công (build ra scratchpad, không đụng `apps/web/dist`). Chưa xem bằng mắt trên trình duyệt vì API chưa trả trường mới.

| File (apps/web/src/…) | Thay đổi |
|---|---|
| lib/unit-dashboard-client.ts | `qty_principle` (ConsumptionQtys); `principle_undelivered` (OutlookBacklog + OutlookBreakdownRow); comment to_deliver 4 nhóm; nghĩa mới `unlinked_undelivered` |
| lib/sales-contract-client.ts | `Backlog.principle_undelivered`; comment `lt_unlinked_undelivered`, `to_deliver` |
| unit-dashboard/DashboardKpiRow.tsx | sub thẻ Tiêu thụ: `Chuyến X · HĐNT Y · dài hạn Z (tấn)`, có thêm `· chưa khai loại W` khi > 0 |
| unit-dashboard/ConsumptionSection.tsx | series "HĐ nguyên tắc" `#a78bfa` (tím), đặt giữa Dài hạn và Chuyến |
| unit-dashboard/OutlookEquation.tsx | ô "HĐNT đã ký chưa giao" giữa ô chuyến và ô dài hạn, luôn hiện; sửa sub ô dài hạn + comment |
| unit-dashboard/unit-dashboard.css | ≤1100px: `.ud-eq` xếp dọc (5–6 ô một hàng quá chật), nhóm "phải giao" vẫn một hàng |
| unit-dashboard/OutlookCard.tsx · OutlookPanels.tsx | câu "Tổng phải giao" có HĐNT; câu `unlinked_undelivered` = phụ lục dài hạn chưa gắn hồ sơ HĐDH |
| unit-dashboard/OutlookBreakdownTable.tsx | ⚠ bảng chưa từng có cột HĐ chuyến → thêm CẢ HAI cột "HĐ chuyến chưa giao" + "HĐNT chưa giao" trước "Còn phải giao" để đối chiếu được; sửa tooltip "Còn lại" + "Còn phải giao" |
| pages/components/consumption-report-totals.ts | `BacklogTotals.principle` (cộng `principle_undelivered`) |
| pages/components/ConsumptionCompanyTable.tsx | cột "HĐNT đã ký chưa giao (tấn)" ở dòng đơn vị + dòng tổng; colSpan 12 |
| pages/components/ConsumptionKpiRow.tsx | thẻ "HĐNT đã ký chưa giao (tấn)"; sửa sub thẻ dài hạn (giờ 9 thẻ, hàng cuối 1 thẻ) |
| pages/ConsumptionReportPage.tsx | câu giải thích: Tổng phải giao = chuyến + HĐNT + dài hạn |
| pages/analytics/ConsumptionStatsPage.tsx | cột `qty_principle` "HĐ nguyên tắc" sau HĐ chuyến; khi nhóm theo đơn vị/khu vực các cột KH vẫn đứng ngay sau HĐ chuyến, HĐNT lùi sau |
| pages/PeriodReportPage.tsx | cột `principle_export` "HĐNT — XK/UTXK", `principle_domestic` "HĐNT — Trong nước" sau 2 cột Chuyến (dòng Tổng cộng tự cộng); note Tổng "= 6 cột trên", XK/TN "DH + chuyến + HĐNT"; câu ghi chú: Excel mẫu Ban TTKD gộp HĐNT vào Chuyến |
| sections/DataLockConfirmModal.tsx | Kpi "HĐ nguyên tắc (tấn)" = `principle_total` giữa dài hạn và chuyến (snapshot cũ → "—") |
| sections/market-movement/ConsumptionBlock.tsx | "(chuyến / HĐ nguyên tắc / dài hạn)" |

Đã grep lại: không còn chỗ nào trong web tự cộng `spot_undelivered + lt_remaining` hay liệt kê `qty_spot`/`qty_long_term` mà bỏ sót HĐNT. Bộ lọc loại HĐ, nhãn dòng chi tiết, cột Chỉ số đơn vị đều lấy từ API nên không phải sửa.
