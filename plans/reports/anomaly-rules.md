# Báo cáo — 8 luật "Cảnh báo bất thường" (`app/services/anomaly_rules.py`)

File DUY NHẤT tạo: `apps/api/app/services/anomaly_rules.py` (426 dòng — vượt mốc 250 dòng khuyến
nghị; giải thích ở mục "Ghi chú" cuối báo cáo). Không sửa file nào khác. Export đúng 1 hàm
`scan(date_from, date_to, thresholds) -> {date_from, date_to, groups, summary}` theo hợp đồng có
sẵn ở `anomaly_types.py`.

## 1. 8 nhóm luật + cột

| key | Nhãn | Mức | Nguồn | Cột (`columns`) |
|---|---|---|---|---|
| `wrong_raw_price` | Giá mủ nguyên liệu sai đơn vị tính | HIGH | Nhóm B collect.sql | don_vi · loai_mu · gia_lon_nhat_dong_do (đồng/độ) · so_o_sai |
| `wrong_sale_price` | Giá bán sai đơn vị tính | HIGH | Nhóm C collect.sql | don_vi · so_dong · tu_ngay · den_ngay · gia_lon_nhat · loai_tien · thieu_ty_gia · ma_hop_dong |
| `revenue_outlier` | Doanh thu một ngày bất thường | HIGH | `unit_report_rows.consumption_rows` | ngay · tong_doanh_thu_ty_dong · don_vi (đóng góp lớn nhất) · doanh_thu_don_vi_ty_dong |
| `missing_merge_stock` | Đơn vị nhận chưa gộp tồn kho sau sáp nhập | HIGH | `member_unit.merged_into/merged_at` + `unit_daily_report` | don_vi (đơn vị nhận) · doi_tac_sap_nhap · ngay_sap_nhap · ton_truoc_gop_tan · ton_sau_gop_tan · hut_tan · hut_phan_tram |
| `not_submitted` | Chưa nộp / thiếu một phần | MEDIUM | Nhóm A collect.sql | don_vi · khu_vuc · bieu_thu_mua (X/Y ngày thiếu hoặc "Không áp dụng") · bieu_ton_kho |
| `missing_price` | Có thu mua nhưng thiếu đơn giá | MEDIUM | Nhóm D collect.sql | don_vi · ngay · loai_mu (danh sách) · san_luong_tan |
| `silent_unit` | Đơn vị ngừng nộp nhiều ngày | MEDIUM | tự viết (đọc chung dữ liệu với `not_submitted`) | don_vi · khu_vuc · ngay_nop_gan_nhat · so_ngay_ngung_nop |
| `plan_missing` | Kế hoạch năm khai thiếu | LOW | Nhóm G collect.sql | don_vi · khu_vuc · o_con_thieu (danh sách) · so_o_thieu |

Thứ tự trả về: HIGH → MEDIUM → LOW (đúng thứ tự bảng trên, `scan()` tự sắp lại theo `severity`
phòng khi ai đó thêm luật không đúng thứ tự khai báo).

## 2. Output THẬT trên DB local (01/01/2026 – 10/09/2026)

```
{"total": 153, "high": 6, "medium": 138, "low": 9, "units": 67}
  [high]   wrong_raw_price          0 dòng ·  0 đơn vị
  [high]   wrong_sale_price         1 dòng ·  1 đơn vị  — Cao su Hà Tĩnh, 3 dòng, 27/01–24/03/2026,
                                                           giá lớn nhất 50.750.000, VND, thiếu tỷ giá,
                                                           HĐ "01, 1812-02, 34"
  [high]   revenue_outlier          3 dòng ·  1 đơn vị  — 27/01 (2,59 triệu tỷ), 30/01 (9,51 triệu tỷ),
                                                           24/03 (12,68 triệu tỷ) đồng, đều do Hà Tĩnh
  [high]   missing_merge_stock      2 dòng ·  2 đơn vị  — Eah Leo hụt 392,0 tấn (21,3%) của Krông Buk;
                                                           Lộc Ninh hụt 10.694,7 tấn (81,9%) của Bình Long
  [medium] not_submitted           65 dòng · 65 đơn vị
  [medium] missing_price            8 dòng ·  6 đơn vị
  [medium] silent_unit             65 dòng · 65 đơn vị
  [low]    plan_missing             9 dòng ·  9 đơn vị
```

