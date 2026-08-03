# Audit lỗi thật — màn hình Nhập liệu / Sửa dữ liệu (apps/web)

Ngày: 2026-07-23 · Phạm vi: mọi màn nhập/sửa tay ở `apps/web/src/features/command-center` +
`apps/web/src/features/public/PublicPurchaseInputPage.tsx`. Chỉ đọc code — **không sửa gì**.
`tsc --noEmit`: 0 lỗi kiểu (không phải cùng loại lỗi audit này soi).

---

## 🔴 Nghiêm trọng

### 1. `NumInput` — nhập số thập phân bị nhân ~10 lần và MẤT phần lẻ
**File:** `apps/web/src/features/command-center/sections/NumInput.tsx:16-20,32-36`
```js
const fmt = (v) => (v != null ? v.toLocaleString("vi-VN") : "");
const parse = (s) => { const n = Number(s.replace(/[.,\s]/g, "")); ... };
<input value={fmt(value)} onChange={(e) => onChange(parse(e.target.value))} />
```
`parse()` xoá **cả `.` lẫn `,`** trước khi `Number()`. Vì input là **controlled** (value luôn bị ghi
đè lại bằng `fmt(value)` sau mỗi keystroke), bất kỳ dấu `,` hay `.` người dùng gõ để tách phần lẻ đều
bị `parse` nuốt mất ngay ở lần gõ đó (giá trị không đổi → React set lại `value` = chuỗi không có dấu
lẻ). Gõ tiếp chữ số sau đó sẽ bị nối thẳng vào phần nguyên → giá trị bị nhân lên (thường ×10) và mất
hẳn phần thập phân.

**Tái hiện:** ở "Giá sàn Tập đoàn" (VrgFloorPage) → tạo/sửa biểu giá → ô "Giá XK FOB/FCA (USD/T)" →
gõ `1234,5` (hoặc `1234.5`): gõ xong sẽ thấy ô hiện **`12345`** (hoặc client tự "nuốt" dấu phẩy khi
gõ tới), không phải `1234,5`. Nhấn "Lưu biểu giá" → **giá sàn chính thức bị lưu sai gấp ~10 lần**.

**Ảnh hưởng — mọi nơi dùng `NumInput`:**
- `VrgFloorPage.tsx:204,208` — Giá XK FOB/FCA (USD/T) & Giá nội địa (VNĐ/T) của **Giá sàn Tập đoàn**
  (văn bản chính thức gửi TGĐ/đơn vị) — USD/tấn theo ghi chú trong `PriceSheetGrid.tsx:140-141` vốn
  **có lẻ ,5** (nguồn gốc US cents/kg 2 số lẻ).
- `components/GradePriceTable.tsx:107-108` — đặc biệt Mục "3. Giá xuất khẩu — hàng VRG" (USD/tấn FOB,
  xem `MarketQuotePage.tsx:311`) rất hay có lẻ.
- `components/VcbRateBar.tsx:37-38` — tỷ giá VCB nhập tay khi API lỗi ("Không lấy được — nhập tay");
  backend parse tỷ giá VCB bằng `float()` (`apps/api/app/services/vcb_rate.py:23`) nên có lẻ.
- `components/ProposalTable.tsx`, `components/RegionLatexTable.tsx` — cùng lỗi cấu trúc (rủi ro thấp
  hơn vì đơn giá VNĐ nguyên thường không lẻ, nhưng bug vẫn tồn tại nếu có).
- Với `MarketQuotePage` (tự lưu sau 0.9s), giá trị sai có thể **tự động ghi xuống DB mà người dùng
  chưa kịp bấm gì** để xác nhận.

**Đề xuất:** đổi `NumInput` sang cùng cơ chế `formatter`/`parser` tách riêng nhóm-nghìn (`.`) và thập
phân (`,`) như `unit-daily-inputs.tsx:6-14` đã làm đúng (hoặc dùng thẳng antd `InputNumber` với
`formatter`/`parser` đó) — KHÔNG dùng 1 regex xoá chung cả 2 ký tự.

---

