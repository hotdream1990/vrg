# Phase 06 — Cột so sánh kỳ (liền trước · cùng kỳ năm trước)

**Context**: [plan.md](plan.md) (Đ6, rủi ro 1) · Phase 02–05

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 5h
- Phụ thuộc: **02 · 03 · 04 · 05** (cần các endpoint tab đã chạy). Song song được với 07 · 08 · 09.
- Làm **cả hai** cột so sánh + % chênh lệch, dùng chung một cơ chế cho mọi tab.

## Key insights
- Dữ liệu đơn vị thực tế **chỉ có từ 01/2026** → cột "cùng kỳ năm trước" sẽ **trống gần hết trong
  2026**. Phải hiện ô TRỐNG + chú thích, **tuyệt đối không đắp 0** (nguyên tắc cứng
  `no-cross-date-data-substitution`).
- ⚠ **Bản sao DB cục bộ có 17 bản ghi `unit_daily_report` rơi vào năm 2025**
  (6 `purchase`: 05/04 · 11/05 · 15/05 · 24/06 · 27/06 · 08/07 — 11 `consumption`: 26/07 → 31/12,
  riêng Eah Leo 5 dòng tháng 11–12). Nghi **gõ nhầm năm**. Nếu prod cũng có, cột "cùng kỳ năm
  trước" sẽ hiện vài con số lẻ vô nghĩa. **Phải kiểm trên DB chạy thật trước — KHÔNG tự sửa dữ liệu**
  (xem bước 1).
- `% chênh` khi kỳ gốc trống hoặc bằng 0 → **trống**, không phải "+∞" hay "100%".

## Requirements
- Mỗi chỉ tiêu **so sánh được** có thêm 4 ô: `{key}_prev`, `{key}_prev_pct`, `{key}_yoy`, `{key}_yoy_pct`.
- Chỉ tiêu **không** so sánh được thì không sinh cột: `as_of` (ngày lấy số), `age_days`,
  `plan_*` (chỉ tiêu năm — so với chính nó vô nghĩa), `last_day`.
- Công tắc **"Hiện cột so sánh"** trên thanh lọc (mặc định BẬT), lưu trong URL — tắt đi thì server
  không chạy kỳ so sánh (đây cũng là van hiệu năng).
- Định nghĩa kỳ so sánh:
  | Tab | Kỳ liền trước | Cùng kỳ năm trước |
  |---|---|---|
  | Thu mua · Tiêu thụ · Hợp đồng · Tuân thủ | cùng độ dài, kề ngay trước `from` | `from`/`to` lùi **đúng 1 năm** |
  | Tồn kho | **ngày chốt** lùi đúng độ dài kỳ đang chọn | **ngày chốt** lùi 1 năm |
- Chú thích hiện **một lần trên đầu bảng** khi cột YoY trống toàn bộ:
  "Số liệu đơn vị chỉ có từ 01/2026 — cùng kỳ năm trước chưa có dữ liệu để so."

## Architecture
`services/unit_report_compare.py` (mới, ~90 dòng):
```python
def shift_period(date_from, date_to, mode) -> tuple[str, str]:
    """mode='prev' → lùi đúng (to-from+1) ngày; mode='yoy' → lùi 1 năm (29/02 → 28/02)."""

def attach(base: dict, others: dict[str, dict], keys: Sequence[str]) -> dict:
    """Gắn {key}_prev/_yoy/_*_pct vào từng dòng của `base`, khớp theo row['key'] ở CẢ 2 CẤP CÂY.
    Dòng không tìm thấy ở kỳ so sánh → None (đơn vị kỳ đó chưa tồn tại / chưa nộp) — KHÔNG ghi 0.
    """
```
Router: mỗi endpoint tab nhận `compare=prev,yoy` (mặc định `prev,yoy`; rỗng = tắt), gọi lại chính
hàm báo cáo của mình với kỳ đã dịch rồi `attach`. **Không** nhân bản logic gom ở đâu cả.

## Related code files
**Tạo**
- `apps/api/app/services/unit_report_compare.py`
- `apps/web/src/features/command-center/pages/unit-index/compare-cols.ts` (sinh `StatsCol` so sánh từ cột gốc)
- `apps/api/tests/test_unit_index_compare.py`

**Sửa**
- `apps/api/app/routers/unit_index.py` (mọi endpoint nhận `compare`)
- `apps/web/src/features/command-center/pages/unit-index/IndexFilters.tsx` (công tắc)
- `apps/web/src/features/command-center/pages/unit-index/use-index-context.ts` (`compare` vào URL)
- `apps/web/src/features/command-center/pages/unit-index/IndexTree.tsx` (cụm cột so sánh gộp nhóm, có thể thu lại)
- 5 file `tabs/*-cols.ts` (đánh dấu cột nào so sánh được)