`wrong_sale_price` và `revenue_outlier` cùng chỉ ra MỘT lỗi thật đã biết trên hệ thống (Cao su Hà
Tĩnh, tháng 01–03/2026, đơn giá ~50,75 triệu đ/tấn thay vì ~50.750 đồng — lệch đúng 1.000 lần) —
hai luật độc lập cùng bắt được, đúng ý "cross-check" của màn cảnh báo.

## 3. Tự kiểm luật `missing_merge_stock`

4 cặp sáp nhập hiện có trên DB, so tồn kho (khối "chưa nhập kho" + "đã nhập kho") ngày gần nhất
TRƯỚC mốc của cả 2 đơn vị với ngày gần nhất TỪ mốc trở đi của đơn vị nhận:

| Cặp | Mốc | Trước gộp (kỳ vọng) | Sau gộp (thực tế) | Hụt | Kết luận |
|---|---|---|---|---|---|
| Krông Buk → **Eah Leo** | 01/08/2026 | 440,05 (Krông Buk 31/07) + 1.398,71 (Eah Leo 31/07) = 1.838,8 | 1.446,7 (Eah Leo 01/08) | **392,0 tấn (21,3%)** | **CÓ NÊU** — khớp đúng "~392 tấn" đề bài cho |
| Chư păh → **Chư prông** | 21/08/2026 | 862,55 + 422,03 = 1.284,6 | *(không có báo cáo nào của Chư prông từ 21/08 trở đi trong DB local)* | — | **KHÔNG NÊU** — đúng yêu cầu, nhưng vì THIẾU DỮ LIỆU sau mốc chứ không phải vì đã đo và thấy khớp (xem mục 5) |
| Bình Long → **Lộc Ninh** | 21/08/2026 | 10.691,88 + 2.368,07 = 13.060,0 | 2.365,2 (Lộc Ninh 21/08) | **10.694,7 tấn (81,9%)** | Nêu thêm — Bình Long còn tự nộp riêng số của mình (10.699,8 tấn ngày 21/08) sau khi đã bị sáp nhập, Lộc Ninh chưa gộp gì cả |
| Mang Yang → Chư sê | 24/07/2026 | — | — | — | Không xét: `merged_at` (24/07) nằm ngoài phạm vi kiểm tra vì Mang Yang không còn dữ liệu "trước mốc" (đơn vị vào hệ thống sau khi đã sáp nhập) |

Luật cho ra **đúng 2 tiêu chí bắt buộc của đề bài**: nêu Eah Leo (~392 tấn, khớp chính xác con số
đã cho), không nêu Chư prông. Phát hiện thêm ca Bình Long → Lộc Ninh (hụt gần như toàn bộ 10.700
tấn) — đáng chú ý vì đúng NGHĨA của luật: đơn vị nhận hoàn toàn chưa gộp số của đơn vị bị sáp nhập.

**Lưu ý quan trọng**: DB local hiện KHÔNG có báo cáo tồn kho nào (mọi đơn vị) sau **27/08/2026** —
xem mục 5. Vì vậy Chư prông "không bị nêu tên" ở đây là do luật đúng nguyên tắc "thiếu dữ liệu thì
không kết luận" (không dựng số ngày khác thay), CHỨ CHƯA PHẢI xác nhận lại được con số "1.284,6
khớp tuyệt đối" mà đề bài nói đã đo trên prod — prod có dữ liệu mới hơn local. Khi chạy lại `scan()`
trên **prod** (có báo cáo của Chư prông sau 21/08), luật sẽ tự tính ra và nếu đúng như đã đo thì
`gap_pct` sẽ ≤ 10% nên không xuất hiện trong nhóm — hành vi thiết kế đã sẵn sàng cho việc đó.

