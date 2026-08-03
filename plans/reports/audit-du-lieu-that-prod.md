# Audit dữ liệu thật production — VRG (2026-07-23)

Phạm vi: DB prod (`bizino-vrg-z4vmdr-db-1`, qua SSH). CHỈ SELECT, không ghi. Đối chiếu code
`apps/api/app/core/db.py`, `market_meta.py`, `services/floor_repo.py`, `services/to_trinh.py`,
`scripts/import-history/*`.

Tổng quan nguồn trong `fact_price`: `tocom/shfe/sgx/lgm` (crawler tự động, sạch), `reuters`
(paste tay từ MarketScreener + import lịch sử từ Excel "Lưu"), `fx` (VCB/BNM/exchangerates),
`market` (payload `market_quote` ghi lại), `vrg` (giá thu mua mủ nước — độ chênh lệch, ÂM là
BÌNH THƯỜNG), `anrpc` (gần như bỏ, đúng theo quyết định đã biết).

---

## 1. Giá bất hợp lý (≤0, đột biến >20%, lệch bậc)

```sql
-- (a) giá <=0
SELECT source, grade, price_type, as_of, price, unit FROM fact_price WHERE price <= 0 ...;
-- (b) đột biến >20% so phiên liền trước cùng (source,grade,price_type)
WITH s AS (SELECT source,grade,price_type,as_of,price,
  lag(price) OVER (PARTITION BY source,grade,price_type ORDER BY as_of) prev,
  lag(as_of) OVER (...) prev_date FROM fact_price WHERE source NOT IN ('vrg'))
SELECT * FROM s WHERE abs((price-prev)/prev) > 0.20 ORDER BY abs(...) DESC;
```

**(a) giá ≤ 0**: 456 dòng dính, nhưng **100% thuộc `source='vrg'`** (price_type `purchase`/`region`).
🟢 **BÌNH THƯỜNG** — cột này lưu **chênh lệch giá thu mua mủ nước** (đồng/độ TSC) so với giá tham
chiếu, không phải giá tuyệt đối → âm là hợp lệ (min -33.5, max 605, đa số dòng dương). Đã kiểm tra
`vrg|Dầu Tiếng|purchase` quanh 2024-06-21: `-2.5 → 407 → 407 → 402...` — chỉ dòng đầu tiên (ngày
khởi tạo chuỗi) âm nhỏ, các ngày sau bình thường. Không có giá ≤0 ở bất kỳ nguồn sàn/FX/physical
nào khác.

**(b) đột biến >20%** — 9 dòng, đáng chú ý:

| Nguồn | Grade | Ngày | Giá trước→sau | % | Đánh giá |
|---|---|---|---|---|---|
| reuters | STR20 | 2024-06-04 | 1963(05-31) → **71** → 1937(06-06) | -96%/+2628% | 🔴 **LỖI DỮ LIỆU** — giá `71` USD/tấn phi lý cho STR20 (range thật ~1900-2000), kẹp giữa 2 giá trị bình thường. Nguồn từ import lịch sử (`import_physical_staff.py`, batch `ingested_at=2026-06-23`), đọc thẳng ô Excel `Giá các sàn...2021-2025.xlsx` sheet "Lưu" — rất có thể lỗi gõ/đọc ô nguồn (thiếu số, ví dụ nhầm "1971"→"71" hoặc ô Excel bị lỗi công thức). |
| lgm | SMRCV | 2024-11-19→20→21 | 261.9 → **363.2** → 261.9 | +38.7%/-27.9% | 🔴 **LỖI DỮ LIỆU** — hình chữ V hoàn hảo, giá 20/11 bất thường so với 2 ngày kẹp 2 bên giống hệt nhau (261.9). Nguồn từ crawler LGM (không phải import tay) — nghi crawler đọc nhầm 1 phiên. |
| reuters | RSS3/STR20/SIR20/Thai Latex Bulk & Drums | 2025-12-29 → 2026-04/05/06-2026 | +25%→+46% | 🟡 Không phải "đột biến 1 phiên" mà là **khoảng trống ~4-6 tháng** giữa batch import lịch sử (hết ở 2025-12-29) và batch crawler mới (bắt đầu ~2026-04/05) — xem mục 5. % lớn vì gộp nhiều tháng biến động thật, không phải lỗi 1 điểm. |

