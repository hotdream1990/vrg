# Phase 04 — Tab Hợp đồng

**Context**: [plan.md](plan.md) · [phase-01](phase-01-khung-man-va-cay-khu-vuc.md)

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 5h · Phụ thuộc: Phase 01
- **Chạy song song được** với Phase 02 · 03 · 05 (file backend riêng, file web riêng).
- Đây là tab **mới hoàn toàn** — chưa có màn nào gom tiến độ hợp đồng theo đơn vị/khu vực.

## Key insights
- `/api/sales-contracts` chỉ trả `totals` cho **cả bộ lọc**, không tách theo `company`
  (`sales_contract_report.parents_with_progress`, `_totals`). Đây là khoảng trống chính.
- Nhưng **đã có sẵn** 2 mảnh gom theo đơn vị, dùng lại được ngay:
  - `sales_contract_report.consumption(from, to, companies)` → `{đơn vị: {qty, revenue, deliveries,
    by_channel, by_type, by_grade, …}}` — sản lượng/doanh thu **đã giao** trong kỳ.
  - `sales_contract_report.undelivered_on(as_of, companies, grades)` → `{đơn vị: {qty, by_grade}}`
    — **đã ký chưa giao** tại một ngày.
  - `unit_report_query.roll_by_company()` gộp đơn vị đã sáp nhập cho cả 2 khối.
- Còn thiếu: **số hợp đồng đã ký trong kỳ · sản lượng đã ký · đang chờ giao · giao vượt** theo đơn vị.
  Câu SQL tính các số này đã có trong `parents_with_progress` (CTE `parent/kid/progress/scored`),
  chỉ thiếu bản `GROUP BY company`.

## Requirements
Cột của tab (dòng = đơn vị · khu vực · tập đoàn):
| Cột | Nguồn | Luật gom khu vực |
|---|---|---|
| Số HĐ ký trong kỳ | SQL group-by mới | cộng |
| Sản lượng đã ký (tấn) | SQL group-by mới | cộng |
| Đã giao trong kỳ (tấn) | `consumption()` | cộng |
| Doanh thu đã giao (tỷ đ) | `consumption()` | cộng, **trống** nếu có đợt thiếu tỷ giá |
| Giá bán BQ (triệu đ/tấn) | tính | **BQ gia quyền** = Σ doanh thu ÷ Σ sản lượng có doanh thu |
| Số đợt giao | `consumption()` | cộng |
| Đang chờ giao (tấn) | SQL group-by mới (`pending_qty`) | cộng |
| Còn phải giao (tấn) | SQL group-by mới (`remaining_qty`) | cộng |
| Giao vượt (tấn) | SQL group-by mới (`over_qty`) | cộng |
| Đã ký chưa giao tại ngày chốt (tấn) | `undelivered_on()` | cộng |

- Lọc: kỳ · khu vực · đơn vị · **chủng loại** (bật) · **loại HĐ** · **hình thức** · `split_merged`.
- Bấm dòng đơn vị → mở **danh sách hợp đồng của đơn vị đó** (dùng lại `/api/sales-contracts`
  với `company=`, **có phân trang server sẵn**) — không dựng bảng hợp đồng mới.
- Doanh thu thiếu tỷ giá: hiện **trống** + cảnh báo "n hợp đồng/đợt chưa quy đổi được", theo đúng
  quy ước `_totals` (`*_missing`) — **không** cộng thiếu rồi coi như đủ.

## Architecture
```
GET /api/unit-daily/index/contract
    ?date_from&date_to&as_of&companies&regions&grades&contract&channel&split_merged&group_by=tree|company|region
```
Backend chia 2 file cho gọn (file cũ đã 533 dòng):
1. `sales_contract_report.py` — **chỉ tách CTE**: rút phần dựng `where/params/sql/keep` của
   `parents_with_progress` ra hàm `_progress_cte(...) -> (sql, keep, params)`; `parents_with_progress`
   gọi lại hàm đó (hành vi **không đổi**, test hiện có phải vẫn xanh). Thêm
   `progress_by_company(...)` chạy `GROUP BY company` trên CTE đó.
2. `services/unit_report_contract.py` (mới, ~120 dòng) — ghép 3 nguồn (`progress_by_company`,
   `consumption`, `undelivered_on`), áp `roll_by_company` + `merge_scope/merge_view`, gom theo
   `company` hoặc `region`, tính giá BQ **gia quyền**.

## Related code files
**Tạo**
- `apps/api/app/services/unit_report_contract.py`
- `apps/web/src/features/command-center/pages/unit-index/tabs/ContractTab.tsx`
- `apps/web/src/features/command-center/pages/unit-index/tabs/contract-cols.ts`
- `apps/api/tests/test_unit_index_contract.py`