## 4. Đối chiếu với skill `bao-cao-nhap-lieu` (make-xlsx.py, cùng DB local, `--until 2026-09-10`)

Chạy: `uv run --directory apps/api --with openpyxl python .claude/skills/bao-cao-nhap-lieu/scripts/make-xlsx.py --days 49 --purchase-days 253 --until 2026-09-10 --out /tmp/chk --local`

- **Sheet "B · Sai đơn vị tính"** (không giới hạn kỳ, giống hệt luật của tôi): 0 dòng giá mủ
  nguyên liệu, 1 dòng giá bán — **Cao su Hà Tĩnh, 50.750.000, 3 ô, 27/01–24/03/2026, HĐ "01,
  1812-02, 34", VND** → **KHỚP TUYỆT ĐỐI** với `wrong_raw_price` (0 dòng) và `wrong_sale_price`
  (1 dòng, đúng từng số) của tôi.
- **Sheet "D · Thu mua theo tháng"** (`--purchase-days 253` = đúng kỳ 01/01–10/09/2026 của tôi):
  so số "Đã nộp" của 34 đơn vị có kế hoạch thu mua với `253 − thieu_thu_mua` tính từ nhóm
  `not_submitted` → **34/34 đơn vị khớp tuyệt đối** (vd Cao Su Bà Rịa: xlsx 231/253, tôi
  253−22=231). Bộ 31 đơn vị "không áp dụng" (không có kế hoạch thu mua) cũng khớp 100% — cùng
  dùng chung `unit_daily_repo.companies_with_purchase_plan`.
- **Sheet "A2 · Thiếu đơn giá"** (kỳ ngắn 24/07–10/09, 49 ngày) chỉ ra đúng 2 dòng, cả hai đều là
  dữ liệu test (`_zz_audit_don_vi_a`, `_zz_audit_don_vi_b`, ngày 29/08/2026) — **`missing_price`
  của tôi (kỳ dài hơn, 01/01–10/09) cũng ra đúng 2 dòng test NÀY, kèm 6 dòng thật khác nằm NGOÀI
  cửa sổ 49 ngày của skill** (28/02, 31/03 ×2, 28/04, 26/06, 13/07/2026 — tất cả trước 24/07) →
  khớp hoàn toàn phần giao nhau, phần lệch là do KỲ KHÁC NHAU (lý do hợp lệ theo đề bài).

Không đối chiếu Sheet A/C (nhóm A/E) vì hai sheet đó dùng kỳ 49 ngày trong khi `not_submitted`
dùng kỳ 253 ngày do lệnh kiểm thử yêu cầu (`scan('2026-01-01', ...)`) — số ngày thiếu vì thế
không thể so trực tiếp; đã đối chiếu gián tiếp qua sheet D (cùng kỳ 253 ngày) ở trên.

## 5. Lưu ý dữ liệu (KHÔNG phải lỗi của luật)

- **DB local không có báo cáo `unit_daily_report` nào sau 29/08/2026** (purchase) / **27/08/2026**
  (consumption) — mọi đơn vị active đều "im lặng" kể từ khoảng 20–22/08 trở đi trong dữ liệu local
  này. Vì vậy `not_submitted` (65/65 đơn vị) và `silent_unit` (65/65 đơn vị) gần như liệt kê TOÀN
  BỘ đơn vị — đây là tính chất của BẢN SAO local (rất có thể clone từ mốc cuối tháng 8), KHÔNG phải
  bằng chứng cả Tập đoàn ngừng nộp 3 tuần liền. Chạy `scan()` trên prod với dữ liệu tới hôm nay sẽ
  cho con số thực tế hơn nhiều so với 138 dòng MEDIUM ở đây.