## 2. Lẫn đơn vị / currency trong cùng (source, grade)

```sql
SELECT source, grade, price_type, unit, currency, count(*), min(as_of), max(as_of)
FROM fact_price GROUP BY 1,2,3,4,5 ORDER BY 1,2,3;
```

🟢 **SẠCH** — mỗi tổ hợp `(source, grade, price_type)` hiện chỉ có **đúng 1** `(unit, currency)`
xuyên suốt toàn bộ lịch sử (kể cả `lgm|LATEX` = Sen/kg/MYR từ 2024-01-02 đến nay, `sgx` = US
cents/kg, `shfe` = CNY/tonne, `tocom` = JPY/kg) — không phát hiện dấu vết lẫn đơn vị cũ (US
cents/kg) còn sót trong DB hiện tại; các lần đổi đơn vị trong quá khứ (memory: MRB Latex, SGX
multi-contract) đã được migrate/ghi đè sạch, không còn tồn dư.

## 3. Tỷ giá (fx)

```sql
-- số chữ số thập phân theo pair
SELECT grade, CASE WHEN price=trunc(price) THEN 0 ELSE length(split_part(price::text,'.',2)) END dec,
       count(*) FROM fact_price WHERE source='fx' GROUP BY 1,2;
-- đứng im >=5 phiên liên tiếp / thay đổi >2%
```

- **Số lẻ không đồng nhất theo thời gian** (🟡 thẩm mỹ, không phải lỗi giá trị): `USD/CNY` dao động
  1-6 chữ số lẻ (2 dòng có 6 chữ số lẻ đúng ngày 2026-06-20/21: `6.784364`, `6.789004`), `USD/MYR`
  cùng 2 ngày đó cũng nhảy lên 6 chữ số lẻ (`4.133145`, `4.131165`) — dấu vết một nguồn/tính toán
  khác chen vào đúng 2 ngày này. `USD/THB` dao động 1-6 chữ số lẻ theo từng giai đoạn (nguồn đổi
  từ VCB-tham-chiếu sang exchangerates.host). `USD/VND` (grade cũ, đã thay bằng Mua/Bán) có 6 chữ
  số lẻ toàn bộ 13 dòng (`26184.788185`...) — rõ ràng tính bằng công thức chia (không phải số niêm
  yết VCB nguyên bản). `USD/JPY` phần lớn đã đúng 2 số lẻ theo quy ước 0.2.80, còn 8 dòng rải rác
  là số nguyên tròn (158, 157...) — có thể trùng hợp giá tròn thật, không phải lỗi làm tròn nhầm
  (giá trị vẫn hợp lý theo range JPY 143-168).
- **Đứng im ≥5 phiên liên tiếp**: **0 dòng** — 🟢 không có carry-forward trên FX.
- **Đổi >2%/phiên**: 18 dòng, toàn bộ đều nằm quanh khoảng trống cuối tuần/lễ (vd MYR
  27/01→31/01 +7.21% qua nghỉ Tết) — 🟢 biến động qua gap ngày nghỉ, không phải lỗi nhập.
- `USD/VND (Mua)`/`(Bán)` (26.070–26.510) hợp lý, spread mua/bán ổn định ~350-400đ — 🟢.

## 4. Carry-forward (giá đứng yên nhiều phiên liên tiếp)

```sql
-- chuỗi giá trị y hệt liên tiếp theo (source,grade,price_type), loại vrg/fx
```

Phát hiện đáng ngờ nhất:

- 🔴 **`reuters|SIR20|physical` = 1710 suốt 40 phiên (2025-08-14 → 2025-12-16)**, trong khi các
  grade khác cùng batch import (SMR20, RSS3, STR20...) đổi giá hằng ngày bình thường. Toàn bộ 40
  dòng có cùng `ingested_at` (batch import lịch sử một lần, không phải 40 lần nhập tay riêng) →
  không chứng minh được carry-forward xảy ra ở tầng import (script `import_physical_staff.py`
  không có logic fill-forward, chỉ đọc thẳng ô Excel) — **nghi vấn nằm ở file nguồn Excel "Lưu"**
  (chuyên viên có thể đã copy giá cũ khi SIR20 không có báo giá mới trong ~4 tháng). Cần đối chiếu
  lại bản Excel gốc.
- 🟢 Các chuỗi lặp 3-14 phiên còn lại (tocom TSR20, sgx RSS3, lgm LATEX, `market|*` giá niêm yết
  VRG...) đều **hợp lý**: `market_domestic_vrg`/`market_export_vrg` là giá niêm yết chính thức VRG,
  chỉ đổi khi có quyết định mới (đứng yên nhiều ngày là đúng bản chất); tocom/sgx settlement đứng
  1-2 tuần trùng giai đoạn thị trường ít biến động — biên độ nhỏ, không lặp hàng tháng như SIR20.

## 5. Lỗ hổng dữ liệu (90 ngày gần nhất, phiên T2-T6)

```sql
WITH cal AS (...T2-T6 trong 90 ngày...), active AS (SELECT DISTINCT source,grade,price_type ...)
SELECT ..., expected_weekdays - actual_rows AS missing FROM active CROSS JOIN cal LEFT JOIN fact_price ...
```

- 🔴 **`reuters` (paste tay)**: SIR20 thiếu 56/65 phiên, RSS3/STR20/Bulk thiếu 22/65, SMR20 thiếu
  14/65 — nguồn phụ thuộc thao tác dán text thủ công, hay bị bỏ quên (khớp với gap 4-6 tháng ở mục
  1).
- 🟡 `anrpc` gần như chết (63-64/65 thiếu) — đã biết, nguồn coi như ngừng dùng.
- 🟢 4 nguồn crawler tự động lõi (`tocom`, `sgx`, `shfe`, `lgm` các grade chính SMRCV/SMR20/LATEX)
  chỉ thiếu 2-9/65 phiên — khớp lịch nghỉ lễ khác nhau giữa Nhật/Trung/Malaysia và lịch VN, **healthy**.
- `fx` các cặp chính (JPY/MYR/CNY) chỉ thiếu 2-3/65 — 🟢. `USD/VND`, `USD/THB` thiếu nhiều hơn vì
  mới đổi/thêm gần đây (đã biết, không phải lỗi).

## 6. Trùng lặp / mồ côi

- `fact_price`: PK `(as_of, source, grade, price_type)` chặn trùng ở tầng DB — không cần kiểm.
- `unit_daily_report`, `market_demand`, `unit_stock_contract`, `unit_purchase_plan`: **JOIN với
  `member_unit`** → 🟢 **0 dòng mồ côi** (không có company nào ngoài danh sách `member_unit`). Lưu ý
  3/4 bảng này hiện **0 dòng dữ liệu thật** trong prod (`unit_daily_report`, `market_demand`,
  `unit_stock_contract` đều rỗng — tính năng đã deploy nhưng chưa được nhập liệu thật).
