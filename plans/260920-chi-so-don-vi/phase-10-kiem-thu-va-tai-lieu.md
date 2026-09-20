# Phase 10 — Kiểm thử · sổ tay · deploy

**Context**: [plan.md](plan.md) · toàn bộ phase trước

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 5h
- Phụ thuộc: **06 · 07 · 08 · 09**. **Làm một mình** — không chạy song song với phase nào
  (đụng git, chạy đủ bộ test, deploy).

## Key insights
- Web **không có test runner** → kiểm thử giao diện bằng **Playwright chụp màn đã đăng nhập**
  (khuôn mẫu ở `local-testing-and-screenshots`), lưu vào `plans/260920-chi-so-don-vi/visuals/`.
- Bẫy môi trường đã biết: modal AntD đứng khi chạy cục bộ · Vite đổi tên file build ·
  **DB dev dùng chung** (test ghi rác — `conftest.py` đã dọn `audit_log`/`access_log`).
- Sổ tay người dùng **chỉ dạy dùng chức năng** — không đưa kết quả kiểm thử, danh sách lỗi, tên
  file/hàm vào (`documentation-management`).

## Requirements
1. **Checklist "không mất chức năng"** — màn mới phải có đủ mọi thứ 4 màn cũ có.
2. Bộ test backend xanh + bổ sung test đối soát.
3. Ảnh chụp 6 tab (sáng/tối) lưu `visuals/`.
4. Cập nhật sổ tay + changelog + roadmap.
5. Deploy theo skill `deploy`, sau deploy kiểm lại 4 redirect trên prod.

## Checklist "không mất chức năng"
| Chức năng của màn cũ | Tab mới | Đã có |
|---|---|---|
| Lọc loại mủ (latex/cup/finished) | Thu mua | ☐ |
| Lọc chủng loại (chỉ khi chọn thành phẩm) | Thu mua | ☐ |
| Lọc loại HĐ · hình thức | Tiêu thụ | ☐ |
| Bảng chi tiết từng lần giao **CÓ PHÂN TRANG** | Tiêu thụ | ☐ |
| Drill-down (khu vực → đơn vị → ngày → …) | mọi tab | ☐ |
| Ô "Nhóm theo" đủ lựa chọn cũ | mọi tab | ☐ |
| Biểu đồ cột + KPI (`DrillHeader`) | mọi tab | ☐ |
| Dải độ phủ tồn kho + cột "Ngày lấy số" + "Số cũ" | Tồn kho | ☐ |
| Ô "xem lại N ngày" khi nhóm theo NGÀY | Tồn kho | ☐ |
| Ma trận đơn vị × ngày | Tuân thủ (chế độ 2) | ☐ |
| Nút "Đánh dấu không tổ chức thu mua" (admin, 2 nhịp) | Tuân thủ | ☐ |
| Nút "Đăng nhập hộ" (`UnitLoginButton`, admin) | Tuân thủ | ☐ |
| Công tắc "Tách đơn vị đã sáp nhập" | mọi tab | ☐ |
| Xuất Excel | 6 tab | ☐ |
| Cảnh báo (thiếu tỷ giá · thiếu đơn giá · % KH khi lọc) | mọi tab | ☐ |

## Test bổ sung (pytest)
- `test_unit_index_tree.py`
  - dòng khu vực = kết quả `group_by="region"`, **không** phải tổng các dòng con (đặt 2 đơn vị
    sản lượng lệch nhau, kiểm đơn giá BQ khu vực ≠ TB cộng);
  - `% KH` khu vực = Σ thực hiện ÷ Σ kế hoạch;
  - đơn vị chưa gán khu vực rơi vào "(Chưa gán khu vực)", không mất;
  - `split_merged=false` → đơn vị đã sáp nhập không có dòng riêng.
- `test_unit_index_reconcile.py` — **đối soát chéo** (điều kiện chốt của QĐ-1):
  - `/index/overview` ↔ 5 endpoint tab gốc (từng ô, 1 đơn vị);
  - `/index/overview` (thu mua) ↔ `/api/unit-daily/period-report?kind=purchase` cùng kỳ;
  - `/index/stock` (`signed_undelivered`) ↔ `/index/contract` (đã ký chưa giao) cùng ngày;
  - `/index/*` ↔ `/analytics/*` cũ (nếu còn) trên cùng bộ lọc.
- Chạy đủ: `cd apps/api && uv run pytest -q` (69 file test hiện có phải **vẫn xanh**).

## Kiểm thử giao diện (Playwright)
Kịch bản, lưu ảnh `visuals/2026-09-XX-chi-so-don-vi/`:
1. Đăng nhập admin → `/chi-so-don-vi` → chụp 6 tab (khu vực gập và mở).
2. Đổi kỳ ở tab Thu mua → sang tab Tiêu thụ → **kỳ vẫn nguyên** (chụp 2 ảnh liên tiếp).
3. Tab Tồn kho: ô "Chốt ngày" thay ô Kỳ; quay lại tab Thu mua, kỳ còn nguyên.
4. Tab không gắn chủng loại: ô lọc **mờ** + ghi chú (chụp cận cảnh).
5. Cột "cùng kỳ năm trước" trống + chú thích (chụp cận cảnh).
6. Dán 4 đường dẫn cũ → mở đúng tab (4 ảnh).
7. Tài khoản `executive` → menu có "Chỉ số đơn vị", vào được.