### 2. `EditableCell` — chỉ CLICK VÀO Ô rồi rời đi (không sửa gì) cũng làm hỏng số có phần lẻ
**File:** `apps/web/src/features/command-center/sections/EditableCell.tsx:40,61`
```js
onClick={() => { setEditing(true); setV(value != null ? String(value) : ""); }}   // dòng 61
...
const n = Number(raw.replace(/[.,\s]/g, ""));                                      // dòng 40
if (!isNaN(n) && n !== value) onSave(n);
```
Khi bấm vào ô để xem/sửa, ô nạp `String(value)` (vd `"1650.5"` — dấu CHẤM vì là `Number.toString()`
gốc JS, không qua `toLocaleString`). Khi rời ô (Enter/blur) **dù không đổi gì**, `commit()` xoá luôn
dấu chấm đó → `"1650.5"` → `"16505"` → `n = 16505 ≠ value(1650.5)` → **tự động gọi `onSave(16505)`**,
ghi đè số đúng bằng số sai gấp ~10 lần, dù người dùng không cố ý sửa.

**Tái hiện:** trang "Giá Physical" (`PhysicalSheetPage.tsx:131-132`, đơn vị USD/tấn — theo ghi chú
dùng chung `PriceSheetGrid.tsx:140-141` giá USD/tấn "có thể lẻ ,5") → bấm vào 1 ô đã có số lẻ (vd
`1650.5`) chỉ để xem → bấm ra ngoài (blur) → số bị lưu thành `16505`.

**Ảnh hưởng:** `PhysicalSheetPage.tsx:131` (USD/tấn — rủi ro cao, giá trị hay có lẻ ,5) và
`RawMaterialPage.tsx:134` (đồng/độ TSC — rủi ro thấp hơn vì VNĐ thường nguyên, nhưng cùng lỗi cấu
trúc nếu có số lẻ).

**Đề xuất:** bỏ hẳn regex xoá `.`/`,` khi parse chuỗi **raw** (không qua `toLocaleString`) — chỉ cần
`Number(raw)` trực tiếp (raw đã là dạng số JS chuẩn từ `String(value)`), không cần strip gì. Nếu cần
cho phép người dùng gõ dấu phẩy thập phân kiểu VN trong lúc sửa thì đổi `,` → `.` (không xoá `.`) rồi
mới `Number()`.

---

### 3. `MarketQuotePage` — chuyển sang phiếu khác trong lúc auto-save đang đếm giờ → mất số vừa gõ
**File:** `apps/web/src/features/command-center/pages/MarketQuotePage.tsx:84-104,114-148`
```js
useEffect(() => {
  if (!draft || !editable) return;
  ...
  timer.current = window.setTimeout(() => { ...saveQuote(...) }, 900);
  return () => { if (timer.current) clearTimeout(timer.current); };   // cleanup huỷ timer cũ
}, [draft, editable, loadList]);
```
`openDate`/`startAt` gọi `setDraft(...)` để mở phiếu khác. Effect re-run → cleanup của lần trước
**huỷ timer auto-save đang đếm cho phiếu ĐANG gõ dở**, rồi chạy lại effect cho `draft` mới — số vừa
gõ (chưa đủ 0.9s để tự lưu) **biến mất không cảnh báo**.

**Tái hiện:** mở "Báo giá mủ thị trường" → mở 1 phiếu ngày X → gõ 1 giá → trong vòng chưa tới 1 giây
bấm mở phiếu ngày Y khác (hoặc bấm "Tạo phiếu mới") → quay lại ngày X → số vừa gõ đã mất, không có
thông báo nào.

**Đề xuất:** trước khi đổi `draft` (openDate/startAt/remove), nếu đang có timer chờ lưu → flush lưu
ngay (gọi hàm lưu luôn thay vì chỉ `clearTimeout`) hoặc chặn chuyển phiếu kèm cảnh báo.

---

### 4. `UnitDailyEditModal` — đổi Ngày/Đơn vị khi form đang có sửa dở → mất trắng, không hỏi
**File:** `apps/web/src/features/command-center/pages/UnitDailyEditModal.tsx:51,108-112`
```jsx
useEffect(() => { if (open && day) load(day); }, [open, day, load]);   // dòng 51 — nạp lại ngay khi đổi ngày
...
<DateInput value={day} onChange={setDay} .../>                          // dòng 109 — không hỏi trước
<Select value={company} onChange={setCompany} .../>                     // dòng 110 — không hỏi trước
```
Modal nhập "Thu mua"/"Tiêu thụ–Tồn kho" theo dõi trạng thái `dirty` (qua `onDirty` callback, dùng để
enable nút "Lưu số liệu") nhưng **không dùng `dirty` để chặn khi đổi `day`/`company`**. Đổi ngày hay
đơn vị trong lúc đang nhập dở sẽ gọi `load()` nạp dữ liệu mới, và `formKey` đổi khiến
`PurchaseForm`/`ConsumptionForm` reset draft về dữ liệu đã lưu — **toàn bộ phần đang gõ mất trắng**.