- `member_unit`: 61 đơn vị active, chỉ **14 đơn vị** có gán `region` (4 khu vực: Bình Dương/Bình
  Phước/Bình Thuận/Tây Ninh); 47 đơn vị active KHÔNG có `region` — phần lớn là đơn vị Tây Nguyên/
  Bắc/Trung Bộ/Lào/Campuchia (Kon Tum, Chư Prông, Điện Biên, Việt Lào, Bà Rịa-Kampongthom...) nên
  🟢 **có vẻ là THIẾT KẾ đúng** (chỉ 4 khu vực lõi được gom bản tin, các đơn vị khác chưa có khu
  vực tương ứng nên bị bỏ qua có chủ đích). 🟡 Tuy nhiên **cần chuyên viên VRG xác nhận thủ công**
  2 điểm gán `region='Bình Phước'` nhìn có vẻ lệch địa lý: `Bà Rịa` (thường thuộc Bà Rịa-Vũng Tàu)
  và `Tân Biên` (thường thuộc Tây Ninh) — tôi không có nguồn đối chiếu chính thức nên chỉ nêu nghi
  vấn, KHÔNG khẳng định sai.
  ```sql
  SELECT name, region FROM member_unit WHERE is_active AND region IS NOT NULL ORDER BY region, name;
  ```
