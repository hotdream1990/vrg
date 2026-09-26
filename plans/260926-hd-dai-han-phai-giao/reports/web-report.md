# Web — HĐ dài hạn theo HĐ mẹ · phải giao · soát Dashboard đơn vị (26/09/2026)

Trạng thái: **xong**. `cd apps/web && pnpm build` (tsc + vite) **sạch** (chỉ cảnh báo chunk > 500 kB có sẵn).
Không đụng `apps/api`. Không commit.

## File
| File | Việc |
|---|---|
| `src/lib/sales-contract-client.ts` | + `Backlog`, `BacklogItem`; `ConsumptionReport.backlog?`, `backlog_as_of?` |
| `src/lib/unit-dashboard-client.ts` | + `bad_price_lines?` (totals + breakdown tiêu thụ), `scope_done?` (item chỉ tiêu) |
| `pages/ConsumptionReportPage.tsx` | 216 → 133 dòng: tách KPI/bảng ra component; câu mô tả "Tổng phải giao" ≠ "Đã ký HĐ chưa giao" |
| `pages/components/consumption-report-totals.ts` (mới) | định dạng số + cộng tổng từ dòng đơn vị (`sumConsumption`, `sumBacklog`, `spotOf`, `reportCompanies`) |
| `pages/components/ConsumptionKpiRow.tsx` (mới) | 8 thẻ (2 hàng × 4) |
| `pages/components/ConsumptionCompanyTable.tsx` (mới) | bảng theo đơn vị, 3 cột phải giao + tfoot |
| `pages/components/ConsumptionMasterProgress.tsx` (mới) | khối "HĐ dài hạn theo HĐ mẹ" |
| `pages/components/ConsumptionMasterItems.tsx` (mới) | bảng con từng HĐ mẹ + `PctBar` |
| `pages/components/consumption-master-progress.css` (mới) | class `cmp-*` riêng khối mới (không sửa bulletin.css) |
| `unit-dashboard/TargetsCard.tsx` · `DashboardKpiRow.tsx` · `dashboard-format.ts` | việc 2 |

## Quyết định UI
- **Thẻ KPI**: 4 thẻ cũ + "HĐ chuyến đã ký chưa giao" (= Σ spot + unknown, sub "Gồm X tấn HĐ chưa khai loại" khi > 0) · "HĐ dài hạn còn phải giao" (Σ lt_remaining) · "Tổng phải giao đến cuối năm" (Σ to_deliver) · "HĐ dài hạn theo HĐ mẹ" (% = Σ delivered / Σ committed; sub "Đã giao A / cam kết B tấn · còn C" với C = Σ master_remaining). Không có cam kết → "—".
- Cột "HĐ chuyến chưa giao" cũng = spot + unknown để 3 cột cộng khớp "Tổng phải giao".
- Danh sách đơn vị = có lần giao ∪ có `undelivered` ∪ backlog có `masters > 0` hoặc `to_deliver > 0` (đơn vị chưa giao lần nào trong kỳ vẫn hiện phần phải giao).
- **API cũ** (không có `backlog`): giữ thẻ + cột "Chưa giao" từ `undelivered`, khối HĐ mẹ ẩn.
- **Khối HĐ mẹ**: chỉ đơn vị `masters > 0`, xếp theo tên (khớp bảng trên); bấm dòng mở bảng con (Số HĐ mẹ · Loại HĐNT/HĐDH · Khách · Hiệu lực · Cam kết · Đã giao · Còn lại · %; nhãn "hết hạn"). Cột "Hết hạn chưa giao đủ" chỉ hiện khi có đơn vị > 0. Không dùng `.table-scroll` (nó ghim cả thead bảng con).
- **Tên khách**: tái dùng `rep.customers`; cột Khách chỉ hiện khi tra được ít nhất 1 tên (backend nên đưa customer_id của items vào `customers` thì mới có tên).
- **TargetsCard**: dòng số "X / Y đơn vị · N đơn vị có KH" (ẩn phần rổ khi xem 1 đơn vị); dòng muted "Cả phạm vi: … (gồm đơn vị chưa giao KH)" khi |scope_done − done| > 0,5% done; có KH mà pct null → note màu `ud-warn`.
- **KPI Doanh thu**: `bad_price_lines > 0` → "N dòng bán nghi sai đơn vị tính — doanh thu đang bị đội lên" (+ " · chưa gồm M lần giao thiếu tỷ giá" nếu có cả hai), màu warn.
- **KPI Thu mua**: ngày cuối = "hôm nay dd/mm/yyyy" khi date_to ở tương lai (`rangeEndLabel`, giờ địa phương).

## Ghi chú
- `apps/web` còn 2 file đang sửa KHÔNG phải của agent này: `SupportThreadPage.tsx`, `sections/SupportReplyBox.tsx`.
- Chưa chạy trình duyệt (theo yêu cầu) — cần kiểm lại trên dữ liệu thật khi backend xong.
