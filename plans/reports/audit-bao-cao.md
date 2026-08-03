# Audit báo cáo & kết xuất VRG — 260723-2123

Phạm vi: Bản tin ngày · Báo cáo tuần · Báo cáo tiêu thụ-tồn kho ngày · Tờ trình giá sàn · Bản tin
biến động · Gợi ý giá sàn (bảng/kết quả). Đọc code thật + query DB local (`vrg_caosu`, chỉ SELECT)
+ đối chiếu 1 PDF mẫu thật (`Bản tin ngày 29-06-2026.pdf`) + mẫu Excel gốc Ban TTKD
(`Biểu mẫu-Báo cáo tuần-năm 2026 (new).xlsx`) + chạy `pytest` (83 passed).

## Bảng phát hiện

| # | Mức | File:dòng | Mô tả | Tình huống tái hiện | Đề xuất sửa |
|---|-----|-----------|-------|----------------------|-------------|
| 1 | 🔴 | `apps/api/app/services/to_trinh.py:56-58` (`_at`), `:77-96` (`_settlement`/`_physical`), `apps/api/app/services/to_trinh_html.py:84-90` | **Tờ trình giá sàn (gửi TGĐ duyệt) vi phạm nguyên tắc "không đắp dữ liệu ngày khác".** `_at()` lấy `as_of<=:d ORDER BY as_of DESC LIMIT 1` — không kiểm tra khớp ĐÚNG ngày. `t1`/`t2` (2 mốc so sánh) chỉ tính từ `price_type='settlement'` (tocom/shfe/sgx) — bỏ hoàn toàn lgm/MRE (lưu `price_type='physical'` trong DB, xem #2). Khi 1 sàn chưa có phiên đúng `t1`/`t2` (rất thường — SHFE/TOCOM/MRE lệch phiên với SGX gần như mỗi tuần), `_at()` âm thầm lấy giá phiên CŨ HƠN rồi gán nhãn cột "Giá (t1)"/"Giá (t2)" y như đúng ngày đó — không có cờ "N/A"/"No trading" như bảng vật chất. `_narrative()` dòng 138 còn SINH VĂN BẢN "đi ngang" (fabricated) cho các sàn không hề có phiên. Bảng vật chất (dòng 88-96) có chặn 45 ngày (`_STALE_DAYS`) nhưng TRONG 45 ngày đó vẫn đắp y hệt, không có ghi chú ngày thực. | `cd apps/api && DATABASE_URL=... uv run python -c "from app.services import to_trinh; d=to_trinh.build('2026-07-23'); print(d['t1'],d['t2']); [print(r) for r in d['settlement']]"` → t1=23/07, t2=22/07 nhưng OSE/SHANGHAI/MRE đều `prev==curr` (vd OSE 2579==2579, d_abs=0) vì TOCOM/SHFE/lgm mới nhất trong DB là 22/07 — bảng hiện "Giá (23/07/26)" = 2579 dù KHÔNG có phiên 23/07 nào cho TOCOM. Test lại với ngày lịch sử đã đóng cửa hẳn `to_trinh.build('2026-07-21')`: TOCOM cũng prev==curr=2598 (DB không có phiên TOCOM ngày 20 lẫn 21/07, số thực là của 17/07 — 4 ngày cũ) — không phải ca hiếm ngày "hôm nay chưa quét kịp", mà lặp lại thường xuyên. UI mặc định vào chế độ "custom" của Gợi ý giá sàn set `asOf = todayISO()` (`FloorSuggestPage.tsx:96`) — đúng kịch bản người dùng thật sẽ gặp khi lập tờ trình ngày hôm nay. | Áp lại đúng pattern đã làm tốt ở `bulletin_service.py` (`has_data_on_date`, không carry-forward, để trống + nhãn rõ khi thiếu): (a) tính exact-match riêng cho TỪNG sàn thay vì 1 cặp t1/t2 chung; (b) sàn không có đúng ngày → hiện "Chưa có dữ liệu"/"No trading" như bảng vật chất đang làm, KHÔNG dùng giá cũ với đổi=0; (c) nếu vẫn muốn cho phép carry-forward có kiểm soát, phải in kèm ngày thực tế của số liệu (như `floor-vs-market.ts` đã làm — xem mục Đã kiểm/đúng) thay vì chỉ in nhãn `{t1}`/`{t2}` cứng; (d) sửa `_narrative()` bỏ qua sàn có `curr` là carry-forward (không tự sinh "đi ngang"). |
| 2 | 🟡 | DB `fact_price` (nguồn `lgm`) — xem `apps/api/app/services/to_trinh.py:160-163` | Mọi bản ghi `source='lgm'` (MRB/MRE Malaysia — SMRCV/SMR20/LATEX) trong DB lưu `price_type='physical'`, KHÔNG PHẢI `'settlement'` (đã verify bằng SQL). Vì query chọn `t1`/`t2` chỉ lọc `price_type='settlement'`, MRE **không bao giờ** góp phần xác định "ngày nào có phiên" — luôn bị kéo theo cặp ngày do 3 sàn kia quyết định, càng dễ lệch ngày (xem #1). | `SELECT source,grade,price_type,max(as_of) FROM fact_price WHERE source='lgm' GROUP BY 1,2,3;` → toàn bộ `price_type='physical'`. So với `SELECT ... WHERE price_type='settlement'` không có dòng `lgm` nào. | Xác nhận với chuyên viên: giá LGM có đúng là "settlement" (giá đóng cửa/khớp lệnh) hay "physical" (giao ngay) về bản chất nghiệp vụ? Nếu là settlement thật thì sửa `price_type` khi ghi (crawler `lgm`) hoặc đưa `lgm` vào danh sách nguồn xác định t1/t2 ở `to_trinh.py`. |
| 3 | 🟡 CẦN KIỂM CHỨNG | `apps/api/app/services/unit_period_report.py:140-141` (comment + logic), `apps/api/app/services/unit_daily_fields.py:43-49`, mẫu gốc `docs/bieu-mau-bo-sung/Biểu mẫu-Báo cáo tuần-năm 2026 (new).xlsx` sheet "Biểu mẫu Tiêu thụ -Tồn kho" hàng 10, cột N | Code hiện tại (sửa sáng nay, commit `2dbf197`/`af324ef`/`05974ca`) coi khối 3 "Đã ký HĐ chưa giao" là số **NGOÀI** tồn kho thành phẩm — không cộng, không trừ. Nhưng file mẫu GỐC của Ban TTKD tự ghi công thức cột N ("Thành phẩm tồn kho chưa có hợp đồng") = **"N = L − M"** (L = cột "Tồn kho thành phẩm", M = cột "Trong đó, tồn kho thành phẩm đã có hợp đồng") — công thức trừ này CHỈ đúng khi M là TẬP CON của L (đã ký nằm TRONG tồn kho, không phải ngoài). Đây đúng là "cái bẫy" mà đề bài audit mô tả — nhưng bản thân file mẫu gốc lại đang mã hoá theo hướng ngược lại với quyết định code vừa chốt. | Mở `docs/bieu-mau-bo-sung/Biểu mẫu-Báo cáo tuần-năm 2026 (new).xlsx` → sheet 1 → hàng 10 (formula row): cột N = `"N= L - M"`. So với `unit_period_excel.py:58` hiện chỉ còn cột `stock_finished_hd` ghi chú "ngoài tồn kho", KHÔNG còn cột "N" (chưa có HĐ = tổng trừ đã ký) như mẫu gốc có. | Việc code vừa đổi (nằm ngoài, không trừ) là quyết định sản phẩm — nhưng vì mẫu gốc tự mâu thuẫn, **cần xác nhận lại với Ban TTKD 1 lần nữa bằng văn bản** trước khi gửi báo cáo chính thức đầu tiên theo cách hiểu mới, để tránh đảo ngược lại lần nữa. |
| 4 | 🟡 CẦN KIỂM CHỨNG | `apps/api/app/services/unit_period_report.py:94,106` (`pct_plan`), `apps/api/app/services/unit_period_excel.py:35`, `apps/web/src/features/command-center/pages/PeriodReportPage.tsx:63,88` (preset mặc định "Tuần này") | Mẫu gốc Ban TTKD ghi rõ cột "% Kế hoạch thực hiện thu mua" tính trên "**Lũy kế** sản lượng mủ thu mua" (cộng dồn từ đầu năm) so kế hoạch NĂM. Code hiện tính `pct_plan = tổng SL trong KỲ ĐANG CHỌN ÷ kế hoạch năm × 100` — đúng công thức nhưng "tổng SL" phụ thuộc khoảng ngày UI đang chọn. Preset MẶC ĐỊNH là "Tuần này" (`rangeOf`), không phải lũy kế từ đầu năm → cột "%KH" mặc định sẽ ra 1 con số rất nhỏ (vd ~2%/tuần) dễ bị đọc nhầm là "mới đạt 2% kế hoạch năm" thay vì đúng nghĩa "%KH của riêng tuần này". | Mở trang Báo cáo kỳ, để mặc định "Tuần này" → xem cột "% thực hiện kế hoạch": số hiển thị là %KH của TUẦN, không phải luỹ kế năm — nhãn cột không phân biệt 2 nghĩa này. | Đổi nhãn cột cho rõ ("% KH trong kỳ đã chọn") HOẶC mặc định preset "Năm nay" (đúng nghĩa lũy kế của mẫu gốc) khi mở trang lần đầu, hoặc thêm 1 dòng phụ hiển thị %KH lũy kế từ đầu năm cạnh %KH-trong-kỳ. |
| 5 | 🟢 THÔNG TIN | Mẫu gốc `Biểu mẫu-Báo cáo tuần-năm 2026 (new).xlsx` sheet "Biểu mẫu-Thu mua" hàng 8, cột C/D ghi "số thời điểm" dù tiêu đề cột là "...trong tuần" (thường hiểu = cộng dồn); cột I "Giá bán BQ lũy kế" ghi công thức "H=G/F" (lệch cột so với vị trí thật — nên là I=H/G). | Không phải lỗi code — có vẻ là lỗi/nhãn nội bộ của chính file mẫu gốc Ban TTKD (copy công thức từ cột khác). Code hiện tính đúng theo Ý NGHĨA tên cột (cộng dồn "trong tuần", giá BQ = doanh thu/sản lượng), không theo đúng chữ "thời điểm"/"H=G/F". | Không cần sửa code; nêu để nếu đối chiếu số với chuyên viên VRG mà họ dùng đúng công thức chữ trong file gốc thì biết đây là khác biệt đã biết, không phải bug ẩn. |

## ĐÃ KIỂM, ĐÚNG

- **Bản tin ngày** (`bulletin_service.py`) — đối chiếu trực tiếp với PDF mẫu thật
  `Bản tin ngày 29-06-2026.pdf` (pdfplumber): thứ tự 7 dòng Mục I (`CANON_WORLD`), 6 dòng Mục II
  (`CANON_PHYS`), 13-14 dòng Mục III.1 (`VRG_FLOOR_GRADES`), format số VN, nhãn sàn
  ("Sàn TOCOM (Nhật Bản)" = `EXCHANGE_NAMES["OSE"]`), format ngày 2 số lẻ năm ở bảng
  (`%d/%m/%y`) vs 4 số lẻ năm ở tiêu đề (`%d/%m/%Y`), câu văn Mục IV (bỏ qua "tăng/giảm" khi
  `change_abs in (None,0)`) — TẤT CẢ khớp đúng mẫu.
- **Bản tin ngày — chống đắp ngày**: `create_draft()` dùng đúng `has_data_on_date` (chỉ dựng khi
  CÓ giá thật đúng ngày), `phys_curr_iso`/`phys_prev_iso` tách riêng khỏi world dates, tỷ giá quy
  đổi lấy ĐÚNG ngày (`_fx_at`, không carry-forward) — implement đúng chuẩn "no cross-date
  substitution" đã đặt ra, và đây chính là pattern nên áp lại cho `to_trinh.py` (phát hiện #1).
- **`price_repo.py`** — mọi query tham số hoá (không có SQL injection), khoá upsert
  `(as_of, source, grade, price_type)` đúng thiết kế 0.2.29, fix làm tròn USD/JPY 2 số lẻ
  (`_fx_rounded`, commit `725c62b`) có test riêng và test pass.
- **`weekly_ai.py` / `market_movement_service.py`** — prompt chống bịa số rõ ràng: bắt buộc số
  "Cao nhất/Thấp nhất tuần" lấy đúng từ `weekly_stats()` tính từ data thật (không cho AI tự ước),
  cấm bịa vĩ mô không có trong nguồn.
- **`unit_period_report.py` — dòng Tổng cộng**: đơn vị chưa nộp số liệu vẫn xuất hiện trong danh
  sách (từ `member_unit_repo.list_units`) nhưng KHÔNG góp số 0 giả vào tổng (`_add()` bỏ qua giá
  trị None, `total` cộng dồn chỉ từ đơn vị có nhập) — không có nguy cơ cộng trùng do 1 tài khoản
  gán nhiều đơn vị vì khoá dữ liệu là `(as_of, company, kind)` theo TÊN ĐƠN VỊ, không theo account.
- **Chia cho 0**: `_ratio()` (unit_period_report.py) và mọi chỗ tính %/giá BQ đều guard
  `if not den` trước khi chia — không phát hiện `ZeroDivisionError` tiềm ẩn.
- **`floor-vs-market.ts`** (Bản tin biến động) — pattern ĐÚNG mẫu: lùi về phiên gần nhất có số khi
  phiên hiện tại chưa có, nhưng LUÔN trả kèm `asOf` (ngày thực) để UI hiển thị minh bạch, không
  bao giờ gán nhãn ngày hiện tại cho giá cũ — nên dùng làm mẫu sửa phát hiện #1.
- **Gom nhóm mủ nguyên liệu theo khu vực** (`bulletin_service.py:_regions_from_purchase`) — bỏ
  đúng đơn vị chưa gán khu vực, khu vực không có giá bị loại khỏi báo cáo, 1 đơn vị → hiện 1 số,
  nhiều đơn vị lệch giá → hiện khoảng min-max; khớp đúng PDF mẫu ("Khu vực Bình Dương: 550" vs
  "Khu vực Bình Phước: 538-585").
- **83/83 test pytest pass** (`cd apps/api && uv run pytest -q`), bao gồm test riêng cho
  `stock_finished` không cộng/không trừ khối 3 (khớp phát hiện #3 — code + test nhất quán, chỉ
  còn nghi vấn với mẫu gốc).
- Không phát hiện chỗ nào AI tự hiển thị số `0` thay cho "không có dữ liệu" ở Bản tin ngày/Bản tin
  tuần/Bản tin biến động; các module này đều có "N/A"/"—"/"Chưa có dữ liệu" rõ ràng.

## Ghi chú phạm vi chưa soát hết (do giới hạn thời gian)

- Chưa đọc toàn bộ `unit_daily_excel_io.py` phần `parse_upload()` (dòng 252-330, đọc/validate
  file Excel người dùng nộp) — chỉ đọc phần khai báo cột + phần ghi (`commit_rows`).
  **CẦN KIỂM CHỨNG** nếu cần soát kỹ hơn logic parse lỗi dòng.
- Chưa mở PDF mẫu thứ 2 trở đi để đối chiếu chéo nhiều ngày (chỉ đối chiếu 1 file
  `29-06-2026.pdf`) — đủ để xác nhận cấu trúc/nhãn nhưng chưa loại trừ khả năng có ngày cá biệt
  lệch khác.
- Chưa audit riêng `to_trinh.py::_proposal()` (khối 3 — giá đề xuất từ engine `floor_suggest`) về
  mặt số học ngoài các phát hiện đã nêu; đã đọc code nhưng chưa đối chiếu với 1 tờ trình thật đã
  ban hành để so số tuyệt đối.