**Tái hiện:** mở modal nhập "Báo cáo tiêu thụ - tồn kho" cho đơn vị A ngày 23/07 → gõ vài dòng tiêu
thụ → lỡ tay đổi ngày (DatePicker) hoặc đổi đơn vị (Select) để xem trước → toàn bộ dữ liệu vừa nhập
biến mất, modal không hỏi "có chắc không lưu?".

**Đề xuất:** trước khi `setDay`/`setCompany`, kiểm tra `dirty` (cần nâng state `dirty` lên component
modal thay vì chỉ giữ trong closure của `footer`) → `confirm()` xác nhận nếu có thay đổi chưa lưu.

---

## 🟡 Cao

### 5. `PriceSheetGrid` — gõ số kiểu "dấu chấm ngăn nghìn" (đúng như màn hình đang hiển thị) bị hiểu nhầm thành số thập phân
**File:** `apps/web/src/features/command-center/sections/PriceSheetGrid.tsx:75,81`
```js
onClick={() => { setEditing(id); setVal(raw != null ? String(raw) : ""); }}   // dòng 81
...
const n = Number(val.replace(/[,\s]/g, ""));                                   // dòng 75 — CHỈ xoá dấu phẩy, GIỮ dấu chấm
```
Ô đọc hiển thị số theo kiểu vi-VN (`fmt()` dùng `toLocaleString("vi-VN")` → dấu `.` ngăn nghìn, vd
`"14.523"`), nhưng khi bấm vào sửa, ô nạp `String(raw)` kiểu JS gốc (`"14523"`, không dấu chấm) và
`parse` chỉ xoá dấu phẩy — **giữ nguyên dấu chấm**. Nếu người dùng xoá trắng ô rồi gõ số MỚI theo
đúng quy ước đang thấy trên màn hình (`"14.523"` nghĩ là 14 nghìn 523), `Number("14.523")` = **14.523**
(chia cho ~1000 so với ý định).

**Tái hiện:** trang "Bảng tính giá các sàn" hoặc "Tỷ giá" (`FxRatePage.tsx`) → bấm 1 ô NATIVE/Tỷ giá
(cột hay hiện số ≥1000, có dấu chấm ngăn nghìn khi hiển thị, dec=3/4) → xoá trắng → gõ `14.523` (theo
thói quen nhìn thấy trên UI) → lưu → giá trị ghi vào `fact_price` là `14.523`, không phải `14523`.

**Đề xuất:** thống nhất 1 format cho cả hiển-thị-khi-đọc lẫn giá-trị-nạp-khi-sửa (nạp `fmt(raw)` thay
vì `String(raw)`, và `parse` xoá `.` + đổi `,`→`.`), tránh 2 quy ước số khác nhau cùng 1 ô.

### 6. Toàn bộ biểu "Thu mua" & "Tiêu thụ – Tồn kho" (Báo cáo tiêu thụ - tồn kho) KHÔNG có cảnh báo lệch ≥10%
**File:** `apps/web/src/features/command-center/pages/PurchaseForm.tsx`,
`ConsumptionForm.tsx`, `FinishedPurchaseTable.tsx`, `StockContractTable.tsx`,
`unit-daily-inputs.tsx` — không có file nào `import` `isBigChange`/`ChangeWarn`, hàm
`numInput()` (`unit-daily-inputs.tsx:29-45`) không nhận `prevValue`.

Đây là cụm màn hình nhập tay khối lượng lớn nhất (mọi đơn vị thành viên nhập MỖI NGÀY: sản lượng thu
mua, đơn giá, doanh thu tiêu thụ, tồn kho…) nhưng **không có** cơ chế cảnh báo lệch ≥10% so với kỳ
trước mà `MarketQuotePage`, `RawMaterialPage`, `InventoryPage`, `PriceSheetGrid`,
`PublicPurchaseInputPage` đều đã có. Nhập nhầm đơn giá thiếu/thừa 1 số 0 (vd `50` thay vì `500`) sẽ
không có bất kỳ tín hiệu cảnh báo nào trên các form này.

**Đề xuất:** thêm `prevValue` cho `numInput()` (hoặc bọc `ChangeWarn` quanh các ô Sản lượng/Đơn giá
chính: `latex_wet`, `coagulum`, `price_latex_vnd/local`, `price_cup_vnd/local`, giá bán từng dòng
`SaleLine.price`) — cần API trả về số liệu ngày liền trước để so sánh (tương tự
`buildGridPrevMap`/`fetchPrevStock` đã có cho khối Tồn kho).

