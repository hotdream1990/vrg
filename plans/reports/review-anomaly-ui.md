# Rà soát giao diện — trang "Cảnh báo bất thường"

Ngày rà: 11/09/2026 · Phạm vi: `/canh-bao-bat-thuong` (chỉ admin) · **Không sửa file nào.**

Nguồn đối chiếu: 3 ảnh chụp trong `plans/visuals/2026-09-11-canh-bao/`, mã nguồn
`apps/web/src/features/command-center/pages/AnomalyPage.tsx`, `apps/web/src/lib/anomaly-client.ts`,
`apps/api/app/services/anomaly_rules.py`, `anomaly_types.py`, `anomaly_export.py`,
`apps/api/app/routers/anomalies.py`.

> ⚠ **Lưu ý về ảnh**: `01-tong-quan.png` và `02-toan-trang.png` là **cùng một file** (md5 trùng
> `81433fd2…`). Nên tôi KHÔNG có ảnh toàn trang — phần dưới màn hình đầu tiên được suy ra từ mã
> nguồn (thứ tự nhóm, trạng thái bung/gấp, bảng) chứ không phải nhìn thấy. Nếu cần soát kỹ phần
> đuôi trang, chụp lại giúp ảnh full page.

---

## Tóm tắt trong 30 giây

Trang **đúng dữ liệu, đúng chuẩn dự án** (không emoji, hint đỏ, giao diện sáng, cột động theo
server — backend thêm luật là web hiện ngay). Nhưng ở **đúng trạng thái production hiện tại
(4/8 nhóm rỗng)** thì bố cục đang phản tác dụng: **3 nhóm RỖNG được bung sẵn ở đầu trang với thẻ
đỏ "Nghiêm trọng", còn 21 việc thật thì bị gấp lại ở dưới.** Admin mở trang, ba màn hình đầu toàn
chữ "Không có cảnh báo".

Sửa 2 chỗ (~25 dòng, chỉ frontend) là đảo ngược hoàn toàn ấn tượng đó. Chi tiết ở 🔴-1 và 🔴-2.

**Kết luận nhanh**: dùng được, nhưng nên làm xong nhóm 🔴 trước khi bàn giao chính thức cho Ban TTKD.

---

## 🔴 SỬA NGAY

### 🔴-1. Nhóm RỖNG chiếm chỗ đẹp nhất, việc thật bị gấp xuống dưới
`apps/web/src/features/command-center/pages/AnomalyPage.tsx:209`
`apps/api/app/services/anomaly_rules.py:416-427` (thứ tự `groups` + `sort` chỉ theo mức độ)

**Người dùng gặp gì.** Backend luôn trả **đủ 8 nhóm** kể cả nhóm 0 dòng, rồi sắp xếp **chỉ theo
mức độ** (`sev_rank`), sort ổn định nên giữ nguyên thứ tự khai báo. Frontend thì bung mặc định
**mọi nhóm `high`**, không phân biệt nhóm có dòng hay không:

```
setActiveKeys(r.groups.filter((g) => g.severity === "high").map((g) => g.key));
```

Với số liệu production hôm nay, trang xếp ra như sau:

| Thứ tự | Nhóm | Số dòng | Trạng thái mặc định |
|---|---|---|---|
| 1 | Giá mủ nguyên liệu sai đơn vị tính | **0** | 🔴 tag "Nghiêm trọng" · **BUNG** → "Không có cảnh báo." |
| 2 | Giá bán sai đơn vị tính | **0** | 🔴 tag "Nghiêm trọng" · **BUNG** → "Không có cảnh báo." |
| 3 | Doanh thu một ngày bất thường | **0** | 🔴 tag "Nghiêm trọng" · **BUNG** → "Không có cảnh báo." |
| 4 | Chưa gộp tồn kho sau sáp nhập | 1 | 🔴 · BUNG (đúng) |
| 5 | Chưa nộp / thiếu một phần | **14** | gấp — phải bấm mới thấy |
| 6 | Có thu mua nhưng thiếu đơn giá | **7** | gấp |
| 7 | Đơn vị ngừng nộp nhiều ngày | 0 | gấp |
| 8 | Kế hoạch năm khai thiếu | 3 | gấp |