- **2 đơn vị rác từ test** còn sót trong `member_unit` local: `_zz_ast` (is_active=true, tạo
  24/08/2026) và `_zz_xl_rt`, cộng 2 mã `_zz_audit_don_vi_a/b` xuất hiện trong `unit_daily_report`/
  `fact_price` — xuất phát từ `tests/test_support.py`, `test_auth.py`, `test_member_unit_rename.py`…
  chạy thẳng vào DB local thay vì DB test cô lập. Các luật của tôi KHÔNG lọc riêng theo tên (đúng
  nguyên tắc không hard-code danh sách loại trừ vào luật nghiệp vụ), nên chúng xuất hiện lẫn trong
  `not_submitted`/`silent_unit`/`plan_missing`/`missing_price` như một đơn vị bình thường — ngoài
  phạm vi file được giao (không sửa test/DB), chỉ ghi nhận ở đây để người khác dọn nếu cần.

## 6. Bẫy nghiệp vụ đã xử lý (theo đúng yêu cầu đề bài)

- **Giá bán đọc ở `sales_contract.lines`**, không đụng tới `unit_daily_report.sales/sales_own` đã
  chết (bẫy 21/08/2026).
- **4 loại tiền quy đổi bằng tỷ giá của chính dòng** trước khi so ngưỡng triệu đ/tấn; KHÔNG áp
  ngưỡng USD cho LAK/KHR (bẫy 07/09/2026, đã viết lại nguyên văn điều kiện `CASE` của nhóm C).
  Loại tiền trống mới suy theo `member_unit.currency` (JOIN trực tiếp, không tự đoán khác đi).
- **Thu mua "không áp dụng"** dùng đúng `unit_daily_repo.companies_with_purchase_plan(year)` (đã
  đối chiếu khớp 34/34 + 31/31 ở mục 4) thay vì tự viết lại điều kiện "năm gần nhất ≤ năm nay".
- **"Đã nộp" = có ô số liệu thật** — dùng thẳng `unit_daily_fields.has_data(kind, fields)` cho cả
  `not_submitted` lẫn `silent_unit`, không đếm theo "có bản ghi".
- **Thiếu đơn giá bỏ qua ngày đã khai rõ "không có giá"** — dùng thẳng
  `unit_daily_fields.declared_no_price(fields)` (cờ `no_price_*` hoặc `price_*_local == 0`).
- **Kế hoạch năm: số 0 là ĐÃ khai, chỉ NULL mới tính thiếu** — so `IS NULL`, không so `<= 0`.
- **Sáp nhập**: không dựng số liệu ngày khác thay ngày thiếu — thiếu 1 trong 3 mốc (trước-nguồn,
  trước-đích, sau-đích) thì bỏ qua cặp đó, không đoán.
- **Doanh thu 4 loại tiền** dùng lại `unit_report_rows.consumption_rows` (qua `_delivery_rows`,
  đã xử lý đúng công thức `qty*price*TRIEU` cho VND và `qty*price*fx` cho ngoại tệ) thay vì viết
  lại công thức doanh thu lần 2 — tránh DRY violation và tránh lệch số với các màn khác.
- **Không ném exception**: mỗi luật bọc qua `_run()`; lỗi 1 luật trả nhóm rỗng kèm `desc` báo lỗi,
  đã kiểm bằng luật giả lập `RuntimeError` — `scan()` vẫn chạy đủ 8 nhóm còn lại.

## 7. Quyết định thiết kế cần lưu ý (cho phần router/frontend làm song song)

- `wrong_raw_price`/`wrong_sale_price` **KHÔNG giới hạn `date_from`** (đúng ý "lỗi còn tồn, sửa
  lúc nào cũng cần" của `collect.sql`), chỉ chặn trên bởi `date_to` (không tính lỗi có ngày tương
  lai). Nếu sau này muốn 2 luật này cũng tôn trọng `date_from` thì cần sửa 2 câu SQL tương ứng.