---

## 🟢 Trung bình / thấp (đáng ghi nhận, chưa cấp thiết)

- **`StockContractTable.tsx:169-173`** — dòng chữ "tính tồn kho đến hết ngày …" tính bằng
  `new Date(r.delivered_date).getTime() - 86_400_000` rồi `.toLocaleDateString("vi-VN")`. Đúng với
  máy chạy múi giờ dương (VN, UTC+7) vì `new Date("YYYY-MM-DD")` được hiểu là UTC-midnight và hiển thị
  lại local dương sẽ không lùi ngày — nhưng nếu máy người dùng để múi giờ âm thì có thể lệch 1 ngày.
  Chỉ là **dòng chữ hiển thị** (không ghi xuống server) → CẦN KIỂM CHỨNG mức ảnh hưởng thực tế, không
  khẩn.
- **`FinishedPurchaseTable.tsx:41`, `ConsumptionForm.tsx:242` (`salesTable`)** — dùng `key={i}` (index)
  cho danh sách dòng có thể xoá giữa chừng. Mọi ô đều là **controlled component** (value lấy từ props)
  nên chưa thấy bằng chứng lẫn dữ liệu giữa các dòng, nhưng là code smell React kinh điển — có thể làm
  focus "nhảy" khi xoá dòng giữa danh sách. Nên đổi sang key ổn định (như `StockContractTable` đã làm
  với `_key` tăng dần).
- **`YearPlanPage.tsx:108-119`** — mỗi ô trong 1 hàng (Kế hoạch/HĐ dài hạn/…) gắn riêng
  `onBlur={() => canEdit && save(u)}` trên `<td>` cha (bubbling hoạt động vì React mô phỏng blur bằng
  focusout — không phải bug), nhưng Tab qua nhiều ô trong cùng 1 hàng sẽ gửi PUT **nguyên hàng** nhiều
  lần liên tiếp (idempotent, không sai dữ liệu, chỉ dư request). Có thể gộp thành 1 lần lưu khi rời cả
  hàng nếu muốn tối ưu — không khẩn.
- **`useEditorWindow()` (`apps/web/src/lib/edit-window.ts:33`)** — trước khi
  `/api/settings/edit-windows` tải xong, `isEditable()` trả `true` cho mọi ngày (fail-open, có ghi chú
  rõ trong code "backend vẫn là hàng rào thật"). Đã xác nhận backend có enforce riêng
  (`apps/api/app/core/edit_window.py` + `apps/api/tests/test_edit_window.py`) nên không phải lỗi bảo
  mật, chỉ là cửa sổ hẹp lúc trang vừa mở nút Lưu có thể tạm thời không khoá đúng — CẦN KIỂM CHỨNG có
  đáng sửa UI hay không (rủi ro thấp, backend chặn).
- **`PublicPurchaseInputPage.tsx:49,54`** và **`InventoryPage.tsx:37`** — cùng cấu trúc regex xoá cả
  `.`/`,` như NumInput/EditableCell, nhưng cả 2 nơi đều dùng `<input>` thô (state = chuỗi gõ tay, không
  tự format lại theo từng keystroke) và dữ liệu mục tiêu (đồng/độ TSC, tấn tồn kho) thường là số
  nguyên trong thực tế → rủi ro thấp hơn nhiều so với 2 lỗi 🔴 ở trên, nhưng cùng 1 lỗi cấu trúc nếu có
  ai nhập số lẻ. CẦN KIỂM CHỨNG số liệu thực tế có bao giờ lẻ không.

---

## ĐÃ KIỂM, KHÔNG CÓ LỖI

- **`apps/web/src/lib/date.ts`** — `isoDate()`/`todayISO()`/`daysAgoISO()` dùng
  `getFullYear/getMonth/getDate` theo giờ địa phương, có ghi chú rõ lý do KHÔNG dùng `toISOString()`
  (tránh lùi ngày sáng sớm ở VN, UTC+7). Đúng.
- **`apps/web/src/lib/edit-window.ts`** — `daysBetween()`/`shiftISO()` dùng `Date.UTC(...)` nhất quán ở
  cả 2 đầu phép trừ → không lệch múi giờ. `isEditable()`/`windowDates` logic đúng (admin luôn được
  sửa, ngày tương lai luôn khoá).
