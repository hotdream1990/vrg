# Báo cáo: gói kỹ năng "Số liệu nội bộ Tập đoàn" (internal_tools.py)

## File
`/Volumes/Work/biz-project/VRG/apps/api/app/services/assistant_tools/internal_tools.py` (mới, 257 dòng).
KHÔNG sửa file nào khác. `ruff check` pass sạch. Cú pháp OK (`ast.parse`).

Vượt 200 dòng — lý do: 5 tool nghiệp vụ khác nhau + registry TOOLS với description dài (mô tả rõ
đơn vị tính cho LLM là bắt buộc theo `_common.py`). Đã tối đa hoá dùng lại helper của `_common`
(table/line/cols/dm/dmy/err/pct/days_ago/today) để không lặp code; không thấy phần nào tách được
thành module riêng mà không phá vỡ ràng buộc "chỉ 1 file mới".

## 5 tool đã viết

1. **`get_inventory_trend`** (`weeks`, mặc định 26) — chuyển nguyên logic từ `assistant_tools.py`
   cũ, chỉ đổi sang helper `_common`. Dùng `inventory_repo.series()`.
2. **`get_market_quote`** (`as_of` tuỳ chọn) — MỞ RỘNG so với bản cũ: bảng so sánh 4 nhóm giá theo
   chủng loại (Xuất khẩu VRG USD/tấn · Nội địa VRG đồng/tấn · Nội địa tư nhân đồng/tấn · Xuất khẩu
   hàng tư nhân đồng/tấn), thay vì chỉ `export_vrg`. Đơn vị nằm ngay trong nhãn cột.
3. **`get_raw_material_prices`** (`material`∈{latex,cup,lace}, `days`, `by`∈{overall,company}) —
   giá mủ nguyên liệu lớp `vrg` (chuyên viên chốt), dùng `price_repo.purchase_prices_in_range()`
   (đã tự loại giá 0 và không carry-forward theo ngày). `by=overall` → biểu đồ đường bình quân
   Tập đoàn; `by=company` → bảng bình quân kỳ + giá/ngày gần nhất theo từng đơn vị. Đơn vị tính lấy
   từ `market_meta.PURCHASE_PRICE_UNIT` (mủ nước = đồng/độ TSC; mủ chén/mủ dây = đồng/độ DRC).
4. **`get_latest_bulletin`** (`kind`∈{daily,weekly}) — CHỈ đọc nháp/báo cáo ĐÃ LƯU, không gọi lại
   crawler: daily dùng `bulletin_service.list_saved_drafts()` + `draft_repo.get_overrides()` (lấy
   đoạn `market_analysis` thật đã biên tập); weekly dùng `weekly_report_service.list_reports()` +
   `build_report()` (chỉ đọc DB, không crawl) lấy `narrative.conclusion`. Kèm bảng 5 bản gần nhất.
5. **`get_data_freshness`** (không tham số) — bảng "nhóm dữ liệu | ngày mới nhất | số ngày trễ" cho
   9 nhóm `fact_price` (5 sàn + fx + physical + mủ nguyên liệu 2 lớp) + `market_quote` +
   `fact_inventory`, cộng lần quét gần nhất từ `price_repo.recent_runs(1)`.

