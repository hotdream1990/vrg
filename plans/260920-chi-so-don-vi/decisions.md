# Quyết định kỹ thuật & lý do

## QĐ-1. Không mở rộng `/api/unit-daily/period-report`
Khoảng trống khảo sát nêu endpoint này chưa nhận `regions`/`group_by`
(`apps/api/app/routers/unit_daily.py:263`). **Không sửa** vì:
- Nó phục vụ màn "Báo cáo tổng hợp" — bám cứng mẫu Biểu (1)/(2) để in, đã chốt GIỮ RIÊNG (Đ8).
  Thêm trục nhóm vào đó là kéo một màn in-theo-mẫu sang làm việc của màn phân tích.
- Các service thống kê (`unit_report_{purchase,consumption,stock,status}`) **đã** nhận `regions`
  + `group_by` + `split_merged` — đúng thứ màn mới cần. Dùng lại là DRY, mở rộng thêm là trùng.

**Đổi lại**: bắt buộc test đối soát `Tổng quan` ↔ `Báo cáo tổng hợp` ra cùng con số cho cùng kỳ
(Phase 10). Nếu lệch là lỗi của màn mới, không phải "hai cách tính".

> Câu hỏi treo cho chủ dự án: nếu vẫn muốn Báo cáo tổng hợp lọc được theo khu vực thì đó là một
> việc riêng, ước lượng thêm ~3h.

## QĐ-2. Router riêng `routers/unit_index.py`
`unit_analytics.py` đã 264 dòng. Màn mới thêm ~6 endpoint (tree cho 5 tab + overview + excel).
Nhồi vào file cũ là vượt xa mốc 200 dòng. Router mới, prefix `/api/unit-daily/index`,
dùng chung `assert_range` / `_xlsx` bằng cách **import từ `unit_analytics`** (không copy).

## QĐ-3. Cây khu vực = gọi report 2 lần rồi khâu
`*_report(group_by="region")` và `*_report(group_by="company")` đã tính **đúng** bình quân gia
quyền và % tính-lại-từ-tổng ở từng mức. Khâu 2 kết quả theo `row.region` là xong — không viết lại
một dòng phép cộng nào, nên không có nguy cơ hai chỗ tính lệch nhau.

Giá phải trả: 2 lượt đọc dữ liệu / tab. **Ngưỡng chấp nhận: ≤ 2,5 s** cho kỳ 1 tháng, toàn bộ đơn vị.
Nếu vượt → phương án B (chỉ làm khi đo thấy chậm, YAGNI): thêm tham số `group_bys: tuple[str, ...]`
cho các hàm `*_report` để gom nhiều cách nhóm **trong một lượt đọc**, vì phần nặng là
`rows_mod.*_rows()` chứ không phải vòng gom ở Python.

## QĐ-4. Chuỗi drill đổi vì đã có cây
Cây đã hiện sẵn khu vực + đơn vị nên 2 lớp drill đầu của `use-drill.CHAINS` không còn việc.
Chuỗi mới cho màn này: `tree → day → (material | none | grade)`. Bấm vào dòng đơn vị = mở lớp NGÀY
của riêng đơn vị đó. Ô "Nhóm theo" vẫn giữ mọi lựa chọn cũ (ngày · chủng loại · loại HĐ · hình thức ·
loại mủ · chi tiết); chọn cách nhóm ngoài cây thì bảng rơi về `StatsTable` phẳng như hiện nay.

## QĐ-5. Lãnh đạo đơn vị (`leader`) CHƯA mở màn này
Chủ dự án chưa yêu cầu. Lãnh đạo đơn vị đã có "Cảnh báo bất thường" + các màn số liệu đơn vị mình.
Màn này là bảng **so sánh giữa các đơn vị** — mở cho lãnh đạo đơn vị là để họ đọc số của đơn vị bạn.

Nếu sau này chủ dự án yêu cầu, công thức đã có sẵn (làm theo `routers/member_anomalies.py`):
1. Router mới `routers/member_unit_index.py`, prefix `/api/member/unit-index`,
   `leader: dict = Depends(get_current_leader)`.
2. Phạm vi `units = member_unit_merge.expand(leader["member_units"]) or leader["member_units"]`,
   **ép ở server**, không tin `companies` client gửi.
3. Bỏ dòng TOÀN TẬP ĐOÀN và dòng khu vực (gộp nhiều đơn vị = lộ số đơn vị bạn), chỉ còn dòng đơn vị.
4. `get_unit_user` đã chặn ghi theo method HTTP — endpoint mới chỉ GET nên tự an toàn.
Ước lượng ~4h.

## QĐ-6. Lọc chủng loại trên tab không gắn chủng loại
Làm **mờ ô lọc (disabled) + ghi chú** thay vì ẩn: ẩn đi thì người dùng chuyển tab thấy ô biến mất,
tưởng mình chọn nhầm. Ghi chú đặt ngay dưới ô, nội dung nói rõ **vì sao** (nhóm chỉ tiêu này không
gắn chủng loại), không phải "không khả dụng".

Áp dụng:
| Tab | Lọc chủng loại |
|---|---|
| Tổng quan | **mờ** — gồm cả nhóm không gắn chủng loại |
| Thu mua | bật, **chỉ tác động phần thành phẩm**; ghi chú nói rõ mủ nước/chén/dây không có chủng loại |
| Tiêu thụ · Tồn kho · Hợp đồng | bật |
| Tuân thủ nhập liệu | **mờ** — đếm lượt nộp, không liên quan chủng loại |