**Sửa**
- `apps/api/app/services/sales_contract_report.py` (tách `_progress_cte` + thêm `progress_by_company`)
- `apps/api/app/routers/unit_index.py`
- `apps/web/src/lib/unit-index-client.ts`

## Implementation steps
1. Tách `_progress_cte` trong `sales_contract_report.py`. Chạy `uv run pytest -q -k contract`
   **trước khi viết tiếp** — phải xanh y như trước (đây là refactor thuần).
2. `progress_by_company(...)`: dùng `_progress_cte`, `SELECT company, count(*) …, sum(pqty) …
   FROM scored WHERE {keep} GROUP BY company`. Ép `float()` mọi tổng (Postgres trả Decimal →
   JSON thành chuỗi, bài học đã ghi trong file).
3. `unit_report_contract.report(...)`:
   - `scope = merge_scope(comps, split_merged)` để truy vấn; `view = merge_view(...)` để lọc hiển thị.
   - `roll_by_company()` cho cả 3 khối trước khi gom.
   - Gom theo khu vực: cộng các số; giá BQ **tính lại** từ Σ doanh thu ÷ Σ sản lượng có doanh thu.
   - Thiếu tỷ giá: giữ cờ `revenue_missing` lan lên dòng cha → doanh thu + giá BQ của cha **trống**.
   - Ghi comment 6 luật gom khu vực ngay đầu hàm gom.
4. Endpoint `/index/contract`, `group_by="tree"` đi qua `unit_report_tree.build_tree`.
5. `contract-cols.ts` + `ContractTab.tsx`; bấm dòng đơn vị → mở `Drawer`/`Modal` liệt kê hợp đồng
   gọi `/api/sales-contracts?company=…&page=…` (đã phân trang sẵn).
6. Test `test_unit_index_contract.py`: (a) tổng theo đơn vị = `totals` của `/api/sales-contracts`
   cùng bộ lọc; (b) giá BQ khu vực ≠ trung bình cộng 2 đơn vị có sản lượng lệch nhau;
   (c) một đợt thiếu tỷ giá → doanh thu đơn vị và khu vực đều **trống** + có cảnh báo;
   (d) `split_merged=false` → đơn vị đã sáp nhập không có dòng riêng, số nằm ở đơn vị nhận.

## Todo
- [ ] Tách `_progress_cte` (refactor thuần, test cũ xanh)
- [ ] `progress_by_company` (GROUP BY company, ép float)
- [ ] `unit_report_contract.py` ghép 3 nguồn + gom khu vực
- [ ] Endpoint `/index/contract`
- [ ] `contract-cols.ts` · `ContractTab.tsx` · drawer danh sách HĐ (phân trang server)
- [ ] `test_unit_index_contract.py` (4 ca)

## Success criteria
- Với bộ lọc bất kỳ: Σ các dòng đơn vị = `totals` của `/api/sales-contracts` cùng bộ lọc (từng cột).
- "Đã ký chưa giao tại ngày chốt" của tab này = cột `signed_undelivered` ở tab Tồn kho cùng ngày
  (cùng một hàm `undelivered_on`) — **phải khớp tuyệt đối**, lệch là lỗi.
- Giá bán BQ khu vực ≠ trung bình cộng các đơn vị (kiểm bằng ca test b).
- Đợt thiếu tỷ giá: ô doanh thu trống + cảnh báo đếm đúng số đợt.
- `uv run pytest -q` xanh · `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Đếm trùng hợp đồng mẹ ↔ phụ lục ↔ đợt giao | CTE đã lọc `parent_id IS NULL`; test (a) khoá lại |
| Refactor CTE làm vỡ màn Hợp đồng đang chạy | Bước 1 tách xong chạy test ngay, chưa viết gì thêm |
| HĐ mẹ (HĐNT/HĐDH) lọt vào báo cáo sản lượng | HĐ mẹ chỉ là liên kết — không vào `sales_contract`; giữ nguyên nguồn dữ liệu, không tự thêm |
| Kỳ lọc theo `sign_date` vs kỳ giao theo `delivered_at` lẫn lộn | Ghi rõ trên đầu cột: "ký trong kỳ" vs "giao trong kỳ" |

## Security
Chỉ đọc, cap `unit_daily` mức Xem. Không dùng `cap_or_member_scope` ở đây (tab dành cho Ban TTKD,
không dùng chung với tài khoản đơn vị).

## Next steps
Tab này cấp 2 chỉ số cho Tổng quan (Phase 07): "Còn phải giao" và "Đã ký chưa giao".