## Implementation steps
1. **Kiểm dữ liệu 2025 trên prod TRƯỚC** (chỉ đọc):
   ```sql
   SELECT as_of, kind, company FROM unit_daily_report WHERE as_of < '2026-01-01' ORDER BY as_of;
   ```
   Ghi kết quả vào `reports/du-lieu-2025-prod.md`, **gửi chủ dự án hỏi** trước khi làm gì tiếp.
   Không có trên prod → không phải lo. Có → ghi chú trên UI + để chủ dự án quyết định sửa hay để.
   **Không tự sửa/xoá dữ liệu.**
2. `shift_period`: `prev` = lùi `(to - from + 1)` ngày cả 2 đầu. `yoy` = `.replace(year=y-1)`,
   bắt `ValueError` cho 29/02 → 28/02. Có test riêng cho năm nhuận.
3. `attach`: duyệt đệ quy `rows` + `children`, khớp theo `row["key"]`. Công thức
   `pct = (now - old) / abs(old) * 100` chỉ khi `old` là số **và** `abs(old) > 1e-9`; ngược lại `None`.
4. Router: tham số `compare: str = Query("prev,yoy")`; rỗng → bỏ qua. Mỗi mode = **một lượt gọi
   lại** hàm báo cáo (với cây là 2 lượt gom) → tối đa 6 lượt. Đo lại thời gian, ghi `reports/perf.md`.
5. `compare-cols.ts`: từ cột gốc sinh cột `{label} kỳ trước`, `± % kỳ trước`, `{label} cùng kỳ 2025`,
   `± % cùng kỳ`. Nhóm cột (`colSpan` trong `<thead>`) để bảng đọc được.
6. `IndexTree.tsx`: ô % tô màu (tăng = `var(--accent)`, giảm = `var(--danger)`), ô trống hiện `—`
   với `title` = "Kỳ so sánh không có số liệu".
7. Chú thích toàn bảng khi mọi ô YoY trống.

## Todo
- [ ] Kiểm 17 bản ghi 2025 trên **DB prod**, ghi `reports/du-lieu-2025-prod.md`, hỏi chủ dự án
- [ ] `shift_period` (+ test năm nhuận 29/02)
- [ ] `attach` (đệ quy 2 cấp cây, ô trống ≠ 0)
- [ ] Tham số `compare` cho 5 endpoint + đo hiệu năng
- [ ] `compare-cols.ts` + nhóm cột trong `IndexTree`
- [ ] Công tắc "Hiện cột so sánh" (mặc định bật, lưu URL)
- [ ] Chú thích "dữ liệu chỉ có từ 01/2026"
- [ ] `test_unit_index_compare.py`

## Success criteria
- Kỳ = tháng 8/2026: cột "kỳ trước" hiện số của tháng 7/2026 (đối chiếu tay 1 đơn vị).
- Cột "cùng kỳ năm trước" **trống** (`—`), **không** ra 0, và có chú thích trên đầu bảng.
- Đơn vị có số kỳ này nhưng kỳ trước không nộp → ô trống, **%** cũng trống (không phải +100%).
- Đơn vị kỳ trước có số, kỳ này bằng 0 → `% = -100%`.
- Tab Tồn kho: cột so sánh là tồn tại **ngày chốt lùi lại**, không phải tổng của kỳ.
- Tắt công tắc: response **không** có trường `_prev`/`_yoy` và thời gian giảm rõ rệt.
- `uv run pytest -q` xanh · `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| 17 bản ghi 2025 làm cột YoY hiện số lẻ vô nghĩa | Bước 1 — kiểm prod, báo chủ dự án, KHÔNG tự sửa |
| 6 lượt quét/tab → chậm | Công tắc tắt được; đo ở bước 4; phương án B của QĐ-3 |
| `% chênh` chia cho 0 | Ngưỡng `abs(old) > 1e-9`, có test |
| 29/02 khi lùi 1 năm | Bắt `ValueError` → 28/02, có test |
| Bảng quá nhiều cột, không đọc nổi | Nhóm cột + cho phép thu cụm so sánh; mặc định chỉ so sánh các cột chính (sản lượng · doanh thu · tỷ lệ) |

## Security
Chỉ đọc. `compare` là danh sách trắng `{"prev","yoy"}` — giá trị lạ bị bỏ, không ghép thẳng vào SQL.

## Next steps
Phase 09 xuất Excel phải mang theo cột so sánh khi công tắc đang bật.