- `revenue_outlier` chọn "đơn vị đóng góp lớn nhất trong ngày" làm cột `don_vi` để admin có điểm
  bắt đầu điều tra — không có nghĩa CHỈ đơn vị đó sai (ngày bất thường có thể do nhiều dòng cộng
  lại), nhưng thực tế 100% ca đo được đều do đúng 1 dòng của 1 đơn vị.
- `missing_merge_stock` chỉ xét cặp có ĐỦ CẢ 3 mốc dữ liệu (trước-nguồn/trước-đích/sau-đích) — cặp
  Mang Yang→Chư sê (sáp nhập sớm nhất, 24/07) bị bỏ qua vì không có dữ liệu trước mốc đó.
  `MERGE_STOCK_GAP_PCT = 10%` cố định trong code (không đưa vào `anomaly_types.THRESHOLDS` vì đề
  bài không liệt kê nó là ngưỡng admin cấu hình được).
- `not_submitted`/`silent_unit` dùng CHUNG một lượt đọc DB (`_submission_days`) để không hỏi
  `unit_daily_report` hai lần cho cùng khoảng ngày — nếu router gọi `scan()` nhiều lần liên tục
  (vd polling) nên cache ở tầng router, module này không tự cache.
- Hiệu năng đo thật: **~0,37 giây** cho cả 8 luật trên kỳ 253 ngày, 69 đơn vị, ~10.800 bản ghi
  `unit_daily_report` + ~6.280 `sales_contract` — đủ nhanh để quét trực tiếp mỗi lần mở trang,
  không cần bảng lưu kết quả (đúng thiết kế đã chốt trong `anomaly_types.py`).

## 8. Ghi chú

- File 426 dòng — vượt khuyến nghị 250 dòng của tiêu chuẩn dự án. Không tách nhỏ được vì phạm vi
  công việc CHỈ cho tạo một file này (không được tạo module phụ); 8 luật độc lập, mỗi luật có SQL
  + comment giải thích bẫy nghiệp vụ bằng tiếng Việt nên khó nén hơn nữa mà vẫn giữ được lý do
  "vì sao" cho người đọc sau. Đã tách hàm nhỏ theo từng luật (`_wrong_raw_price`, `_wrong_sale_price`,
  `_revenue_outlier`, `_missing_merge_stock` + `_latest_stock`/`_stock_sum`, `_not_submitted`,
  `_missing_price`, `_silent_unit`, `_plan_missing`) — không gộp cục để giữ mỗi luật đọc độc lập.
- `ruff check` sạch.

## Nghi ngờ còn lại / câu hỏi mở

1. `missing_merge_stock` mới kiểm được 3/4 cặp sáp nhập trên DB local (thiếu dữ liệu Chư prông sau
   mốc, và Mang Yang→Chư sê thiếu cả trước lẫn sau). Cần chạy lại trên **prod** (dữ liệu mới hơn)
   để xác nhận đầy đủ cả 4 cặp trước khi bàn giao cho người dùng cuối.
2. `revenue_outlier` ngưỡng mặc định 5.000 tỷ đồng/ngày (theo `THRESHOLDS`) — 3 ngày bắt được đều
   là hàng triệu tỷ (lệch quá xa ngưỡng, không phải ca biên) nên chưa có cơ sở để tinh chỉnh ngưỡng
   này thêm; giữ nguyên mặc định.
3. Router/frontend (đang làm song song) cần tự quyết định khoảng `date_from` mặc định truyền vào
   `scan()` — báo cáo này chỉ xác nhận hàm hoạt động đúng với TẤT CẢ mọi khoảng ngày hợp lệ, không
   tự ý hardcode "24/07" như skill gốc (vì đề bài yêu cầu `scan(date_from, date_to, thresholds)`
   nhận tham số tường minh).