- **`apps/web/src/lib/permissions.ts`** — cơ chế 2 cấp Xem/Sửa (`hasCap`, `effectiveCaps`, `parseCap`)
  dùng bảng RANK so sánh rõ ràng, khớp mô tả trong comment và khớp memory dự án; không thấy lỗ hổng.
- **`unit-daily-inputs.tsx:6-14`** (`numInput`, dùng cho toàn bộ Thu mua/Tiêu thụ–Tồn kho/Kế hoạch
  năm/Hợp đồng tồn kho) — `groupInt`/`fmtInput`/`parseInput` tách riêng đúng nhóm-nghìn (`.`) và thập
  phân (`,`), dùng antd `InputNumber` (formatter/parser không tự đá cursor như input thô) → KHÔNG dính
  lỗi round-trip như `NumInput`/`EditableCell`. Đây là cách làm đúng, nên áp dụng lại cho 2 component
  kia (xem mục 🔴 #1, #2).
- **`PurchaseForm.tsx`/`ConsumptionForm.tsx`** — so sánh "dirty" và giá trị luôn qua `num()` +
  `?? null` tường minh (không dùng `||`) → phân biệt đúng `0` thật với "chưa nhập"; payload gửi lên
  cũng chỉ gồm field thực sự có trong draft, không tự chèn `0`.
- **`MarketQuotePage.tsx`** — cơ chế `editedR`/`editedRc` (chỉ đồng bộ xuống kho "Giá mủ nguyên liệu"
  đúng những ô user vừa sửa trong phiên, không đẩy cả snapshot cũ) chống carry-forward hiệu quả, khớp
  nguyên tắc "No cross-date data substitution" của dự án.
- **`UnitDailyEditModal.savePrices()`** — so sánh `(nv ?? null) === (ov ?? null)` trước khi gọi API,
  tránh gọi thừa/ghi đè không cần thiết.
- **`ReadOnlyNotice`/`canEditCap`** — mọi trang đã đọc đều bọc đúng `cap` tương ứng, khớp giữa
  banner/nút và điều kiện `readOnly` thực tế truyền vào ô nhập.
- **`tsc --noEmit`** chạy trên `apps/web` — 0 lỗi kiểu.

---

## Tóm tắt mức độ

| # | Mức | File | Tóm tắt |
|---|---|---|---|
| 1 | 🔴 | `sections/NumInput.tsx` | Nhập số lẻ → nhân ~10x, mất phần lẻ (Giá sàn Tập đoàn, tỷ giá VCB, giá SVR VRG XK…) |
| 2 | 🔴 | `sections/EditableCell.tsx` | Chỉ click-rồi-rời ô số lẻ cũng ghi đè sai ~10x (Giá Physical) |
| 3 | 🔴 | `pages/MarketQuotePage.tsx` | Đổi phiếu trong <0.9s sau khi gõ → auto-save timer bị huỷ, mất số |
| 4 | 🔴 | `pages/UnitDailyEditModal.tsx` | Đổi ngày/đơn vị khi đang nhập dở → mất trắng, không cảnh báo |
| 5 | 🟡 | `sections/PriceSheetGrid.tsx` | Gõ số kiểu có dấu chấm ngăn nghìn vào ô mới → hiểu nhầm thành thập phân |
| 6 | 🟡 | Thu mua / Tiêu thụ–Tồn kho (unit-daily-*) | Thiếu hoàn toàn cảnh báo lệch ≥10% |
| 7-10 | 🟢 | nhiều file | Xem chi tiết mục Trung bình/thấp |

## Câu hỏi chưa chắc (cần người biết nghiệp vụ/dữ liệu thật xác nhận)

1. Giá trị VND cho "đồng/độ TSC" (RawMaterialPage, giá mủ nước) trong thực tế có bao giờ lẻ (không
   phải số nguyên) không? Nếu KHÔNG thì lỗi #2 ở màn này gần như không xảy ra trên thực tế (chỉ còn
   rủi ro ở Giá Physical).
2. Tỷ giá VCB (`mua_tm/mua_ck/ban`) người dùng có thực sự hay phải NHẬP TAY (API `fetchVcbRate` lỗi)
   không, hay hầu như luôn lấy tự động? Ảnh hưởng mức độ ưu tiên sửa lỗi #1 ở `VcbRateBar`.
3. Múi giờ hệ thống của máy người dùng cuối (đơn vị thành viên) có luôn là giờ VN không, hay có
   trường hợp máy để múi giờ khác (ảnh hưởng mục 🟢 về `StockContractTable`)?