Tức là: **ba màn hình đầu là ba thẻ đỏ "Nghiêm trọng" với 0 dòng**, và 21/25 việc thật nằm sau
những panel đóng. Nhìn 3 giây, admin đọc được thông điệp ngược: "đỏ lòm mà chẳng có gì để làm".

**Đề xuất (chỉ frontend, ~15 dòng, không đụng backend).**

1. Sắp lại: nhóm **có dòng** lên trên (trong khối đó vẫn theo mức độ), nhóm **rỗng** dồn xuống cuối.
2. Bung mặc định = các nhóm **có dòng** (ưu tiên `high` rồi `medium`), tối đa 2–3 nhóm.
3. Nhóm rỗng: **không** đeo tag đỏ nữa — đổi sang tag xám "Không có" (mức độ của *luật*, không phải
   của *kết quả*, mà tag đỏ đang đọc như kết quả).
4. Gọn hơn nữa: gộp toàn bộ nhóm rỗng thành **một dòng cuối trang**, ví dụ:
   `Đã kiểm tra, không phát hiện gì: Giá mủ nguyên liệu sai đơn vị tính · Giá bán sai đơn vị tính ·
   Doanh thu một ngày bất thường · Đơn vị ngừng nộp nhiều ngày.` — vừa giữ bằng chứng "đã quét",
   vừa không chiếm chỗ. Đây là phương án tôi khuyên dùng.

Đáng làm ngay — rẻ nhất, đổi hẳn cảm nhận về trang.

---

### 🔴-2. Thông báo "sạch sẽ" không bao giờ hiện được
`apps/web/src/features/command-center/pages/AnomalyPage.tsx:280-282`

```tsx
{groups.length === 0 ? (
  <Alert type="success" ... message="Không phát hiện bất thường nào trong khoảng đã chọn." />
```

**Người dùng gặp gì.** `scan()` **luôn** trả về 8 nhóm (`anomaly_rules.py:416-427` — kể cả khi luật
lỗi cũng trả nhóm rỗng), nên `groups.length === 0` là **nhánh chết**. Ngày mọi thứ sạch, admin
không thấy câu "Không phát hiện bất thường" mà thấy **8 panel lần lượt nói "Không có cảnh báo"** và
5 thẻ số 0. Đúng là trang "vô dụng" theo đúng chữ trong đề bài.

**Đề xuất.** Đổi điều kiện sang `report.summary.total === 0`, và khi sạch thì hiện đúng một khối
xác nhận, ví dụ:

> **Không phát hiện bất thường nào.** Đã quét 8 nhóm luật trên số liệu của 21 đơn vị, kỳ
> 01/01/2026 → 10/09/2026. *(kèm dòng liệt kê tên 8 nhóm đã kiểm, cỡ chữ nhỏ)*

Câu "đã quét N nhóm / N đơn vị" quan trọng: không có nó, admin sẽ nghi trang hỏng chứ không tin là
số liệu sạch.

---

### 🔴-3. "Giá lớn nhất" không có đơn vị tính → chính admin cũng không biết con số nói gì
`apps/api/app/services/anomaly_rules.py:143` (nhãn cột) · mô tả nhóm ở `:139-141`

**Người dùng gặp gì.** Ảnh 01 dòng Cao su Hà Tĩnh: mô tả nhóm nói *"Giá bán quy đổi vượt **200 triệu
đ/tấn** (mặt bằng 40–70)"*, nhưng ô "GIÁ LỚN NHẤT" hiện **50.750.000**, loại tiền VND. Hai con số
không cùng thang: 50.750.000 là **số đơn vị gõ vào ô** (ô đó phải nhập theo *triệu đồng/tấn*), còn
ngưỡng 200 là *triệu đồng/tấn*. Admin chụp màn hình này gửi đơn vị, đơn vị đọc "giá lớn nhất
50.750.000" rồi cãi "giá tôi có 50 triệu, đúng mà" — đôi bên nói hai ngôn ngữ khác nhau.

