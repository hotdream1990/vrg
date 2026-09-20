---
title: "Màn Chỉ số đơn vị (gộp 4 màn thống kê thành 6 tab)"
description: "Một màn duy nhất xem chỉ số từng đơn vị thành viên, có dòng gom khu vực, cột so sánh kỳ, thay cho 4 màn thống kê rời."
status: pending
priority: P2
effort: 44h
branch: feature/master-contract
tags: [unit-analytics, region-rollup, merge-screens, excel, redirect]
created: 2026-09-20
---

# Chỉ số đơn vị — kế hoạch triển khai

Hiện phải mở 4–5 màn mới ghép được bức tranh một đơn vị, và không có dòng tổng theo khu vực.
Màn mới gom lại **một chỗ**: dòng = đơn vị, cột = chỉ số, cây 2 cấp TOÀN TẬP ĐOÀN → khu vực → đơn vị.

Route mới: `/chi-so-don-vi?tab=<slug>` · quyền `unit_daily` mức **Xem**.

## Quyết định đã chốt (không tự đổi)
| # | Nội dung |
|---|---|
| Đ1 | 6 tab: Tổng quan · Thu mua · Tiêu thụ · Tồn kho · Hợp đồng · Tuân thủ nhập liệu |
| Đ2 | Cây dòng 2 cấp; dòng khu vực mở/gập được, hiện số đơn vị |
| Đ3 | Kỳ + bộ lọc GIỮ NGUYÊN khi chuyển tab (lưu trong URL) |
| Đ4 | Tab Tồn kho đổi trục: ô "Chốt ngày" + cột "Ngày lấy số" + dải độ phủ (KHÔNG cộng dồn theo kỳ) |
| Đ5 | Chủng loại chỉ là BỘ LỌC; tab không gắn chủng loại thì ô lọc **mờ + có ghi chú** |
| Đ6 | Cột so sánh: kỳ liền trước **và** cùng kỳ năm trước + % chênh; cộng % thực hiện KH năm |
| Đ7 | Gộp hẳn 4 màn `/thong-ke/*` thành tab + redirect 4 đường dẫn cũ sang đúng tab |
| Đ8 | GIỮ RIÊNG: `/bao-cao-tong-hop` và `/chot-so-lieu` |

## Quyết định kỹ thuật (agent đề xuất — xem `decisions.md`)
- **Không đụng `/api/unit-daily/period-report`**: tab Tổng quan dựng từ các service thống kê (vốn đã
  nhận `regions`), không mở rộng màn Báo cáo tổng hợp. Bù lại phải có test đối soát 2 màn ra cùng số.
- **Router mới `routers/unit_index.py`** (`/api/unit-daily/index`), không phình `unit_analytics.py`.
- **Cây = gọi report 2 lần** (`group_by=region` + `group_by=company`) rồi khâu lại — không viết lại
  phép cộng/bình quân. Có ngưỡng đo hiệu năng + phương án gộp 1 lượt đọc nếu chậm (Phase 01).
- **Lãnh đạo đơn vị (`leader`) CHƯA mở** màn này (YAGNI) — công thức mở sẵn ở `decisions.md`.

## Luật gom khu vực (dễ sai nhất — bắt buộc ghi comment trong code)
1. **Cộng dồn**: sản lượng · doanh thu · kế hoạch · số đợt giao · số ngày.
2. **BQ gia quyền theo sản lượng**: giá mủ nước/chén/dây BQ, giá bán BQ. Trung bình cộng các đơn vị = SAI.
3. **Tính lại từ tổng**: `% KH = Σ thực hiện ÷ Σ kế hoạch`; `tỷ lệ nộp = Σ ngày đã nộp ÷ Σ ngày phải nộp`.
4. **Không gộp được thì ĐỂ TRỐNG** (vd "ngày lấy số tồn" — mỗi đơn vị một ngày).
5. **Ô trống ≠ 0** — không dựng số kỳ này bằng số kỳ khác (`no-cross-date-data-substitution`).
6. Đơn vị đã sáp nhập: mặc định gộp vào đơn vị hiện hành, có công tắc `split_merged`.

## Các phase
| # | Phase | Ước lượng | Phụ thuộc |
|---|---|---|---|
| 01 | [Khung màn · cây khu vực · luật gom](phase-01-khung-man-va-cay-khu-vuc.md) | 6h | — |
| 02 | [Tab Thu mua · Tiêu thụ](phase-02-tab-thu-mua-tieu-thu.md) | 5h | 01 |
| 03 | [Tab Tồn kho (trục ngày chốt)](phase-03-tab-ton-kho.md) | 3h | 01 |
| 04 | [Tab Hợp đồng](phase-04-tab-hop-dong.md) | 5h | 01 |
| 05 | [Tab Tuân thủ nhập liệu](phase-05-tab-tuan-thu-nhap-lieu.md) | 4h | 01 |
| 06 | [Cột so sánh kỳ](phase-06-cot-so-sanh-ky.md) | 5h | 02–05 |
| 07 | [Tab Tổng quan](phase-07-tab-tong-quan.md) | 4h | 02–05 |
| 08 | [Gộp màn cũ · redirect · menu](phase-08-gop-man-cu-va-redirect.md) | 3h | 02–05 |
| 09 | [Xuất Excel từng tab (+ sửa lỗi cột mủ dây)](phase-09-xuat-excel-tung-tab.md) | 4h | 02–05 |
| 10 | [Kiểm thử · sổ tay · deploy](phase-10-kiem-thu-va-tai-lieu.md) | 5h | 06–09 |

**Chạy song song được**: 02 · 03 · 04 · 05 (file không giao nhau) sau khi 01 xong.
Tiếp đó 06 · 07 · 08 · 09 chạy song song. 10 làm cuối, một mình.

## Rủi ro đầu bảng
1. **17 bản ghi `unit_daily_report` năm 2025** trên bản sao DB cục bộ (6 purchase · 11 consumption,
   rải rác 04/2025 → 31/12/2025) — nghi gõ nhầm năm. Nếu có thật trên prod, cột "cùng kỳ năm trước"
   sẽ hiện vài con số lẻ vô nghĩa. **Phải kiểm trên DB chạy thật trước, KHÔNG tự sửa dữ liệu** (Phase 06).
2. **Hiệu năng**: 6 tab × cây 2 cấp × 3 kỳ (hiện tại + 2 kỳ so sánh) = tới 6 lượt quét. Ngưỡng chốt
   ≤ 2,5 s mỗi tab ở kỳ 1 tháng. Bài học `anomaly` (JIT Postgres trên hypertable) áp dụng lại.
3. **Lệch số với màn cũ / Báo cáo tổng hợp** — khoá bằng test đối soát (Phase 10).
4. **Link đã gửi VRG chết** nếu redirect sai tab (Phase 08).

## Tài nguyên tái sử dụng (đừng dựng mới)
Backend `services/unit_report_{purchase,consumption,stock,status,query,rows}.py` ·
`unit_analytics_excel.py` · `member_unit_merge.py` · `member_region_repo.py` · `sales_contract_report.py`.
Frontend `pages/analytics/{StatsTable,AnalyticsFilters,use-stats,use-drill,DrillHeader,StockFilters,StockCoverageBar}.tsx` ·
`lib/{date-presets,unit-daily-fields,unit-analytics-client}.ts`.
