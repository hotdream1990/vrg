# Phase 05 — Tab Tuân thủ nhập liệu

**Context**: [plan.md](plan.md) (Đ7) · [phase-01](phase-01-khung-man-va-cay-khu-vuc.md)

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 4h · Phụ thuộc: Phase 01
- **Chạy song song được** với Phase 02 · 03 · 04.
- Tab có **2 chế độ xem**: (1) bảng chỉ số theo cây — mặc định; (2) **ma trận đơn vị × ngày**
  của màn "Theo dõi nộp báo cáo" hiện nay, mở bằng nút **"Xem lịch nộp theo ngày"**.

## Key insights
- `unit_report_status.status_report()` trả `filled / no_purchase / missing / expected` cho từng
  đơn vị và cho tổng — **chưa có trường tỷ lệ (%)**, web đang tự tính `pct` cho dòng tổng.
- Bảng này **cố ý KHÔNG gộp** đơn vị đã sáp nhập: "ai nộp, ai chưa" là chuyện của từng đơn vị nhập
  liệu. Ngày từ ngày sáp nhập trở đi mang trạng thái `merged`, **không vào mẫu số**. Giữ nguyên
  hành vi này — tab này là ngoại lệ có chủ ý so với 4 tab kia, phải ghi comment + chú thích trên UI.
- Biểu Thu mua chỉ tính đơn vị **được giao kế hoạch thu mua** (`companies_with_purchase_plan`),
  không dùng cờ `has_purchase_plan` cũ.
- Nút "Đánh dấu không tổ chức thu mua" (`MarkNoPurchaseButton`) là thao tác **GHI, chỉ admin** —
  phải giữ đúng như vậy khi chuyển sang tab.

## Requirements
**Chế độ 1 — bảng chỉ số (cây 2 cấp)**
| Cột | Luật gom khu vực |
|---|---|
| Lượt cần nộp | cộng |
| Đã nộp | cộng |
| Không tổ chức thu mua | cộng |
| Chưa nộp | cộng |
| **Tỷ lệ nộp (%)** | **tính lại từ tổng** = (Σ đã nộp + Σ không tổ chức) ÷ Σ cần nộp — KHÔNG lấy TB các % |
| Ngày nộp gần nhất | dòng cha **để trống** (mỗi đơn vị một ngày) |

- Chọn biểu: **Thu mua / Tồn kho** (Segmented) — thuộc riêng tab, lưu trong URL.
- Kỳ dùng chung với các tab khác; trần 366 ngày như hiện nay, vượt thì báo và không gọi API.
- Ô lọc chủng loại: **mờ** + ghi chú (QĐ-6).
- Đơn vị đã sáp nhập luôn đứng riêng; dòng khu vực **không** đếm ô `merged` vào mẫu số.

**Chế độ 2 — ma trận đơn vị × ngày**: bê nguyên `SubmissionStatusPage` (cột dính trái, 4 KPI,
`UnitLoginButton`, `MarkNoPurchaseButton`), chỉ bỏ phần thanh lọc riêng (dùng thanh lọc chung).

## Architecture
```
GET /api/unit-daily/index/compliance?kind=purchase|consumption&date_from&date_to
    &companies&regions&group_by=tree|company|region
  → { rows: cây, totals: {expected, filled, no_purchase, missing, pct}, warnings:[…] }

GET /api/unit-daily/analytics/status   ← GIỮ NGUYÊN, chế độ 2 gọi thẳng (đã đủ dùng)
```
Gom khu vực ở đây **không** đi qua `unit_report_tree.build_tree`: `status_report` chưa có
`group_by`. Cách rẻ nhất và đúng nhất: gọi `status_report` **một lần** (nó vốn trả theo đơn vị),
rồi gom lên khu vực bằng cộng thuần 4 con số + tính lại `pct`. Không có bình quân gia quyền nào
ở tab này nên cộng ở tầng gom là an toàn.

## Related code files
**Tạo**
- `apps/api/app/services/unit_report_compliance.py` (~80 dòng — gom khu vực + `pct`)
- `apps/web/src/features/command-center/pages/unit-index/tabs/ComplianceTab.tsx`
- `apps/web/src/features/command-center/pages/unit-index/tabs/SubmissionMatrix.tsx` (chế độ 2)

**Sửa**
- `apps/api/app/services/unit_report_status.py` — thêm `pct` vào mỗi dòng + `totals`
- `apps/api/app/routers/unit_index.py`
- `apps/web/src/lib/unit-index-client.ts`

