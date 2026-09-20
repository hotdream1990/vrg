# Phase 08 — Gộp màn cũ · redirect · menu

**Context**: [plan.md](plan.md) (Đ7, Đ8) · Phase 02–05

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 3h
- Phụ thuộc: **02 · 03 · 04 · 05** (4 tab phải chạy đủ trước khi xoá màn cũ). Song song với 06 · 07 · 09.
- Xoá hẳn 4 màn cũ, chuyển hướng 4 đường dẫn cũ sang đúng tab, cập nhật **cả 2** menu.

## Key insights
- 4 đường dẫn cũ **đã gửi cho VRG** → chỉ được `Navigate replace`, không được để 404.
  Repo đã có tiền lệ: `/bao-cao-tieu-thu-ton-kho` → `/bao-cao-ton-kho` (`App.tsx`).
- Menu khai ở **2 chỗ**: `buildMenu` (nhóm `stats`, ~dòng 129) và `buildExecutiveMenu` (~dòng 174).
  Sửa một chỗ là lãnh đạo Tập đoàn mất mục — `executive` đã có sẵn cap `unit_daily`.
- **GIỮ RIÊNG** (Đ8): `/bao-cao-tong-hop` (Báo cáo tổng hợp, in theo mẫu Biểu (1)/(2)) và
  `/chot-so-lieu` (Chốt số liệu đơn vị — thao tác ghi). Không đụng.
- `/thong-ke-hop-dong` (Hợp đồng cũ, đã ẩn khỏi menu 20/08/2026) cũng **không** đụng.

## Requirements
| Đường dẫn cũ | Chuyển tới |
|---|---|
| `/thong-ke/thu-mua` | `/chi-so-don-vi?tab=thu-mua` |
| `/thong-ke/tieu-thu` | `/chi-so-don-vi?tab=tieu-thu` |
| `/thong-ke/ton-kho` | `/chi-so-don-vi?tab=ton-kho` |
| `/thong-ke/tinh-trang-nop` | `/chi-so-don-vi?tab=tuan-thu` |

- Menu: **một mục duy nhất** "Chỉ số đơn vị" (`/chi-so-don-vi`, icon `<BarChartOutlined />`) thay
  4 mục `statPurchase` · `statStock` · `statConsumption` · `submission`, ở **cả** `buildMenu` và
  `buildExecutiveMenu`. Đặt ngay sau "Báo cáo tổng hợp" trong nhóm `stats`.
- Xoá 4 file page cũ + import của chúng trong `App.tsx`; giữ lại các component dùng chung
  (`StatsTable`, `AnalyticsFilters`, `DrillHeader`, `StockCoverageBar`, `MarkNoPurchaseButton`,
  `use-stats`, `use-drill`) — vẫn còn chỗ dùng.
- Kiểm tra **không còn tham chiếu** `/thong-ke/thu-mua|tieu-thu|ton-kho|tinh-trang-nop` ở nơi khác
  (trợ lý AI, sổ tay, email nhắc lịch, `docs/`).

## Related code files
**Sửa**
- `apps/web/src/App.tsx` — thêm 4 `<Navigate>`, xoá 4 import + 4 route cũ
- `apps/web/src/features/command-center/sidebar-menu-builders.tsx` — `ITEM.unitIndex`, sửa
  `buildMenu` (nhóm `stats`) **và** `buildExecutiveMenu` (nhóm `stats`); bỏ 4 `ITEM` cũ nếu hết chỗ dùng

**Xoá**
- `apps/web/src/features/command-center/pages/analytics/PurchaseStatsPage.tsx`
- `apps/web/src/features/command-center/pages/analytics/ConsumptionStatsPage.tsx`
- `apps/web/src/features/command-center/pages/analytics/StockStatsPage.tsx`
- `apps/web/src/features/command-center/pages/analytics/SubmissionStatusPage.tsx`

## Implementation steps
1. Quét tham chiếu trước khi xoá:
   `grep -rn "thong-ke/thu-mua\|thong-ke/tieu-thu\|thong-ke/ton-kho\|thong-ke/tinh-trang-nop" apps/web/src apps/api/app docs scripts`
   — sửa hết chỗ trỏ tới (nếu có trong trợ lý AI / sổ tay / email).
2. `App.tsx`: trong block `RequireCap caps={["unit_daily"]}` thay 4 route bằng
   `<Route path="/thong-ke/thu-mua" element={<Navigate to="/chi-so-don-vi?tab=thu-mua" replace />} />`
   (và 3 dòng tương tự). Xoá 4 import.
3. `sidebar-menu-builders.tsx`: thêm
   `unitIndex: { key: "/chi-so-don-vi", icon: <BarChartOutlined />, label: "Chỉ số đơn vị" }`
   vào `ITEM`; thay 4 dòng ở `buildMenu` và 4 dòng ở `buildExecutiveMenu` bằng
   `can("unit_daily") && ITEM.unitIndex`.
4. Xoá 4 file page. Chạy `pnpm build` — TypeScript sẽ chỉ ra mọi import còn sót.
5. Kiểm tay 4 đường dẫn cũ (dán thẳng vào trình duyệt) → mở đúng tab, kỳ mặc định đúng.
6. Đăng nhập bằng tài khoản `executive` (hoặc đổi tạm role) → menu có "Chỉ số đơn vị", vào được.
7. Đăng nhập bằng tài khoản không có cap `unit_daily` → không thấy mục, vào URL bị chặn.

## Todo
- [ ] Quét & sửa mọi tham chiếu tới 4 đường dẫn cũ
- [ ] 4 `<Navigate replace>` trong `App.tsx`
- [ ] `ITEM.unitIndex` + sửa **cả 2** hàm dựng menu
- [ ] Xoá 4 file page cũ, `pnpm build` xanh
- [ ] Kiểm tay 4 redirect + 3 loại tài khoản (admin · executive · không có cap)

## Success criteria
- Dán `/thong-ke/tinh-trang-nop` → về `/chi-so-don-vi?tab=tuan-thu`, **không** nháy 404, URL thay
  hẳn (dùng `replace` nên nút Back không kẹt vòng lặp).
- Menu chuyên viên **và** menu Lãnh đạo Tập đoàn đều có đúng **một** mục "Chỉ số đơn vị".
- "Báo cáo tổng hợp" và "Chốt số liệu đơn vị" **vẫn còn nguyên** ở menu và chạy được.
- `grep` không còn kết quả nào trỏ tới 4 đường dẫn cũ (ngoài 4 dòng `Navigate`).
- `pnpm build` xanh, không còn import mồ côi.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Sót `buildExecutiveMenu` → lãnh đạo Tập đoàn mất màn | Ghi rõ "cả 2 hàm" trong todo; bước 6 kiểm tay |
| Xoá màn cũ khi tab mới còn thiếu chức năng | Phase này chạy **sau** 02–05; checklist đối chiếu chức năng ở Phase 10 |
| Còn chỗ khác trỏ tới đường dẫn cũ (sổ tay Word, email) | Bước 1 quét cả `docs/` và `scripts/` |
| `Navigate` mất query của link cũ (vd người dùng bookmark kèm tham số) | Link cũ không mang tham số (bộ lọc trước đây nằm trong state) — không cần giữ |

## Security
Không đổi mô hình quyền: route mới vẫn nằm trong `RequireCap caps={["unit_daily"]}`.

## Next steps
Phase 10 chạy checklist "màn mới có đủ mọi thứ màn cũ có" trước khi deploy.
