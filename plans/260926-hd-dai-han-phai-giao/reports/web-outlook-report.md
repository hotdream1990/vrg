# Web — thẻ "Tiến độ bán hàng năm" trên Dashboard đơn vị (26/09/2026)

Trạng thái: **xong**. `cd apps/web && pnpm build` (tsc + vite) **sạch**, chỉ còn cảnh báo chunk > 500 kB có sẵn từ trước.
Không đụng `apps/api`, TargetsCard, DashboardKpiRow, ConsumptionReportPage. Không commit.
Đã chạy thử render phía server (vite ssrLoadModule + renderToString) với 3 bộ dữ liệu: đủ khoá, **thiếu hết khoá con**
(chỉ có scope/year/as_of) và xem một đơn vị có `items`. Cả 3 không vỡ, ô thiếu hiện "—". Chưa mở trình duyệt.

## File
| File | Việc |
|---|---|
| `src/lib/unit-dashboard-client.ts` | chỉ thêm: `OutlookLt/Backlog/Volume/Revenue`, `OutlookBreakdownRow`, `OutlookBlock`, `fetchDashOutlook`. Khoá con để `Partial`/optional: API viết song song, thiếu khoá thì hiện "—". File còn 198 dòng. |
| `unit-dashboard/OutlookCard.tsx` (mới, 46) | khung card, sub nêu cách tính, ghép các phần |
| `unit-dashboard/OutlookEquation.tsx` (mới, 64) | dòng phương trình sản lượng cả phạm vi |
| `unit-dashboard/OutlookPanels.tsx` (mới, 151) | 3 khối: HĐ mẹ · so KH bán hàng · doanh thu dự kiến |
| `unit-dashboard/OutlookBreakdownTable.tsx` (mới, 91) | bảng theo khu vực/đơn vị |
| `unit-dashboard/OutlookMasterItems.tsx` (mới, 53) | bảng HĐ mẹ khi xem 1 đơn vị |
| `unit-dashboard/OutlookBars.tsx` (mới, 62) | `PctProgress` (thanh to), `MiniPct` (thanh mini trong bảng), `MiniEquation` |
| `unit-dashboard/dashboard-format.ts` | thêm `fmtTons`, `isPositive`, `differsNotably` |
| `unit-dashboard/UnitDashboardPage.tsx` | khối thứ 6 `outlook`, đặt ngay sau TargetsCard. Đã sửa comment (6 khối) và biến `loading`. |
| `unit-dashboard/unit-dashboard.css` | class `ud-eq*`, `ud-ol-*`, `ud-mini-eq*`, `ud-cell-sub`, `ud-badge-gap`, rule mobile |

## Bố cục
1. **Dòng phương trình (cả phạm vi, tấn)**
   - Công thức: [Đã giao lũy kế] **+** [khung nét đứt "Tổng phải giao đến cuối năm = to_deliver"] **=** [Tổng bán cả năm (dự kiến)] (ô viền xanh).
   - Trong khung: HĐ chuyến đã ký chưa giao + HĐ dài hạn còn phải giao, thêm "HĐ chưa khai loại" khi > 0.
   - Dấu +/= là ký tự thường, không dùng emoji.
   - Màn ≤ 768px: xếp dọc, mỗi ô một hàng.
2. **3 khối** (lưới tự co: 3 cột trên màn 1440, 1 cột trên mobile):
   - *HĐ dài hạn theo HĐ mẹ*:
     - Dòng chính: "Đã giao X / cam kết Y tấn · còn Z", có thanh %.
     - Nhãn góc: "N HĐ mẹ có cam kết".
     - Dòng muted khi > 0: "HĐ mẹ đã hết hạn còn thiếu …" và "… tấn HĐ dài hạn chưa gắn HĐ mẹ (tính theo phụ lục đã ký)".
   - *So kế hoạch bán hàng*:
     - Dòng chính: "Bán cả năm (dự kiến) [rổ] / KH [rổ] tấn", có thanh %.
     - Phương trình nhỏ: KH khai thác + KH thu mua = KH bán hàng.
     - Câu nêu rổ: "Tính trên N đơn vị đã nhập KH khai thác". Nếu lệch > 0,5% thì kèm số cả phạm vi.
     - Nếu `units_missing_exploit` > 0: câu cảnh báo `ud-warn`.
     - Có hiện `note`.
   - *Doanh thu dự kiến*:
     - Dòng chính: "Rổ có KH: dự kiến / KH tỷ đ", có thanh %.
     - Phương trình nhỏ "Cả phạm vi": Đã thực hiện + Dự kiến phần còn lại = Tổng dự kiến.
     - Khi `pct` null: hiện `note` màu cảnh báo.
   - Khi xem 1 đơn vị: bỏ nhãn rổ, số chính lấy `projected`.
3. **Bảng theo khu vực/đơn vị** (khi `breakdown` không rỗng):
   - 2 tầng tiêu đề: HĐ dài hạn theo HĐ mẹ (Còn lại · % thực hiện) | Sản lượng cả năm (Còn phải giao · Bán cả năm · KH (KT + TM) · % KH) | Doanh thu (Dự kiến · KH · % KH).
   - Ô KH ghi tổng, dòng nhỏ bên dưới tách "KT … · TM …".
   - Mỗi tiêu đề cột có tooltip `title` giải thích cách tính.
   - Màn hẹp thì cuộn ngang trong `.ud-table-wrap`.
4. **Bảng HĐ mẹ** (chỉ khi xem 1 đơn vị và có `items`):
   - Cột: Số HĐ mẹ (nhãn "hết hạn") · HĐNT/HĐDH · Hiệu lực · Cam kết · Đã giao · Còn lại · %.
   - Cuộn dọc tối đa 330px, tiêu đề cột ghim trên.
- Không có vạch tiến độ thời gian: endpoint không trả `time_pct`, và số ở đây là cả năm dự kiến.
- Mọi % hiện số thật, kể cả khi > 100%; thanh thì dừng ở 100%.

## Ghi chú / việc sau
- `differsNotably` trong dashboard-format.ts trùng logic với `scopeDiffers` (hằng riêng) trong TargetsCard.tsx. Không được sửa TargetsCard nên chưa gộp. Nên gộp ở lượt sau.
- Nhãn "Rổ 3 đơn vị" / câu giải thích là `note` do server gửi, web hiện nguyên văn. Nếu note đã nêu rổ thì sẽ lặp một phần với câu "Tính trên N đơn vị…" của web. Cần xem lại khi backend chốt câu chữ.
- Cần kiểm lại trên dữ liệu thật và màn 1440 / mobile khi backend `/api/unit-dashboard/outlook` xong.