**Đề xuất.**
- Đổi nhãn cột: **"Đơn giá lớn nhất đã nhập"** (rõ là *số đơn vị đã gõ*, không phải giá thật).
- Thêm câu vào mô tả nhóm: *"Ô đơn giá của hợp đồng VND phải nhập theo **triệu đồng/tấn**. Con số
  trong bảng là đúng những gì đơn vị đã gõ — vượt ngưỡng nghĩa là nghi gõ theo đồng/tấn."*
- Lý tưởng thì thêm cột **"Quy ra triệu đ/tấn"** để thấy 50.750.000 tương đương 50.750.000 triệu
  đ/tấn — nhưng chỉ câu chữ ở trên đã đủ gỡ hiểu lầm, làm sau cũng được.

Cùng bệnh, nhẹ hơn: `:89` **"Số ô sai"** — "ô" ở đây là ô nào? (bản ghi giá của đơn vị theo ngày).
Đổi thành **"Số ngày có giá sai"** thì đơn vị biết đi tìm cái gì.

---

## 🟡 NÊN SỬA

### 🟡-4. Thẻ tổng quan không bấm được, và "Cần xem 138" không nói gì
`AnomalyPage.tsx:54-73` (`SummaryCards` là `<div>` thuần, không handler)

**Người dùng gặp gì.** 5 con số đẹp nhưng **chết**: thấy "Nghiêm trọng 6" rồi vẫn phải tự cuộn đi
tìm 6 dòng đó ở đâu. Riêng "Cần xem 138" thì mơ hồ hoàn toàn — cần xem *cái gì*?

**Đề xuất (~10 dòng).**
- Thẻ mức độ bấm được → cuộn tới + bung nhóm đầu tiên của mức đó (`activeKeys` đã có sẵn, chỉ thêm
  `scrollIntoView`). Thêm `cursor:pointer` + `role="button"` + `tabIndex={0}`.
- Thêm dòng phụ trong thẻ (class `.kpi .sub` đã có sẵn ở `styles/command-center.css:62`) ghi tên
  nhóm đông nhất: ví dụ dưới "Cần xem 138" ghi *"phần lớn: Chưa nộp / thiếu một phần"*.
- Cân nhắc thêm **một dòng kết luận** ngay dưới hàng thẻ để trả lời đúng câu "3 giây":
  **"Gấp nhất: 1 đơn vị chưa gộp tồn kho sau sáp nhập — Cao su Lộc Ninh."**

### 🟡-5. Xem xong không biết đi đâu sửa — trong khi hạ tầng deep-link ĐÃ có sẵn
`AnomalyPage.tsx:101-118` (bảng không có cột hành động)

**Người dùng gặp gì.** Bảng cho biết *đơn vị nào · ngày nào · sai gì*, rồi dừng. Admin phải tự nhớ
màn nào sửa được cái đó, tự mở menu, tự chọn lại đơn vị và ngày.

**Đề xuất — rất rẻ vì đường đã mở sẵn:** `UnitDailyPage` đã nhận `?ngay=&don-vi=` và **tự bật phiếu
của đúng ngày đó** (`apps/web/src/features/command-center/pages/UnitDailyPage.tsx:52-59`; mẫu dùng
sẵn ở `sections/MemberChecklistBanner.tsx:237`). Chỉ cần một bảng tra cứu tĩnh ở frontend:

| Nhóm | Link |
|---|---|
| `missing_price` | `/bao-cao-thu-mua?ngay={ngay}&don-vi={don_vi}` (mở thẳng phiếu sai) |
| `wrong_raw_price` | `/quan-ly-so-lieu/gia-mu-nguyen-lieu` |
| `not_submitted`, `silent_unit` | `/thong-ke/tinh-trang-nop` (ma trận đơn vị × ngày — **chỉ đúng ngày nào thiếu**) |
| `missing_merge_stock` | `/bao-cao-ton-kho?don-vi={don_vi}` |
| `plan_missing` | `/ke-hoach-nam` |
| `wrong_sale_price`, `revenue_outlier` | `/hop-dong` |