**Dùng lại nguyên**: `pages/analytics/MarkNoPurchaseButton.tsx`, `pages/components/UnitLoginButton.tsx`,
`lib/unit-analytics-client.fetchSubmissionStatus`.

## Implementation steps
1. `unit_report_status.py`: thêm `"pct": (ok + skip) / due * 100 if due else None` cho mỗi dòng và
   cho `totals`. **`due == 0` → `None`, không phải 0%** (đơn vị không phải nộp ngày nào thì không
   có tỷ lệ để nói).
2. `unit_report_compliance.py`: gọi `status_report`, bỏ mảng `cells` (nặng, chế độ 1 không cần),
   gom theo `region` của từng dòng (`r["region"] or NO_REGION_LABEL`), cộng 4 số, **tính lại**
   `pct`, `last_day` của dòng cha = `None`. Comment rõ vì sao tab này không gộp sáp nhập.
3. Endpoint `/index/compliance`; giữ trần `MAX_STATUS_DAYS = 366` (import từ `unit_analytics`).
4. `SubmissionMatrix.tsx`: cắt phần bảng + KPI từ `SubmissionStatusPage.tsx`, nhận
   `{kind, filters}` từ ngoài; giữ nguyên `MarkNoPurchaseButton` (chỉ admin, chỉ biểu Thu mua).
5. `ComplianceTab.tsx`: Segmented biểu + nút chuyển chế độ ("Bảng chỉ số" ↔ "Xem lịch nộp theo ngày"),
   chế độ lưu trong URL (`?view=matrix`).
6. Test: thêm `test_compliance_rate_is_recomputed_from_totals` vào `apps/api/tests/test_unit_analytics.py`
   — 2 đơn vị tỷ lệ 100% và 0% với số ngày lệch nhau → `pct` khu vực **khác** 50%.

## Todo
- [ ] `pct` trong `unit_report_status` (due=0 → None) + không vỡ test cũ
- [ ] `unit_report_compliance.py` (gom khu vực, tính lại %, `last_day` cha = trống)
- [ ] Endpoint `/index/compliance`
- [ ] `SubmissionMatrix.tsx` bê từ màn cũ (giữ cột dính trái + 2 nút thao tác)
- [ ] `ComplianceTab.tsx` 2 chế độ, nhớ chế độ trong URL
- [ ] Test tỷ lệ nộp khu vực

## Success criteria
- Chế độ 1: `expected/filled/no_purchase/missing` của dòng TOÀN TẬP ĐOÀN = `totals` của
  `/analytics/status` cùng kỳ, cùng biểu.
- Tỷ lệ nộp khu vực = Σ đã nộp ÷ Σ cần nộp (ca test khoá lại), **không** bằng TB các đơn vị.
- Chế độ 2 giống hệt màn `/thong-ke/tinh-trang-nop` hiện nay: cột dính trái, 4 KPI, nút đăng nhập
  hộ (chỉ admin), nút đánh dấu hàng loạt (chỉ admin, xem trước rồi mới ghi).
- Đơn vị đã sáp nhập: ô từ ngày hiệu lực là `merged`, không tính vào "chưa nộp" và không vào mẫu số.
- Kỳ > 366 ngày → báo và **không** gọi API.
- `uv run pytest -q` xanh · `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Ai đó "thống nhất" tab này gộp sáp nhập như 4 tab kia | Comment + chú thích UI + test `merged` |
| Lấy TB các % của đơn vị (sai kinh điển) | Test ca 100%/0% lệch số ngày |
| Chế độ 2 kéo `cells` của 366 ngày × 70 đơn vị mỗi lần đổi tab | Chỉ gọi khi ở chế độ matrix; chế độ 1 không trả `cells` |
| Nút ghi (đánh dấu hàng loạt) lọt cho tài khoản chỉ-Xem | Giữ `require_admin` ở server; nút tự ẩn ở client |

## Security
Chế độ đọc: cap `unit_daily` mức Xem. Thao tác ghi duy nhất (`mark-no-purchase`) giữ nguyên
`require_admin` + 2 nhịp xem-trước-rồi-ghi + trần 5.000 ô. `UnitLoginButton` (đăng nhập hộ) giữ
nguyên điều kiện chỉ admin.

## Next steps
Tỷ lệ nộp là 1 cột của tab Tổng quan (Phase 07).
