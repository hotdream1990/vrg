# Review tách nhóm HĐNT — 01/10/2026 (code-reviewer)

Lõi đúng: 4 nhóm cộng = `qty` ở mọi đường; `to_deliver` khớp; Excel mẫu Ban TTKD gộp HĐNT đúng chỗ;
không vòng import; `_BLOCK3_SQL` alias `s` không phá `{scope}`.

| # | Mức | Phát hiện | Xử lý |
|---|---|---|---|
| 1 | Cao | Gỡ hồ sơ giữ loại "Phụ lục" → HĐ chuyến lặng lẽ thành "dài hạn" | Gỡ → loại về chưa khai; loại cũ ghi nhật ký |
| 2 | Trung | `master_id` dịch nhóm báo cáo nhưng vẫn coi là "sửa an toàn" sau chốt; gắn/gỡ & đổi HĐNT↔HĐDH bỏ qua hàng rào | `assert_regroup_fences` ở form HĐ, gắn/gỡ, lưu hồ sơ mẹ (chặn đơn vị, xét cả đợt giao) |
| 3 | Trung | Bảng khu vực: tooltip "Còn lại" sai, các cột không cộng ra "Còn phải giao" | Thêm `backlog_lt_remaining` + cột "HĐ dài hạn còn phải giao" |
| 4 | Thấp | Nhãn `lt_unlinked_undelivered` "chưa gắn hồ sơ HĐDH" sai nghĩa | "ngoài HĐDH có cam kết" (6 chỗ) |
| 5 | Thấp | Cột "Loại HĐ" chi tiết không tách được HĐNT/HĐDH | Thêm "Nhóm HĐ" (lịch sử đợt giao + 2 sheet Excel) |
| 6 | Thấp | Câu chữ lỗi thời ("nối hồ sơ không đổi số liệu"…) | Sửa 5 chỗ |
| 7 | Thấp | Subquery master_type trong `_BLOCK3_SQL` | Giữ (tra theo khoá chính, ~3k dòng) |
| 8 | Info | 13 HĐ chuyến gắn HĐDH chuyển sang nhóm dài hạn ngay khi deploy | Báo chủ dự án |