Làm tối thiểu: mỗi nhóm **một liên kết ở dòng mô tả** ("Sửa tại: Theo dõi nộp báo cáo"). Làm đầy
đủ: thêm cột cuối "Mở phiếu" cho 2 nhóm có cặp (đơn vị, ngày) là `missing_price` và
`wrong_sale_price`. Tôi khuyên làm bản tối thiểu trước — 90% giá trị, 1/5 công.

### 🟡-6. Số không canh phải, cột dài không cắt → bảng chụp gửi Zalo bị cắt
`AnomalyPage.tsx:101-106` (mọi cột đều render mặc định, canh trái) · `:111` (`scroll: max-content`)

**Người dùng gặp gì.** "50.750.000", "2.592.983,9", "3" đều canh trái (thấy rõ trong ảnh 01), mắt
không dóng hàng được để so số nào lớn. Nặng hơn: `scroll={{ x: "max-content" }}` cho bảng nở theo
nội dung, mà cột "Mã hợp đồng" (`anomaly_rules.py:145`, ghép `string_agg` mọi mã) và "Ô còn thiếu"
(`:406`, ghép 5 nhãn chỉ tiêu) có thể dài vài trăm ký tự → bảng tràn ngang, **ảnh chụp màn hình mất
đúng cột cuối**. Ảnh 01 đang dừng ở "01, 1812-02, 34" — nhiều khả năng còn nữa mà bị che.

**Đề xuất (~8 dòng, ngay trong `GroupTable`).**
- Canh phải + `whiteSpace: nowrap` cho cột mà giá trị mẫu là `number` (suy từ `rows[0]`, không cần
  backend khai thêm). Dự án đã có tiền lệ `align: "right"` ở `lib/unit-daily-columns.tsx`.
- Cột chuỗi dài: `ellipsis: { showTitle: true }` + `width` trần (ví dụ 260) — di chuột vẫn xem đủ,
  ảnh chụp không vỡ.

### 🟡-7. Quét lại là trắng nguyên trang
`AnomalyPage.tsx:267-277` (khối `loading`) và `:277` (`{!loading && report && …}`)

**Người dùng gặp gì.** Mỗi lần bấm "Quét lại" hoặc lưu ngưỡng, **toàn bộ kết quả biến mất** ~1,3
giây rồi vẽ lại từ đầu — mất luôn chỗ đang cuộn và các panel đang mở. Với 1,3 giây thì spinner toàn
trang là quá tay; nhấp nháy kiểu này làm người dùng tưởng trang lỗi.

**Đề xuất.** Lần quét ĐẦU (chưa có `report`): giữ spinner lớn như hiện tại, hoặc `Skeleton` cho 5
thẻ + 3 panel — dễ chịu hơn. Lần quét SAU: **giữ nguyên kết quả cũ**, chỉ để nút "Quét lại" xoay +
bọc `<Spin spinning={loading}>` mờ nhẹ lên phần kết quả. Sửa ~6 dòng.

### 🟡-8. Web và Excel gọi mức độ bằng hai bộ từ khác nhau
`AnomalyPage.tsx:35-39` (Nghiêm trọng · **Cần xem** · **Ghi nhận**)
`apps/api/app/services/anomaly_export.py:23` và `:94-96` (Nghiêm trọng · **Trung bình** · **Nhẹ**)

**Người dùng gặp gì.** Admin xem web thấy "Cần xem 138", xuất Excel gửi đơn vị thì cột ghi "Trung
bình". Hai bên họp, một người đọc web một người đọc Excel → cãi nhau về một thứ.

**Đề xuất.** Chốt một bộ. Tôi nghiêng về bộ của web vì nó nói *phải làm gì* chứ không chỉ *nặng nhẹ
bao nhiêu*: **Nghiêm trọng · Cần xem · Ghi nhận**. Sửa `_SEV_LABEL` và 2 nhãn ở `_overview_sheet`.