- 🟡 **`vrg_floor_price` — cột `lan` (PK, số lần ban hành) KHÔNG khớp thứ tự thời gian**:
  ```sql
  SELECT lan, as_of, title, dispatch_no FROM vrg_floor_price WHERE lan BETWEEN 57 AND 62 ORDER BY lan;
  ```
  - `lan=57` và `lan=60` **không tồn tại** (bị bỏ trống trong chuỗi tăng dần 1..81, có thể do tạo
    rồi xoá bản nháp — không có audit log để xác nhận).
  - `lan=58` (as_of **2025-09-08**, dispatch `2390/CSVN-TTKD`, title "Lần thứ 20 năm 2025") có
    `as_of` **MUỘN HƠN** `lan=59` (as_of **2025-08-27**, dispatch `2293/CSVN-TTKD`, title "Lần thứ
    19 năm 2025") — tức "Lần 19" (dán nhãn `title` đúng) lại được gán `lan=59` **sau** "Lần 20"
    gán `lan=58`, ngược thứ tự thời gian thật lẫn số công văn (2293 < 2390). Rất giống việc chuyên
    viên nhập "Lần 20" trước rồi mới bổ sung "Lần 19" bị bỏ sót sau — hệ thống tự cấp `lan` theo
    `MAX(lan)+1` tại thời điểm tạo (`floor_repo.next_lan()`), không theo ngày `as_of`.
  - **Tác động thực tế: THẤP.** Đã đọc `to_trinh.py::build()` — số "lần thứ N năm YYYY" hiển thị
    trên **Tờ trình chính thức** được tính lại độc lập bằng
    `count(DISTINCT as_of) WHERE as_of BETWEEN 'YYYY-01-01' AND as_of` (đếm theo NGÀY, không dùng
    cột `lan` thô), và giao diện danh sách biểu giá ưu tiên hiển thị `title` (đã đúng) chứ không
    hiện số `lan` thô cho người dùng cuối. Vẫn nêu vì đây là bất thường dữ liệu thật, có thể ảnh
    hưởng nếu sau này có code khác giả định `lan` tăng đơn điệu theo ngày.

## 7. `fact_inventory` & `unit_daily_report`

- `unit_daily_report`: **0 dòng** trong prod → không có gì để kiểm (xem mục 6).
- `fact_inventory`: không có giá trị âm. 🟡 2 tuần có `ton_kho_hd` (đã ký HĐ chưa giao) **lớn hơn**
  `ton_kho` (tồn kho thành phẩm):
  ```sql
  SELECT as_of, ton_kho, ton_kho_hd, note FROM fact_inventory WHERE ton_kho_hd > ton_kho;
  ```
  `2026-06-05`: ton_kho=26.079, ton_kho_hd=27.211 (lệch +1.132 tấn) · `2026-06-12`: 25.569 vs
  25.644 (lệch +75 tấn). Đối chiếu 3 commit gần nhất trên branch (`2dbf197`, `af324ef`, `05974ca`
  — "signed-undelivered stock recorded outside inventory") cho thấy đội đã **biết và đang xử lý
  đúng bản chất nghiệp vụ này** (HĐ đã ký chưa giao có thể vượt tồn kho vật lý hiện có vì hàng sẽ
  được sản xuất bổ sung trước hạn giao) → 🟢 **không phải lỗi**, chỉ nêu để đối chiếu với các audit
  khác nếu cần. Không phát hiện biến động tồn kho >30%/tuần bất thường nào khác.

## 8. `meta_crawl_run`

```sql
SELECT status, count(*), min(started_at), max(started_at) FROM meta_crawl_run GROUP BY status;
```

- Bảng chỉ có dữ liệu từ **2026-06-30** (tính năng theo dõi crawl run còn mới, ~3 tuần) → 136 lần
  chạy, 128 `ok` / 8 `error`.
- 🟢 **8 lỗi đều từ `marketscreener`** (2026-06-30 → 2026-07-02): thiếu Playwright browser lần đầu
  cài, rồi bị Akamai/anti-bot chặn IP nhiều lần → khớp đúng quyết định đã biết "ANRPC+marketscreener
  removed" khỏi chu trình `all` (không còn lỗi nào sau 2026-07-02 vì đã bỏ nguồn này).
  Không có nguồn nào khác lỗi.
- 🟢 Không có lần nào `status='ok'` nhưng `rows=0` (không có "thành công giả").
- Tần suất chạy đều đặn (4-13 lần/ngày, chu kỳ ~5-6h), khoảng trống dài nhất giữa 2 lần chạy chỉ
  ~19.5h (đêm 2026-07-01→02, dịp đang debug marketscreener) — 🟢 healthy, không có ngày nào scan
  "im lặng" hoàn toàn.

---

## ĐỀ XUẤT SỬA DỮ LIỆU (CHƯA CHẠY — chờ duyệt)

```sql
-- 1) reuters STR20 71 (2024-06-04) — giá trị phi lý kẹp giữa 1963 và 1937.
--    ĐỀ XUẤT dùng nội suy tuyến tính ~1940 NHƯNG khuyến nghị đối chiếu ô gốc trong
--    "Giá các sàn OSE,SHFE,SGX,MRB năm 2021-2025.xlsx" (sheet "Lưu", ngày 4/6) trước khi sửa.
-- Ảnh hưởng dự kiến: 1 dòng.
UPDATE fact_price SET price = 1940
  WHERE source='reuters' AND grade='STR20' AND price_type='physical' AND as_of='2024-06-04';

-- 2) lgm SMRCV 363.2 (2024-11-20) — kẹp giữa 261.9 (19/11) và 261.9 (21/11).
--    ĐỀ XUẤT về ~262 (nội suy) NHƯNG khuyến nghị đối chiếu lại nguồn LGM gốc trước khi sửa.
-- Ảnh hưởng dự kiến: 1 dòng.
UPDATE fact_price SET price = 262.0
  WHERE source='lgm' AND grade='SMRCV' AND price_type='physical' AND as_of='2024-11-20';

-- 3) (cosmetic, rủi ro thấp) làm tròn 611 dòng reuters (RSS3/STR20/Thai Latex Bulk&Drums,
--    2024-12-06..2025-12-29) đang có nhiều số lẻ do công thức Excel, cho đồng nhất định dạng
--    với dữ liệu crawler mới (luôn số nguyên). KHÔNG đổi giá trị bản chất (chỉ làm tròn <1 đơn vị).
-- Ảnh hưởng dự kiến: 611 dòng.
UPDATE fact_price SET price = round(price::numeric, 0)
  WHERE source='reuters' AND price <> round(price::numeric, 0)
    AND as_of BETWEEN '2024-12-06' AND '2025-12-29';

-- 4) reuters SIR20 đứng yên 1710 suốt 2025-08-14→2025-12-16 (40 phiên) — CHƯA đề xuất sửa vì
--    không đủ căn cứ phân biệt "thị trường thực sự đứng giá" và "carry-forward từ Excel nguồn".
--    Cần chuyên viên đối chiếu Excel "Lưu" trước, sau đó mới quyết định sửa hay giữ.

-- 5) member_unit.region cho "Bà Rịa" và "Tân Biên" đang = 'Bình Phước' — CHƯA đề xuất sửa, cần
--    chuyên viên VRG xác nhận khu vực đúng trước (không có nguồn đối chiếu chính thức trong repo).

-- 6) vrg_floor_price.lan không khớp thời gian (lan 58/59 đảo, 57/60 thiếu) — CHƯA đề xuất sửa vì
--    tác động thực tế thấp (to_trinh.py tự tính lại số "lần" theo ngày, không dùng lan thô) và
--    sửa PK (lan,grade) có rủi ro (cần đổi theo đúng thứ tự, tránh vỡ liên kết nếu có nơi khác
--    tham chiếu lan trực tiếp qua URL /api/floor/{lan}).
```

## NGHI NGỜ LỖI CODE (để đối chiếu với audit khác)

1. **`scripts/import-history/import_physical_staff.py`** — đọc thẳng giá trị ô Excel không có
   bước sanity-check (range check, vd chặn giá physical <500 hoặc >5000 USD/tấn) trước khi
   `_lib.upsert()`. Đây là lý do giá `71` lọt vào DB mà không bị chặn. Gợi ý: thêm ngưỡng hợp lý
   (`_PLAUSIBLE_MAX`-style, xem `to_trinh.py:_usd_t` đã có cơ chế tương tự cho USD/T) vào chính
   script import và/hoặc vào endpoint ghi giá thủ công cho reuters.
2. **`services/floor_repo.py::next_lan()`** — `MAX(lan)+1` không gắn với `as_of`, nên nếu nhập
   liệu không theo đúng thứ tự thời gian (bổ sung "lần" bị bỏ sót sau), `lan` sẽ không còn phản
   ánh thứ tự ban hành thực tế (xem mục 6). Không gây lỗi hiển thị hiện tại (vì `to_trinh.py` tính
   lại độc lập từ `as_of`), nhưng nếu có code mới nào lỡ dùng `lan` để suy ra thứ tự ("lần trước" =
   `lan-1`) sẽ sai — xem `to_trinh.py:169` `"prev_lan": lan - 1` (ở đây `lan` là biến tính từ
   `lan_year`, KHÔNG phải cột `lan` của bảng, nên vẫn an toàn — nhưng tên biến trùng dễ gây nhầm
   lẫn khi bảo trì).
3. **FX crawler(s)** (`services/crawlers/crawlers/macro/fx.py`) — số chữ số thập phân không đồng
   nhất theo thời gian cho cùng 1 cặp (`USD/CNY`, `USD/MYR`, `USD/THB`, `USD/VND` cũ) gợi ý nhiều
   nguồn/nhánh code khác nhau ghi vào cùng 1 `grade` với độ chính xác khác nhau (ví dụ
   exchangerates.host trả nhiều số lẻ hơn VCB/BNM). Không sai giá trị nhưng nên chuẩn hoá làm tròn
   tại tầng ghi (giống đã làm cho `USD/JPY` ở bản 0.2.80) để nhất quán.

## Câu hỏi/việc chưa giải quyết

- Chưa xác nhận được **nguyên nhân gốc** của giá `71` (reuters STR20) và `363.2` (lgm SMRCV) —
  cần mở lại file Excel nguồn / log crawler gốc (không có trong DB) để biết đây là lỗi gõ ở nguồn
  hay lỗi trong quá trình đọc/convert.
- Chưa xác nhận **region** đúng của "Bà Rịa" và "Tân Biên" trong `member_unit` — cần người có
  domain knowledge VRG xác nhận.
- Chưa xác nhận **40 phiên SIR20=1710 liên tiếp** là thị trường đứng giá thật hay carry-forward từ
  Excel nguồn "Lưu" — cần đối chiếu file gốc.
- `unit_daily_report`, `market_demand`, `unit_stock_contract`, `unit_purchase_plan` hiện **0 dòng**
  trong prod — không phải bug nhưng đáng lưu ý nếu kỳ vọng đã có dữ liệu thật ở các tính năng này.