## Tài liệu
- `docs/huong-dan/` — mục mới "Chỉ số đơn vị": **chỉ dạy dùng** (mở ở đâu · 6 tab là gì · cách gập
  mở khu vực · vì sao tab Tồn kho hỏi "Chốt ngày" · vì sao ô chủng loại có lúc mờ · vì sao cột
  cùng kỳ năm trước trống). Bước đánh số + ảnh (dùng skill `screenshot-annotate`).
  **Không** đưa vào: kết quả test, tên file/hàm, ghi chú kỹ thuật.
- `docs/project/project-changelog.md` — mục "Chỉ số đơn vị" (gộp 4 màn, redirect, sửa cột mủ dây
  trong Excel, bổ sung % KH doanh thu ở tiêu thụ).
- `docs/project/development-roadmap.md` — cập nhật tiến độ.
- Cập nhật memory: tạo `unit-index-feature.md` + thêm dòng vào `MEMORY.md`
  (đường dẫn mới, 4 redirect, luật gom khu vực, quyết định không mở cho `leader`).

## Implementation steps
1. Chạy `uv run pytest -q` toàn bộ; sửa hết test đỏ (không bỏ qua test nào).
2. Viết 2 file test đối soát ở trên.
3. Chạy `./scripts/dev.sh`, chạy kịch bản Playwright, lưu ảnh.
4. Đi hết checklist "không mất chức năng", tick từng dòng.
5. Gọi agent `code-reviewer` (song song 2 góc: đúng/sai số liệu · hiệu năng+bảo mật).
6. `pnpm build` + `uv run pytest -q` lần cuối; commit theo Conventional Commits
   (feat/fix/docs tách riêng, **không** tham chiếu AI).
7. Cập nhật tài liệu + memory.
8. Deploy bằng skill `deploy`; sau deploy: kiểm 4 redirect trên prod, kiểm 1 đơn vị đối chiếu với
   Báo cáo tổng hợp, kiểm tài khoản `executive`.
9. **Hard refresh** khi kiểm trên prod (Ctrl+F5 không đủ — bài học `dev-workflow-preferences`).

## Todo
- [ ] `uv run pytest -q` toàn bộ xanh
- [ ] `test_unit_index_tree.py` (4 ca)
- [ ] `test_unit_index_reconcile.py` (4 đối soát)
- [ ] Ảnh Playwright 6 tab + 7 kịch bản
- [ ] Checklist "không mất chức năng" tick đủ
- [ ] `code-reviewer` 2 góc, sửa hết phát hiện
- [ ] Sổ tay `docs/huong-dan/` (chỉ dạy dùng)
- [ ] Changelog + roadmap + memory
- [ ] Deploy + kiểm hậu-deploy (4 redirect · đối soát 1 đơn vị · executive)

## Success criteria
- Toàn bộ test backend xanh, **không** test nào bị skip/xoá để qua build.
- Checklist "không mất chức năng" tick 100%.
- Đối soát: Tổng quan ↔ tab gốc ↔ Báo cáo tổng hợp ra **cùng con số**.
- 4 đường dẫn cũ hoạt động trên **prod**.
- Sổ tay có ảnh, người dùng đọc là làm được, không lẫn nội dung kỹ thuật.
- Không có dữ liệu nào bị sửa/xoá trong cả tính năng này (màn chỉ đọc).

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Phát hiện lệch số sau khi đã xoá màn cũ | Đối soát ở bước 2 **trước** khi deploy; nhánh git riêng để quay lại |
| Test ghi rác vào DB dev dùng chung | Dùng tiền tố `_zz_` cho đơn vị test như `test_unit_analytics.py` đang làm |
| Deploy nuốt việc dở của agent khác | Phase này làm một mình; `git add` theo đường dẫn cụ thể, **không** `git add -A` |
| Người dùng vẫn mở link cũ và thấy khác | Redirect + thông báo trong sổ tay + email nhắc (nếu Ban TTKD muốn) |

## Security
Rà lại trước khi deploy: mọi endpoint mới đều `require_cap("unit_daily")` mức Xem, **không**
`require_any_cap`; không endpoint nào nhận `companies` từ client làm phạm vi quyền; thao tác ghi
duy nhất (`mark-no-purchase`) vẫn `require_admin`.

## Câu hỏi treo (gửi chủ dự án)
1. **17 bản ghi năm 2025** — có trên prod không, và nếu có thì xử lý thế nào? (Kế hoạch **không**
   tự sửa dữ liệu; chờ quyết định.)
2. Lãnh đạo **đơn vị** (`leader`) có được xem màn này không? Kế hoạch đang để **không** (QĐ-5) —
   vì đây là bảng so sánh giữa các đơn vị. Nếu có, chỉ mở đơn vị mình + đơn vị đã sáp nhập vào,
   bỏ dòng khu vực và dòng Tập đoàn (+4h).
3. "Báo cáo tổng hợp" có cần lọc theo khu vực không? Kế hoạch đang **không** mở rộng
   `period-report` (QĐ-1). Nếu cần thì là việc riêng (+3h).
4. Ma trận "Theo dõi nộp báo cáo" (chế độ 2) có cần nút **xuất Excel** không? Màn cũ chưa có,
   kế hoạch đang theo YAGNI là không thêm.
5. Cột so sánh mặc định **bật** ở 5 tab, **tắt** ở tab Tổng quan (vì nặng) — có chấp nhận không?