### 🟡-9. Excel xuất ra chưa gửi thẳng cho đơn vị được
`anomaly_export.py:71-78` (ghi thẳng giá trị thô) · `:89` và `:130` (kỳ rà soát dạng ISO) ·
`:131-133` (nhóm nào cũng tạo sheet)

**Người dùng gặp gì** — 3 lỗi nhỏ cộng lại thành file trông "máy in ra":
1. **Ngày kiểu máy**: ô ngày là chuỗi `2026-01-27`, trong khi web hiện `27/01/2026`
   (`AnomalyPage.tsx:50` có đổi, Excel thì không). Dòng "Kỳ rà soát" cũng là `2026-01-01 →
   2026-09-10`.
2. **TRUE/FALSE**: cột "Thiếu tỷ giá" là bool Python → Excel hiện `TRUE`; web hiện "Có"
   (`AnomalyPage.tsx:48`).
3. **4 sheet rỗng** (đúng tình trạng production hôm nay): người nhận mở file, lật 4 sheet trắng
   trước khi tới sheet có việc.

**Đề xuất.** Định dạng ngày `dd/mm/yyyy` + bool → "Có"/"Không" ngay tại `_group_sheet`; bỏ qua nhóm
rỗng khi tạo sheet (`Tổng quan` vẫn liệt kê đủ 8 nhóm với số 0 — vẫn chứng minh "đã quét").

### 🟡-10. Nói "đơn vị bị nêu tên" cho đơn vị chưa chắc có lỗi
`anomaly_rules.py:174` + `:180` (`don_vi` = *đơn vị đóng góp lớn nhất*) → `anomaly_types.py:46`
(hàm `group` đếm `units` từ khoá `don_vi`) → `AnomalyPage.tsx:60` (thẻ "Đơn vị bị nêu tên")

**Người dùng gặp gì.** Ở nhóm "Doanh thu một ngày bất thường", cột `don_vi` mang nghĩa **"đơn vị
đóng góp doanh thu lớn nhất ngày đó"** — có thể hoàn toàn vô can (bán nhiều thật). Nhưng vì dùng
chung khoá `don_vi`, đơn vị ấy bị đếm vào "**1 đơn vị**" trên tiêu đề nhóm và vào thẻ "**Đơn vị bị
nêu tên**". Đây đúng là chỗ "kết luận oan" mà đề bài lo.

**Đề xuất.** Nhẹ nhất: thêm câu vào mô tả nhóm — *"Cột 'Đơn vị đóng góp lớn nhất' chỉ để dò nhanh
dòng nào gây vọt, **chưa khẳng định đơn vị này nhập sai**."* Và đổi nhãn thẻ tổng quan từ "Đơn vị bị
nêu tên" → **"Đơn vị cần rà"** (đỡ giọng buộc tội, đúng tinh thần câu đã có sẵn ở tiêu đề trang:
*"Cảnh báo là dấu hiệu cần kiểm tra, chưa chắc đã là số sai"*). Sạch nhất (đắt hơn): đổi khoá cột
này thành `don_vi_top` để nó không lọt vào phép đếm đơn vị.

### 🟡-11. "14/253 ngày thiếu" — con số đúng nhưng đọc như bản án
`anomaly_rules.py:292`, `:300-302` (giá trị ô) · `:305-310` (mô tả nhóm)

**Người dùng gặp gì.** Ba vấn đề chồng nhau ở nhóm đông nhất production (14 dòng):
1. Mô tả nhóm in **ngày ISO** lẫn trong câu tiếng Việt: *"Thu mua: kỳ 2026-01-01 – 2026-09-10"* —
   lệch hẳn với `DD/MM/YYYY` ở mọi chỗ khác trên trang.
2. Mẫu số là **ngày lịch**, tính cả thứ Bảy · Chủ nhật · lễ. Mô tả không nói rõ điều đó, nên đơn vị
   nộp đủ mọi ngày làm việc vẫn hiện "thiếu ~14 ngày" và bị nhắc oan. **Cần chốt lại với nghiệp vụ:
   đơn vị có phải nộp cả ngày nghỉ không?** — nếu không, luật đang thổi phồng con số.
