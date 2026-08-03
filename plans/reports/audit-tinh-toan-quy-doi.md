# Audit tính toán / quy đổi đơn vị / làm tròn — VRG

Ngày: 2026-07-23 · Phạm vi: convert.py dùng chung + các service tính giá/báo cáo (apps/api) + web
tự tính %/trung bình (apps/web). Không sửa code — chỉ báo cáo. Mọi ví dụ số dưới đây đã chạy tay
hoặc chạy live trên code thật (DB local `vrg_caosu`, `uv run python3 -c ...`).

## Tóm tắt mức độ nghiêm trọng

| # | Mức | File:dòng | Vấn đề |
|---|-----|-----------|--------|
| 1 | 🔴 | `apps/api/app/services/to_trinh.py:39-53,61-68` | Tờ trình: dòng MRE LATEX **luôn trống** — thiếu nhánh `Sen/kg` + thiếu `USD/MYR`/`USD/THB` trong `_fx_at` |
| 2 | 🔴 | `apps/api/app/services/price_board.py:26,35` | Bảng giá dashboard (`/api/prices/board`) ghép tỷ giá "mới nhất" **không cùng ngày** với giá gốc — chứng minh live: LATEX ngày 22/07 bị quy đổi bằng tỷ giá USD/MYR ngày 23/07 |
| 3 | 🟡 | `apps/api/app/services/to_trinh.py:44,46,49,52,73,92,113,114,118-120` | Tự chế lại quy đổi bằng `round()` (banker's rounding) thay vì `r0` dùng chung — tái phát đúng lỗi MRB SMR20 đã từng vá ở `convert.py` |
| 4 | 🟡 | `apps/api/app/services/weekly_report_service.py:92-100,143-150,190-196,209` | Toàn bộ trung bình/đỉnh-đáy/Δ%/tỷ giá tuần dùng `round()` bản địa thay vì `r1`/`r2` dùng chung — chứng minh cụ thể bên dưới |
| 5 | 🟡 | `apps/api/app/services/floor_suggest.py:135` + `floor_recommend.py:31-33,46-47,62-65` | Engine "Gợi ý giá sàn" dùng `round()` bản địa cho dự báo/Δ/band thay vì `r0`/`r1` — điểm gốc rủi ro ở `_fit_at` khi mô hình dự báo ra đúng `x.5` |
| 6 | 🟡 | `apps/api/app/services/bulletin_service.py:302,320` | `%` thay đổi (Section I/II bản tin) tính trên giá **đã** làm tròn nguyên (`r0`) thay vì số gốc — cùng dạng lỗi vừa vá hôm nay ở market-movement (commit `33ef909`), biên độ ảnh hưởng nhỏ vì bản tin vốn in số nguyên |
| 7 | 🟡 | `apps/api/app/services/to_trinh.py:88-96` (`_physical`) | Bỏ qua cột `unit`, coi mọi giá reuters là USD/tấn sẵn — hiện AN TOÀN (reuters đã chuẩn hoá ở khâu nhập) nhưng giòn, không có lớp bảo vệ nếu tương lai nạp giá baht/kg |
| — | 🟢 | (xem mục "ĐÃ KIỂM, ĐÚNG") | convert.py, price_sheet.py, bulletin_service.py (khối quy đổi chính), unit-daily-consumption.ts, unit_period_report.py, market-movement (sau fix hôm nay) |

---

## 🔴 1. Tờ trình giá sàn — MRE LATEX luôn trống

**File:** `apps/api/app/services/to_trinh.py`
- `_fx_at()` (dòng 61-68) chỉ lấy 2 cặp tỷ giá: `("USD/CNY", "USD/JPY")` — **không có `USD/MYR`, không có `USD/THB`**.
- `_usd_t()` (dòng 39-53) chỉ xử lý 4 nhánh unit: `US cents/kg`, `USD/tonne`, `CNY/tonne`, `JPY/kg`. **Không có nhánh `Sen/kg`** (đơn vị gốc của LGM Latex — xem `lgm.py:42`: `unit = "Sen/kg"`).
- Hệ quả: với `SETTLE` có `("lgm", "LATEX", "MRE", "LATEX")` (dòng 24), mọi giá LATEX luôn rơi vào `else` ngầm của `_usd_t` (không nhánh nào khớp) → trả `None`.

**Bằng chứng chạy live trên DB thật** (`to_trinh.build('2026-07-22')`):
```
{'san': 'MRE', 'grade': 'SMRCV', 'prev': 3052, 'curr': 3048, ...}   # OK
{'san': 'MRE', 'grade': 'SMR20', 'prev': 2202, 'curr': 2240, ...}   # OK
{'san': 'MRE', 'grade': 'LATEX', 'prev': None, 'curr': None, 'd_abs': None, 'd_pct': None}  # LUÔN None
```
Mẫu chuẩn của Ban TTKD (`docs/ban hanh gia san/to-trinh-gia-san-mau.html:89`) lại kỳ vọng dòng
này có SỐ THẬT: `<td>LATEX</td><td>USD/T</td><td>1.924</td><td>1.934</td><td>+10</td><td>+0,5</td>`.

Số ĐÚNG lẽ ra phải hiện (tính tay theo công thức `convert.py`, dùng đúng ngày 21/07 vì 22/07 DB
không có `USD/MYR`): `722 Sen/kg × 10 ÷ 4.087 (USD/MYR 21/07) = 1766.83 → r0 = 1767 USD/T`. Hệ
thống hiện tại trả **None** ("—") thay vì 1767.

**Đề xuất:** thêm `"USD/MYR", "USD/THB"` vào vòng lặp `_fx_at`; thêm 2 nhánh `Sen/kg`/`baht/kg`
vào `_usd_t` — tốt nhất là **bỏ hẳn `_usd_t` tự chế**, gọi thẳng
`bulletin.convert.to_usd_tonne_detail()` (1 nguồn quy đổi dùng chung) như `price_sheet.py` /
`price_board.py` đã làm, để không lệch công thức và không lệch quy tắc làm tròn.

---

## 🔴 2. `price_board.py` ghép tỷ giá sai ngày (không phải "mới nhất" của cùng 1 ngày)

**File:** `apps/api/app/services/price_board.py:24-26,35`
```python
rows = price_repo.latest()                                             # mới nhất MỖI (source,grade)
fx_rates = {r["grade"]: float(r["price"]) for r in rows if r["source"] == "fx"}  # mới nhất MỖI cặp FX
...
usd, fx_pair, fx_rate = to_usd_tonne_detail(float(r["price"]), r["unit"], fx_rates)
```
`price_repo.latest()` trả **bản ghi mới nhất riêng của từng (source, grade)** — giá sàn và tỷ giá
được lấy "mới nhất" ĐỘC LẬP, không ép cùng `as_of`. Đây khác hẳn `price_sheet.py`/`bulletin_service.py`,
cả hai đều tra tỷ giá ĐÚNG NGÀY của giá gốc và để trống nếu thiếu (đúng luật dự án — "không carry
forward"). `price_board.py` không có bước ràng buộc ngày này.

**Bằng chứng chạy live** (DB thật, hôm nay 23/07/2026):
```
DB: fact_price(lgm, LATEX)   as_of mới nhất = 2026-07-22, price=722 Sen/kg
DB: fact_price(fx, USD/MYR)  as_of mới nhất = 2026-07-23, price=4.084   (KHÔNG có bản ghi 22/07)

price_board.build_board() → {'exchange': 'MRE', 'grade': 'LATEX', 'as_of': '2026-07-22',
                              'fx_pair': 'USD/MYR', 'fx_rate': 4.084, 'usd_tonne': 1767.9}
```
Giá LATEX **của ngày 22/07** bị quy đổi bằng tỷ giá USD/MYR **của ngày 23/07** (ngày SAU, không
phải carry-forward mà còn "carry-backward" từ tương lai) — vì 22/07 không có bản ghi USD/MYR.
Theo đúng luật dự án ("tỷ giá phải lấy ĐÚNG NGÀY của giá; thiếu → để trống, KHÔNG đoán bừa"),
ô USD/tấn của LATEX lẽ ra phải là **None**, không phải 1767,9 (con số tính từ tỷ giá sai ngày).
Sai lệch cụ thể ở đây nhỏ (4.084 vs 4.087 của 21/07 → ~0,07%) nhưng cơ chế là SAI NGUYÊN TẮC và
không tự giới hạn — khoảng cách ngày giữa giá và tỷ giá có thể lớn hơn tuỳ dữ liệu thiếu bao lâu.
Đây là dashboard người dùng nhìn trực tiếp (`ExchangeBoard.tsx`).

**Đề xuất:** đổi `build_board()` sang mô hình như `price_sheet.py` — với mỗi dòng giá, tra tỷ giá
theo đúng `r["as_of"]` của chính dòng đó (không phải tỷ giá "mới nhất" toàn cục); thiếu đúng ngày
→ `usd_tonne=None` + vẫn trả `fx_pair` để UI báo rõ (đúng pattern `to_usd_tonne_detail` đã hỗ trợ
sẵn qua tham số `fx_rates` — chỉ cần truyền đúng set tỷ giá của ngày đó thay vì set "mới nhất").

---

## 🟡 3. `to_trinh.py` tự chế lại `round()` (banker's rounding) thay vì `r0`

Cùng file/nguyên nhân với mục 1. Toàn bộ `_usd_t`, `_row`, `_physical`, `_proposal` dùng
`round()` builtin thay vì `r0`/`r1` từ `bulletin/convert.py` — đúng loại lỗi mà `convert.py` và
`test_price_convert.py` đã ghi nhận rõ ("MRB SMR20 223,85 → 2238,5 bị hạ thành 2238").

**Chứng minh số cụ thể** (chạy tay):
```python
>>> round(2238.5)      # Python round-half-to-even
2238                    # SAI theo quy ước dự án
>>> r0(2238.5)          # bulletin.convert.r0 (Decimal ROUND_HALF_UP)
2239                    # ĐÚNG
```
Nếu 1 grade MRE settlement nào đó (SMRCV/SMR20, cùng dùng US cents/kg) có giá gốc kết thúc bằng
`,X5` — đúng dạng nguồn LGM hay yết (2 số lẻ) — `_usd_t()` ở dòng 44 (`round(price * 10)`) sẽ hạ
sai xuống dưới giống hệt ca lỗi gốc, dù `convert.py` đã vá xong chỗ khác.

`_proposal()` (dòng 113,119) cũng dùng `round(raw / 50000) * 50000` để làm tròn VNĐ về bội số
50.000đ — cùng rủi ro half-to-even khi `raw/50000` rơi đúng `x.5`.

**Đề xuất:** import `r0` từ `bulletin.convert` (file đã import `floor_suggest`, thêm 1 dòng import
là đủ) và thay toàn bộ `round()` liên quan tới giá/tỷ giá bằng `r0`.

---

## 🟡 4. `weekly_report_service.py` — trung bình tuần dùng `round()` bản địa

**File:** `apps/api/app/services/weekly_report_service.py:92-94` (`_avg`), `97-100` (`_row`),
`142-150` (`_core_range`), `190-196` (`hl`), `209` (fx trung bình).

Điểm TÍCH CỰC đã kiểm đúng: mẫu số của `_avg()` chỉ đếm các ngày CÓ số liệu (`[v for v in vals if
v is not None]`), không chia cho tổng số ngày trong tuần kể cả ngày trống — đúng yêu cầu rule 5.

Điểm SAI: `_avg()` gọi `round(statistics.mean(xs), 1)` — `round()` builtin, không phải `r1`.
Input của `_avg` là các giá trị `usd` đã ở dạng 1-số-lẻ (`r1`, từ `price_sheet.build_sheet`), nên
trung bình cộng của N giá trị dạng `x.x` HOÀN TOÀN có thể rơi đúng ranh giới `x.x5` khi làm tròn
về 1 số lẻ.

**Chứng minh số cụ thể** (4 phiên OSE·RSS3 giả định, đều hợp lệ vì `r1` luôn trả 1 số lẻ):
```python
vals = [2579.3, 2579.4, 2579.5, 2579.6]   # 4 giá USD/T/ngày, đã r1
mean = sum(vals) / 4  ==  2579.45          # đúng ranh giới làm tròn 1 số lẻ
round(2579.45, 1)  ==  2579.4              # Python (banker's) — SAI
r1(2579.45)        ==  2579.5              # ROUND_HALF_UP (quy ước dự án) — ĐÚNG
```
Chênh lệch 0,1 USD/T ở TB tuần trong "III.1 Sàn quốc tế" — không lớn, nhưng đây LÀ báo cáo tuần
chính thức (in PDF gửi khách), và bug tái diễn ở mọi chỗ khác trong file (đỉnh/đáy `hl()`, Δ%
`_row()`, TB tỷ giá `fx`) vì cùng dùng `round()` builtin, không có test khoá lại như `convert.py`
đã có (`test_price_convert.py`) — không tìm thấy test nào cho `weekly_report_service.py`.

**Đề xuất:** import `r1`/`r2` từ `bulletin.convert`, thay mọi `round(x, 1)`/`round(x, 2)` liên
quan giá/tỷ giá trong file này.

---

## 🟡 5. Engine "Gợi ý giá sàn" — cùng dạng round() bản địa, rủi ro thấp hơn nhưng có thể lật quyết định NÂNG/GIỮ/HẠ

**File:** `apps/api/app/services/floor_suggest.py:135`, `floor_recommend.py:31-33,46-47,62-65`.

`_fit_at()` (floor_suggest.py:135): `"pred": round(fm.predict(inter, beta, xt))` — đây là điểm
DUY NHẤT giá dự báo (`sug`) được sinh ra từ hồi quy (số thực liên tục) rồi làm tròn về số nguyên
bằng `round()` builtin thay vì `r0`. Vì `fm.predict()` trả số thực bất kỳ, xác suất rơi đúng
`x.5` thấp hơn ca "MRB cents×10" (vốn LUÔN cho `,X5` với giá 2 số lẻ) nhưng KHÔNG bằng 0.

Đã kiểm: hiện tại `vrg_floor_price.fob_usd` trong DB luôn là số nguyên (double precision nhưng
`.0`), nên `delta = round(sug - prev)` ở `floor_recommend.py:46` thực chất là no-op VÌ `sug` đã
là int từ bước trên — rủi ro tập trung hết ở `_fit_at` chứ không lặp lại ở `build_item`.

**Vì sao đáng lưu ý dù xác suất thấp:** `delta` này đi thẳng vào
`fm.decide_action(delta, band)` (dead-band NÂNG/GIỮ/HẠ). Nếu `delta` đúng bằng `band` (biên) và
bị làm tròn sai hướng do banker's-rounding, quyết định hiển thị cho lãnh đạo có thể lật từ "giữ"
sang "nâng"/"hạ" hoặc ngược lại — hệ quả nghiêm trọng hơn tỷ lệ xảy ra thấp. CẦN KIỂM CHỨNG thêm
bằng cách rà lịch sử `_fit_at` trên toàn bộ ngày ban hành xem có lần nào `fm.predict()` ra đúng
`x.5` hay không (chưa làm vì cần chạy backtest đầy đủ, ngoài phạm vi thời gian audit).

`floor_model.py` (`mae/mape/rmse/r2/hit`) cũng dùng `round()` builtin nhưng đây là **chỉ số đánh
giá mô hình** (không phải giá/tỷ giá theo đúng nghĩa quy tắc 2) — rủi ro thấp hơn, liệt vào
CẦN KIỂM CHỨNG chứ không xếp lỗi.

**Đề xuất:** đổi `round(fm.predict(...))` ở `floor_suggest.py:135` thành `r0(...)`; đổi các
`round()` còn lại trong `floor_recommend.py` sang `r0`/`r1` cho nhất quán (phòng ngừa, vì hiện dữ
liệu toàn số nguyên nên chưa gây sai số quan sát được).

---

## 🟡 6. `bulletin_service.py` — % thay đổi tính trên giá đã làm tròn nguyên

**File:** `apps/api/app/services/bulletin_service.py:299-302` (Section I — sàn thế giới),
`317-320` (Section II — physical).

```python
curr_int = _convert_to_usd_tonne(*wc, t_str) if wc else None   # đã r0 → int
prev_int = _convert_to_usd_tonne(*wp, world_prev_iso) if wp else None
chg = (curr_int - prev_int) if (curr_int and prev_int) else None
pct = round(chg / prev_int * 100, 1) if (chg is not None and prev_int) else None
```
`%` được tính trên `curr_int`/`prev_int` — hai số ĐÃ được `r0` về nguyên — chứ không phải trên
giá gốc trước khi làm tròn. Đây CHÍNH LÀ dạng lỗi vừa được vá hôm nay (23/07/2026, commit
`33ef909 fix(market-movement): serve fractional USD prices...`) cho `price_board`/market-movement,
với lý do nêu rõ trong commit: "giá bán MRB SMR20 2238,5 bị ép kiểu int → mất phần lẻ, gãy % so
sánh". `bulletin_service.py` (Section I/II của Bản tin ngày — tài liệu chính thức) vẫn còn cùng
mẫu hình, chỉ khác là ở đây **cố ý** in số nguyên theo mẫu Ban TTKD (comment dòng 245-247 giải
thích rõ).

**Đánh giá mức độ:** khác thực chất với ca market-movement (từng gây lỗi 500/mất dữ liệu hoàn
toàn) — ở đây USD/tấn ~2000-3000, sai số do làm tròn trước khi chia trần tối đa ±0,5 USD/T, tương
đương `%` lệch tối đa khoảng ±0,02 điểm phần trăm ở mức hiển thị 1 số lẻ — thường KHÔNG đổi số
hiển thị. Không phải lỗi cấp market-movement (không gây mất dữ liệu), nhưng vi phạm cùng nguyên
tắc "quy tắc 4" và đáng đồng bộ để nhất quán + phòng thủ chiều sâu.

**Đề xuất:** tính `pct` từ giá trị `float` CHƯA làm tròn (trước khi gọi `_convert_to_usd_tonne`
ép về `int`), giữ `curr_int`/`prev_int` chỉ để HIỂN THỊ, tương tự cách `market_movement`/`price_sheet`
đã làm (giữ `usd_tonne` ở dạng `float` 1 số lẻ xuyên suốt, chỉ làm tròn tại điểm hiển thị cuối).

---

## 🟡 7. `to_trinh.py` `_physical()` bỏ qua cột `unit`

**File:** `apps/api/app/services/to_trinh.py:88-96`
```python
def val(r, ref):
    return round(r[0]) if (r and (ref - r[2]).days <= _STALE_DAYS) else None
```
`r[0]` = `price`, lấy thẳng không qua bất kỳ quy đổi nào — ngầm coi mọi giá `reuters/physical` đã
là USD/tấn. Đã kiểm tra DB: **hiện tại đúng** — toàn bộ 6 grade `reuters/physical` (kể cả 2 dòng
Thai Latex, vốn thường yết baht/kg ở nguồn gốc) đều được chuẩn hoá về `unit='USD/tonne'` NGAY khi
nhập (xem `reuters-physical-import` — parser tự quy đổi baht→USD trước khi lưu DB). Vì vậy hiện
KHÔNG có sai số quan sát được. Nhưng hàm này không tự bảo vệ — nếu tương lai có nguồn nhập thẳng
baht/kg vào `fact_price` (vd nhập tay nhầm đơn vị), `_physical()` sẽ cộng nhầm baht coi như USD mà
không cảnh báo. `price_repo.physical_sheet()`/`_to_usd_tonne()` (dùng cho màn "Quản lý số liệu")
CÓ xử lý `baht/kg` đúng cách — nên có sự KHÔNG NHẤT QUÁN giữa 2 nơi đọc cùng 1 bảng.

**Đề xuất:** cho `_physical()` dùng lại `price_repo._to_usd_tonne` hoặc `bulletin.convert` thay vì
giả định đơn vị, để nếu có dữ liệu chưa chuẩn hoá thì tự quy đổi đúng thay vì cộng nhầm.

---

## ĐÃ KIỂM, ĐÚNG

- **`services/bulletin/bulletin/convert.py`** — `r0/r1/r2` dùng `Decimal(str(x)).quantize(...,
  ROUND_HALF_UP)` đúng chuẩn; công thức 5 loại quy đổi (CNY/tonne, JPY/kg, US cents/kg, US$/kg,
  Sen/kg, baht/kg) đối chiếu tay đều khớp; test `test_price_convert.py` khoá chặt ca MRB đã từng
  báo lỗi (9/9 test pass, chạy live).
- **`price_sheet.py`** (`build_sheet`) — tra tỷ giá ĐÚNG NGÀY (`fx_at`), không carry-forward,
  đúng luật dự án; dùng `to_usd_tonne_detail` chung, không tự chế công thức.
- **`bulletin_service.py`** khối quy đổi chính (`_convert_to_usd_tonne`, dòng 242-262) — dùng
  đúng `r0` + tra tỷ giá theo đúng ngày `as_of` của giá (biến `fx_by_day`), có comment giải thích
  rõ lý do không dùng `round()`. (Chỉ riêng phần `%` ở mục 6 trên là điểm cần sửa.)
- **`apps/web/src/lib/unit-daily-consumption.ts`** (`lineRevenueVnd`, `totals`, `toTyDong`) —
  đúng quy tắc 6: VND = `qty × price(triệu) × 1_000_000`; USD = `qty × price × fx` (thiếu fx →
  `null`, không đoán); giá bán bình quân = `revenueVnd / qty / TRIEU` (bình quân GIA QUYỀN qua
  tổng doanh thu, không phải trung bình cộng đơn giá dòng) — đúng.
- **`apps/api/app/services/unit_period_report.py`** — bình quân giá thu mua =
  `Σ(giá ngày×SL ngày) / Σ(SL ngày)` (`_purchase_rows`, dòng 64-82) — đúng bình quân gia quyền;
  "thời điểm" (tồn kho, lấy `_latest`) vs "cộng dồn" (sản lượng/doanh thu, lấy `_add`) tách bạch
  đúng theo mẫu; khối 3 (đã ký HĐ) không cộng/trừ vào tồn kho thành phẩm — đúng nguyên tắc mới
  (xem `docs` "signed-undelivered stock recorded outside inventory").
- **`floor-vs-market.ts` / `summary.ts` / `HeatmapAndVrg.tsx` / `KpiRow.tsx`** — sau commit
  `33ef909` (hôm nay), % đều tính trên giá trị `float` (1 số lẻ từ `r1`), không còn tính trên số
  nguyên đã ép kiểu — đã kiểm tra `test_price_board.py` (2/2 pass) khoá lại đúng ca half-unit.
- **`lgm.py`** (crawler) — lưu ĐÚNG giá gốc `Sen/kg` cho Latex, KHÔNG tự quy đổi sớm ở tầng
  crawler — tôn trọng nguyên tắc "1 nguồn quy đổi" (chỉ `convert.py` được quy đổi).
- **`price_repo._fx_rounded`** — chuẩn hoá `USD/JPY` về 2 số lẻ bằng `r2` (HALF_UP) tại MỌI
  đường ghi (crawler/backfill/sửa tay) — đúng, có test riêng.

## CẦN KIỂM CHỨNG (chưa đủ bằng chứng trong thời gian audit)

- `floor_suggest.py:135` (`round(fm.predict(...))`) có từng thực sự rơi đúng `x.5` trong lịch sử
  backtest chưa, và nếu có thì có từng LẬT quyết định NÂNG/GIỮ/HẠ ở ranh giới `band` không — cần
  chạy quét toàn bộ `fd` (ngày ban hành) qua `_fit_at` và kiểm `abs(pred - round(pred)) == 0.5`.
- `floor_model.py` (`mae/mape/rmse/r2`) dùng `round()` — có nơi nào hiển thị số này như căn cứ
  quyết định (không chỉ tham khảo) mà cần độ chính xác HALF_UP hay không.
- `assistant_tools.py` (ngoài danh sách file được giao nhưng cùng nhóm) — `round(price, 2)`,
  `change_pct` — chưa rà, nên audit riêng nếu chatbot AI được dùng để tư vấn quyết định giá.
- Mức độ ảnh hưởng thực tế của mục 2 (`price_board.py`) khi khoảng cách ngày giữa giá và tỷ giá
  lớn hơn (vd nghỉ lễ nhiều ngày liên tiếp ở 1 sàn) — chưa có ca thực tế nào bị lệch quá 1 ngày để
  đo biên độ tối đa.

## Đề xuất ưu tiên sửa

1. `price_board.py` — ràng buộc tỷ giá cùng ngày với giá gốc, thiếu → `None` (mục 2). **Ưu tiên
   cao nhất vì đang chạy sai NGAY BÂY GIỜ trên dashboard thật.**
2. `to_trinh.py` — bỏ `_usd_t`/`_fx_at` tự chế, gọi `bulletin.convert.to_usd_tonne_detail` (gộp
   mục 1 + 3), thêm test khoá ca MRE LATEX giống `test_price_convert.py`.
3. `weekly_report_service.py` — đổi `round()` → `r1`/`r2`, thêm test cho `_avg`/`_row`.
4. `bulletin_service.py` — tính `%` (dòng 302, 320) từ giá trị trước khi ép `int`.
5. `floor_recommend.py`/`floor_suggest.py` — đổi `round()` → `r0`/`r1` để phòng ngừa (rủi ro thấp
   hơn nhưng ảnh hưởng quyết định nếu trúng).

## Không tìm thấy

- Không phát hiện `round()`/lỗi làm tròn ảnh hưởng **giá sàn đã ban hành** lưu trong
  `vrg_floor_price` (số nguyên gốc, không qua các hàm bị nêu ở trên).
- Không phát hiện chỗ nào so sánh nhầm 2 kỳ hạn/2 grade khác nhau MÀ KHÔNG gắn nhãn rõ (fallback
  SMR20→SGX·TSR20 trong `floor-vs-market.ts` có gắn nhãn rõ ràng `marketLabel`, không phải lỗi
  ngầm).
- Không phát hiện vi phạm rule 6 (VND theo triệu đồng/tấn) ở `unit-daily-consumption.ts` /
  `unit_period_report.py` — công thức đúng, đã kiểm kỹ.