## Nghiệp vụ đã xử lý theo đúng luật bắt buộc
- Không carry-forward: mọi tool đọc thẳng bản ghi đúng ngày/kỳ, không đắp số ngày khác.
- Giá 0: `get_raw_material_prices` dựa trên `purchase_prices_in_range` (đã loại `price=0` = "không
  có giá" ở tầng repo) — không tự tính trung bình thêm lần nào ở tool.
- Giá sàn quốc tế: `get_data_freshness` chỉ báo NGÀY mới nhất, không đọc giá nên không đụng quy ước
  No Trading; `EXCH`/`is_no_trading` của `_common` sẵn có cho tool khác dùng nếu cần sau này.
- Mọi số kèm đơn vị: nhãn cột bảng ghép `(unit)`; `don_vi_tinh` là trường riêng trong summary khi
  chỉ có 1 đơn vị cho cả tool.

## Output thật đã chạy trên DB local (docker `vrg-caosu-db-1`, dữ liệu tới ~29/08/2026)
Script test (bắt buộc stub package `assistant_tools` trong `sys.modules` trước khi import — xem lý
do bên dưới) — kết quả rút gọn:

```
get_inventory_trend {} → {"tuan_gan_nhat": "2026-08-21", "ton_kho_tan": 45953.69, ...}
get_market_quote {} → as_of 2026-08-18, 6 grade, đủ 4 nhóm giá (LATEX/SVR10/SVR3L/CV50/CV60), RSS3 = null (không có phiếu)
get_raw_material_prices {} → latex/overall/30d: 8 ngày có dữ liệu, 532→527 đồng/độ TSC (-0.94%)
get_raw_material_prices {material: latex, by: company, days:30} → 8 đơn vị, vd Phước Hòa BQ 513/gần nhất 520 (21/08)
get_raw_material_prices {material: cup, days:60} → 17 ngày, 510→511 đồng/độ DRC (+0.2%)
get_raw_material_prices {material: lace, days:60} → {"error": "Không có giá thu mua mủ dây (lớp chuyên viên) trong 60 ngày qua."}
get_raw_material_prices {material: bogus} → {"error": "Chủng loại nguyên liệu 'bogus' không hợp lệ..."}
get_latest_bulletin {} (daily) → ngày 18/08/2026, trích đúng đoạn IV đã lưu (~800 ký tự)
get_latest_bulletin {kind: weekly} → Tuần 31/2026 (27-31/7/2026), trích đoạn conclusion thật
get_market_quote {as_of: 2026-08-11} → dữ liệu đúng phiếu ngày đó
get_market_quote {as_of: 1999-01-01} → {"error": "Không có phiếu báo giá mủ thị trường ngày 01/01/1999."}
get_data_freshness {} → OSE "chưa có dữ liệu" (thật — xem nghi vấn bên dưới); SHFE/SGX/TOCOM/LGM/FX trễ 14-15 ngày; Reuters trễ 21 ngày; mủ nguyên liệu chuyên viên trễ ít hơn
```
Không tool nào ném exception trên dữ liệu thật. `summary` luôn là dict; `artifact` (khi có) đúng
khuôn `{"type": "table"|"line", "title": ...}`.

## Chỗ còn nghi ngờ / cần người khác lưu ý
1. **`unit_tools.py` chưa tồn tại** khi tôi làm việc (đang được viết song song) → import package
   `app.services.assistant_tools` (chạy `__init__.py`) sẽ lỗi cho tới khi file đó có mặt. Test của
   tôi phải tự stub `sys.modules["app.services.assistant_tools"]` (bỏ qua `__init__.py` thật) rồi
   import thẳng `internal_tools` bằng `importlib`. **Không sửa `__init__.py`** — chỉ ghi chú lại đây
   để người ráp nối cuối cùng chạy lại `python -c "from app.services.assistant_tools import TOOLS"`
   sau khi `unit_tools.py` xong, xác nhận `internal_tools` nạp được qua đường chính thức.
2. **OSE "chưa có dữ liệu"** ở `get_data_freshness` — nghi là do dữ liệu clone local dùng `source`
   khác cho OSE (bản tin map `tocom→OSE`, xem `market_meta.WORLD_GRADE_MAP`), còn `fact_price` gốc
   lưu source=`tocom`. Tool của tôi group theo `source='ose'`/`'tocom'` như `_common.EXCH` định
   nghĩa (`{"ose":..., "tocom":...}` là 2 mã sàn KHÁC NHAU trong `fact_price`, không phải bí danh
   của nhau) — không rõ có crawler nào thực sự ghi `source='ose'` hay tên "OSE" chỉ tồn tại như
   nhãn hiển thị (map từ `tocom`) mà không có dòng `source='ose'` nào trong DB. Nếu đúng vậy thì
   nhóm "Sàn OSE (Nhật)" trong `get_data_freshness` sẽ LUÔN báo "chưa có dữ liệu" một cách sai lệch
   (số liệu OSE thật ra nằm ở `source='tocom'`, đã được nhóm "Sàn TOCOM (Nhật)" báo đúng — nghĩa là
   2 dòng OSE/TOCOM trong bảng của tôi có thể đang lặp lại info của cùng 1 nguồn dữ liệu dưới 2 tên).
   **Đề nghị người sau xác nhận**: `EXCH` trong `_common.py` (`{"ose": "OSE (Nhật)", "tocom": "TOCOM
   (Nhật)", ...}`) có phải đang liệt kê 5 mã CRAWLER riêng biệt hay có cặp trùng ý nghĩa — nếu trùng,
   nên sửa `_common.EXCH` (file dùng chung, ngoài phạm vi của tôi) để bỏ mã thừa, tránh các tool khác
   (`market_tools.py`) cũng bị nhầm tương tự.
3. **`get_latest_bulletin` không chạy `create_draft`/crawler** theo đúng yêu cầu đề bài (tránh gọi
   lại crawler tốn thời gian) — nghĩa là nếu bản tin mới nhất CHƯA từng bấm "Lưu" (chỉ xem preview)
   thì sẽ không xuất hiện trong `bulletin_draft`/`weekly_report` và tool sẽ báo "Chưa có bản tin nào
   được lưu" dù trang UI có thể đang hiển thị bản build-on-the-fly. Đây là đánh đổi có chủ đích
   (đúng theo yêu cầu "đừng bịa nội dung"), ghi lại để người dùng Trợ lý AI hiểu giới hạn này.
4. Không có gì cần sửa ở file ngoài phạm vi — mọi phụ thuộc (`price_repo`, `market_quote_repo`,
   `inventory_repo`, `bulletin_service`, `draft_repo`, `weekly_report_service`, `market_meta`,
   `_common`) đều dùng qua hàm public sẵn có, không cần đổi API của chúng.