3. Bảng cho biết *thiếu bao nhiêu ngày* nhưng **không cho biết thiếu ngày nào** → admin không nhắc
   cụ thể được, đơn vị cũng không biết mở phiếu nào.

**Đề xuất.** (a) `dmy` cho 2 mốc trong mô tả; (b) nói thẳng trong mô tả *"đếm theo ngày lịch, tính
cả ngày nghỉ"* (hoặc bỏ ngày nghỉ khỏi mẫu số nếu nghiệp vụ chốt vậy); (c) thay vì thêm cột, **link
sang `/thong-ke/tinh-trang-nop`** (xem 🟡-5) — màn đó vẽ sẵn ma trận đơn vị × ngày và đã xử lý đúng
ca đơn vị đã sáp nhập. Đỡ phải làm lại.

### 🟡-12. Tên biểu trong bảng là tên cũ
`anomaly_rules.py:310` — nhãn cột **"Biểu Tiêu thụ–Tồn kho"**

**Người dùng gặp gì.** Menu và màn nhập liệu giờ gọi là **"Tồn kho (theo ngày)" / "Báo cáo tồn
kho"** (`AdminLayout.tsx` nhóm nhập liệu; route `/bao-cao-tieu-thu-ton-kho` đã chuyển hướng sang
`/bao-cao-ton-kho`, `App.tsx:185`). Admin đọc "Biểu Tiêu thụ–Tồn kho" rồi đi tìm trong menu không
thấy. Đổi nhãn cột cho khớp menu — sửa một chuỗi.

### 🟡-13. Mỗi nhóm cắt trang ở 10 dòng
`AnomalyPage.tsx:30` (`ROWS_PER_PAGE = 10`) · `:112-115`

**Người dùng gặp gì.** Nhóm "Chưa nộp" có 14 dòng → thành 2 trang → muốn gửi Zalo phải chụp 2 ảnh
và người nhận không biết còn trang 2. Đây là dữ liệu **đã gom sẵn** (mỗi đơn vị một dòng), không
phải danh sách dài vô hạn.

**Đề xuất.** Nâng lên 25, hoặc `pagination={rows.length > 25 ? {...} : false}` — dưới 25 dòng thì
bỏ hẳn thanh phân trang, một ảnh chụp là đủ.

---

## 🟢 GÓP Ý (để sau)

- **🟢-14. Thiếu nút chọn nhanh kỳ.** `AnomalyPage.tsx:253-257` — chỉ có `RangePicker` trần, trong
  khi dự án đã có `lib/date-presets.ts` (Tuần này · Tháng này · Năm nay…) dùng ở `PeriodReportPage`
  và `AnalyticsFilters`. Đốc thúc *hôm nay* mà mặc định quét cả năm thì lỗi tồn đọng từ tháng 1 trộn
  lẫn với việc mới. Thêm `presets` vào `RangePicker` là xong.
- **🟢-15. Nhóm `wrong_raw_price` không có ngày.** `anomaly_rules.py:78-89` — SQL `GROUP BY grade,
  price_type`, không giữ `as_of`. Admin biết "Hà Tĩnh · mủ nước · sai" nhưng không biết **ngày nào**
  để bảo đơn vị mở phiếu. Thêm `min(as_of), max(as_of)` vào SELECT là có ngay 2 cột "Từ ngày /
  Đến ngày" như nhóm giá bán.
- **🟢-16. Thứ tự dòng trong bảng.** `not_submitted` (`:296-303`) và `plan_missing` (`:395-401`) xếp
  theo `sort_order` của đơn vị; nên xếp **thiếu nhiều nhất lên đầu** như `silent_unit` đã làm
  (`:371`). Admin đọc từ trên xuống là gặp ngay ca nặng nhất.
- **🟢-17. "Thiếu tỷ giá: Có".** `anomaly_rules.py:144` + `AnomalyPage.tsx:48` — "Có" nghĩa là *có
  thiếu*, đọc dễ hiểu ngược. Đổi nhãn cột thành **"Tỷ giá"** với giá trị "Thiếu" / "Đủ".
- **🟢-18. Màu viết cứng, không dùng biến theme.** `AnomalyPage.tsx:36-38` (`#c0392b`, `#a96a00`,
  `#0369a1`) và `:96` (`#0b7a3b`). `styles/command-center.css:4-5` đã có `--danger`, `--gold`,
  `--info`, `--accent-2`. Đổi màu chủ đạo sau này sẽ sót trang này.
- **🟢-19. File dài 298 dòng.** Luật chung là <400, nhưng `AGENTS.md:52` của dự án ghi **<200**.
  Tách `ThresholdDrawer` (dòng 120-191) sang `AnomalyThresholdDrawer.tsx` là còn ~210 — vừa gần
  chuẩn vừa để `AnomalyPage` chỉ còn lo bố cục.
- **🟢-20. Nút "Xuất Excel" bị mờ mà không nói vì sao.** `AnomalyPage.tsx:260-262` — khi sạch thì
  `disabled`, người dùng không biết là do không có gì để xuất hay do lỗi. Bọc `Tooltip` một câu.
- **🟢-21. Tải Excel xong im lặng.** `anomaly-client.ts:82-93` — không có `message.success`. Trên
  máy tải file ngầm, admin dễ bấm lại 2-3 lần.
- **🟢-22. Câu mở đầu hơi mâu thuẫn.** `AnomalyPage.tsx:240-241` nói *"gom **mọi dấu hiệu sai**"*,
  câu ngay dưới (`:245`) lại nói *"chưa chắc đã là số sai"*. Đổi vế trên thành *"gom mọi **dấu hiệu
  cần kiểm tra**"* cho nhất quán.

---

## Những chỗ đã làm ĐÚNG chuẩn (giữ nguyên)

- **Không emoji** — đã soát cả 5 file, chỉ dùng `@ant-design/icons`. ✔
- **Hint trong form nhập màu đỏ** — `AnomalyPage.tsx:180` dùng `className="form-note"`
  (`styles/command-center.css:43` → `var(--danger)`); ảnh 03 hiện đúng đỏ. Dòng "Mặc định: 1.500"
  để màu `--muted` là đúng (không phải lời dặn, chỉ là thông tin). ✔
- **Giao diện sáng, `.card`/`.kpi`/`.page-title` đúng bộ `command-center.css`.** ✔
- **Số định dạng nghìn kiểu Việt** qua `formatViNumber`, ngày ISO tự đổi `DD/MM/YYYY`
  (`AnomalyPage.tsx:44-51`). ✔
- **Cột dựng động theo server** — thêm luật mới ở backend, web hiện ngay, không phải sửa frontend.
  Thiết kế này đáng giữ. ✔
- **Một luật lỗi không kéo sập cả lần quét** (`anomaly_rules.py:46-54`). ✔
- **Ngăn cấu hình ngưỡng**: nạp lại mỗi lần mở, "Khôi phục mặc định" chỉ điền chứ không lưu, mỗi
  ngưỡng có câu giải thích bằng tiếng nghiệp vụ ("mặt bằng 100–1.500 đ/độ"). Đây là phần làm tốt
  nhất của trang. ✔

---

## Thứ tự nên làm

| # | Việc | Sửa ở đâu | Công |
|---|---|---|---|
| 1 | Nhóm có cảnh báo lên trên · nhóm rỗng gộp một dòng cuối · bung đúng nhóm có việc | `AnomalyPage.tsx` | ~15 dòng |
| 2 | Thông báo "sạch" dùng `summary.total === 0` | `AnomalyPage.tsx:280` | ~5 dòng |
| 3 | "Giá lớn nhất" → "Đơn giá lớn nhất đã nhập" + câu giải thích đơn vị tính | `anomaly_rules.py:139-143` | 2 chuỗi |
| 4 | Thống nhất nhãn mức độ web ↔ Excel | `anomaly_export.py:23,94-96` | 2 dòng |
| 5 | Canh phải số · cắt cột dài · 25 dòng/trang | `AnomalyPage.tsx:30,101-115` | ~10 dòng |
| 6 | Thẻ tổng quan bấm được + dòng "Gấp nhất hôm nay" | `AnomalyPage.tsx:54-73` | ~15 dòng |
| 7 | Link sang màn sửa (bản tối thiểu: 1 link/nhóm ở dòng mô tả) | `AnomalyPage.tsx` | ~20 dòng |
| 8 | Quét lại không xoá trắng kết quả cũ | `AnomalyPage.tsx:267-277` | ~6 dòng |
| 9 | Excel: ngày dd/mm · Có/Không · bỏ sheet rỗng | `anomaly_export.py` | ~15 dòng |
| 10 | Câu chữ nhóm "Chưa nộp" + "Doanh thu" (chống kết luận oan) | `anomaly_rules.py` | vài chuỗi |

Mục 1-5 nên gộp một lần sửa, deploy ngay (thuần giao diện/câu chữ, không đụng luật tính toán).
Mục 6-10 để đợt sau.

---

## Kết luận

**Trang đã dùng được cho Ban TTKD — nhưng chưa nên coi là xong.**

Số liệu đúng, luật quét tái dùng đúng bộ đã chạy thật ở skill `bao-cao-nhap-lieu`, cấu hình ngưỡng
tốt, tuân thủ chuẩn dự án (không emoji · hint đỏ · giao diện sáng). Công cụ này chắc chắn hơn hẳn
việc chạy script tay.

Nhưng ở **đúng trạng thái production hôm nay** — 25 cảnh báo, 4/8 nhóm rỗng — bố cục đang làm hại
chính nó: mở trang ra là ba thẻ đỏ "Nghiêm trọng" với 0 dòng, còn 21 việc thật thì nằm sau các panel
đóng, và ngày mọi thứ sạch thì trang không nói được câu "sạch". Hai lỗi này (🔴-1, 🔴-2) tổng cộng
~20 dòng frontend.

Sau khi xong nhóm 🔴 và mục 4-5 trong bảng trên, trang đủ sức làm **màn mở đầu buổi sáng của admin**
và ảnh chụp gửi Zalo dùng được luôn. Trước đó thì vẫn dùng được, chỉ là admin phải tự bấm bung từng
nhóm — và người mới sẽ hiểu nhầm là hệ thống đang báo động đỏ.

---

## Câu còn treo (cần chủ dự án / nghiệp vụ chốt)

1. **Đơn vị có phải nộp báo cáo ngày nghỉ (T7/CN/lễ) không?** Nếu không, `not_submitted` đang tính
   thừa ~2 ngày/tuần vào mẫu số và nhắc oan (`anomaly_rules.py:292, 302`).
2. **Biểu Thu mua có mốc bắt đầu thu thập giống `STOCK_START = 2026-07-24` không?**
   (`anomaly_rules.py:273`). Hiện Thu mua đếm thẳng từ 01/01 — đơn vị được cấp tài khoản giữa năm sẽ
   hiện "thiếu ~180/253 ngày", con số đúng nhưng kết luận sai.
3. **Bộ từ cho mức độ**: chốt "Cần xem / Ghi nhận" (web) hay "Trung bình / Nhẹ" (Excel)?
4. **"Tổng số cảnh báo" đang cộng số DÒNG của các nhóm có đơn vị đếm khác nhau** — 1 dòng nhóm
   "Chưa nộp" = 1 *đơn vị*, 1 dòng nhóm "Thiếu đơn giá" = 1 *đơn vị × 1 ngày*. Cộng lại thành 25 thì
   con số đó nên hiểu là gì? Có cần đổi nhãn thành "Tổng số dòng cần rà" không?
5. **Có cần bản xuất theo TỪNG đơn vị** (để gửi riêng cho từng đơn vị) không, hay admin cứ dùng
   AutoFilter sẵn có trong file Excel hiện tại là đủ?
