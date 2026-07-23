# Cách lấy giá từng sàn — Chi tiết & Bảng xác nhận

> **Mục đích:** đối chiếu **quy trình thủ công của chuyên viên** ↔ **quy trình hệ thống tự động làm**, để chuyên viên (Tâm…) **xác nhận tính chính xác** từng bước.
> **Nguồn gốc:** số hóa từ `Các Web và hướng dẫn lấy giá… .docx` (chuyên viên Tâm) → spec `knowledge/data-sources/lay-gia-cac-san.md` → code `services/crawlers/`.
> **Cách dùng:** đọc cột "Hệ thống làm", so với cách anh/chị đang làm tay; mục **✅ Cần xác nhận** ở cuối mỗi sàn là chỗ tick Đúng/Sai.

## Quy ước chung
- **Mốc thời gian:** lấy giá của **ngày trước hiện tại 1 ngày (T‑1)**. Với sàn công bố theo phiên (SHFE, OSE), hệ thống **tự lùi ngày**, bỏ T7/CN, để lấy báo cáo **mới nhất có sẵn** (nếu hôm nay chưa đăng).
- **Chọn kỳ hạn:** theo **kinh nghiệm chuyên viên** — kỳ hạn có **Khối lượng (Volume)** hoặc **Giá trị giao dịch (Trading Value)** lớn nhất. Hệ thống **không cố định số tháng**, mà tính trực tiếp từ dữ liệu phiên.
- **Cô lập lỗi:** một sàn lỗi không chặn các sàn khác.

## Số liệu mẫu để đối chiếu — phiên **15/06/2026** (hệ thống chạy thật)
| Sàn | Mặt hàng | Giá | Đơn vị |
|---|---|---|---|
| ANRPC | SMR20 / STR20 / SIR20 / RSS3 | 2.33 / 2.54 / 2.26 / 3.16 | US$/kg |
| SHFE | RU (Natural Rubber) | 17,760 | CNY/tấn |
| OSE/TOCOM | RSS3 / TSR20 | 435.9 / 362.0 | JPY/kg |
| LGM | SMR CV / SMR20 / **Latex** | 335.1 / 235.95 / **198.04** | US cents/kg |
| Tỷ giá | USD/VND · CNY · THB · JPY · MYR | 26.184,79 · 6,7691 · 32,6631 · 160,1404 · 4,0572 | / USD |
| SGX/SICOM | TSR20 · RSS3 | *(chưa lấy được)* | — |

> 👉 Đề nghị chuyên viên so các số trên với **bản tin ngày 15/06/2026** để xác nhận khớp.

---

## 1. ANRPC — giá physical (SMR20, STR20, SIR20, RSS3)

**Lấy gì:** giá physical 4 grade chuẩn. **Đơn vị:** US$/kg · **Loại:** physical.

| Bước | Chuyên viên (thủ công) | Hệ thống (tự động) |
|---|---|---|
| 1 | Mở `anrpc.org/anrpc-daily-price` | Tải HTML trang ANRPC Daily Price |
| 2 | Nhìn bảng giá, tìm cột ngày mới nhất | Trích mọi bảng `<table>`; tìm bảng có hàng tiêu đề chứa **ngày** (định dạng dd/mm/yyyy · dd‑mm‑yyyy · yyyy‑mm‑dd) |
| 3 | Đọc giá theo dòng grade | Chọn **cột ngày MỚI NHẤT**; map nhãn dòng: `BKK (RSS3)`→RSS3, `SMR 20`→SMR20, `STR 20`→STR20, `SIR 20`→SIR20 |
| 4 | Ghi số | Lấy **số đầu tiên** trong ô (bỏ dấu phẩy) → giá |

**✅ Cần xác nhận:**
- [ ] Lấy đúng **cột ngày mới nhất** là đúng ý (không phải cột cố định)?
- [ ] 4 grade SMR20/STR20/SIR20/RSS3 là đủ cho bản tin? (web còn LATEX — có cần không?)

---

## 2. SHFE (Thượng Hải) — Natural Rubber (RU)

**Lấy gì:** giá **Settlement** của kỳ hạn **Volume lớn nhất**. **Đơn vị:** CNY/tấn · **Loại:** settlement.

| Bước | Chuyên viên (thủ công) | Hệ thống (tự động) |
|---|---|---|
| 1 | Vào `shfe.com.cn` → Statistical Data → Daily | Bắt đầu từ hôm nay, **lùi dần bỏ T7/CN** (tối đa 7 ngày làm việc) |
| 2 | Chọn ngày (T‑1) → Future → Daily express | Tải file dữ liệu chính thức `…/dailydata/kx{YYYYMMDD}.dat` (JSON) |
| 3 | Mục **Natural rubber**, xem các kỳ hạn | Lọc dòng cao su (`PRODUCTID = ru_f…`); **bỏ dòng tổng** (小计/total) và dòng settlement ≤ 0 |
| 4 | Chọn kỳ hạn **Volume lớn nhất** | Chọn kỳ hạn có **VOLUME** lớn nhất |
| 5 | Lấy giá tại cột **Settle** | Lấy **SETTLEMENTPRICE** của kỳ hạn đó (kèm volume + open interest) |

**✅ Cần xác nhận:**
- [ ] "Volume lớn nhất → giá Settle" đúng quy trình? (spec ghi *thường cách ~3 tháng* — hệ thống chọn theo Volume thực, không cố định tháng)
- [ ] Đơn vị **CNY/tấn** đúng (không quy đổi sang US$/kg ở bước này)?

---

## 3. OSE / TOCOM (Nhật) — RSS3 & TSR20

**Lấy gì:** giá **Settlement** của kỳ hạn **Trading Value lớn nhất**. **Đơn vị:** JPY/kg · **Loại:** settlement.
*(Cao su đã chuyển sang sàn OSE sau tái cơ cấu JPX 2020.)*

**Link đầy đủ** (không viết tắt): `https://www.jpx.co.jp/automation/markets/statistics-derivatives/daily/files/{YYYYMM}/Daily_Report_OSE_{YYYYMMDD}.zip`
— vd phiên **22/07/2026** → `.../daily/files/202607/Daily_Report_OSE_20260722.zip`.

| Bước | Chuyên viên (thủ công) | Hệ thống (tự động) |
|---|---|---|
| 1 | Vào `jpx.co.jp` → Statistics‑Derivatives → Daily | Tải gói **Daily Report OSE** `Daily_Report_OSE_{YYYYMMDD}.zip` đúng phiên (Nhật nghỉ/lễ → 404; lùi tối đa 7 ngày làm việc để tìm báo cáo mới nhất **và ghi đúng ngày của báo cáo đó**) |
| 2 | Mở file **`cdf_dyr`** (Commodity Derivatives Futures), trang RSS3/TSR20 | Giải nén, lấy PDF `cdf_dyr_{YYYYMMDD}.pdf`; đọc text từng trang |
| 3 | Xem trang RSS3 / TSR20 của **thị trường đấu giá** | Chỉ giữ trang **競争売買 / AuctionMarket** (bỏ trang **J‑NET** thoả thuận); trang tiêu đề *RSS3 Rubber Futures* → RSS3, *TSR20 Rubber Futures* → TSR20 — hiện là **trang 12 & 13** |
| 4 | Đọc bảng các kỳ hạn | Mỗi dòng = 1 kỳ hạn (mã 6 số `yyyymm`): **settle** = số thập phân cuối dòng (cột 清算数値 Settlement Price), **trading value** = số tiền lớn nhất trên dòng (≥ 1 triệu ¥, cột 取引金額 cả phiên) |
| 5 | Chọn kỳ hạn **Trading Value lớn nhất** | Chọn kỳ hạn **Trading Value** lớn nhất (nếu cả bảng không giao dịch → kỳ hạn gần nhất, dòng đầu) |
| 6 | Lấy **Settlement Price** | Lấy **settle** của kỳ hạn đó (JPY/kg) |

**Đối chiếu thực tế phiên 22/07/2026** (chạy lại crawler trên file gốc của JPX):

| Kỳ hạn | Trading Value (¥) | Settlement (JPY/kg) |
|---|---:|---:|
| 202607 | 46.278.500 | 429,5 |
| 202611 | 96.482.500 | 418,0 |
| **202612** | **732.392.000** ← lớn nhất | **420,7** ✅ |
| 202701 | 71.486.500 | 420,3 |

→ Hệ thống lấy **420,7 JPY/kg** — khớp đúng số hiển thị trên Bảng tính giá (420,7 ÷ 163,1222 × 1.000 = **2.579 USD/tấn**).
Kiểm chứng chéo: 732.392.000 ¥ ÷ (349 lô × 5.000 kg) ≈ 419,7 ¥/kg → đúng đơn vị **JPY/kg**.

**✅ Cần xác nhận:**
- [ ] "Trading Value lớn nhất → Settlement" đúng? (spec ghi *thường ~5 tháng* / trang 12 — thực tế 22/07/2026 rơi vào 202612, đúng ~5 tháng)
- [ ] Cách đọc **Trading Value** (giá trị giao dịch ¥) trong PDF đúng cột anh/chị dùng?
- [ ] ⚠️ Gói ZIP của JPX chỉ lưu **~4 tháng gần nhất** → lịch sử 2 năm phải lấy từ **Excel của VRG / J‑QUANTS**. Xác nhận có nguồn lịch sử này?
- [ ] ⚠️ **TSR20 trên OSE gần như không có giao dịch** (0/12 kỳ hạn có KL ở mọi phiên đã kiểm tra) → settlement là số sàn công bố, không phải giá khớp lệnh. Bảng tính giá không dùng cột này.

---

## 4. LGM (Malaysia) — physical FOB (SMR CV/L/5/GP/10/20 + Latex)

**Lấy gì:** giá physical FOB. **Đơn vị:** US cents/kg · **Loại:** physical.

| Bước | Chuyên viên (thủ công) | Hệ thống (tự động) |
|---|---|---|
| 1 | Vào `lgm.gov.my` → reference prices (FOB) → chọn ngày | Gọi API mà trang LGM dùng: `…/api/rubberprice/currentprice` (token Basic **công khai** nhúng sẵn trong web LGM) |
| 2 | SMR CV, SMR20… đọc theo **US Cents/Kg** | SMR*: lấy thẳng trường **US cents/kg** (`sellersUs`) |
| 3 | **Latex** (Sen/Kg) → quy đổi: *giá ÷ tỷ giá × 10* | **Latex**: API trả Sen/kg → tự quy đổi **US cents/kg = Sen/kg ÷ tỷ giá MYR/USD** (tỷ giá suy ra từ chính cặp Sen↔US cents của SMR **cùng phiên**) |

**✅ Cần xác nhận (QUAN TRỌNG NHẤT):**
- [ ] 🔴 **Cách quy đổi Latex:** hệ thống dùng *tỷ giá nội tại cùng phiên của LGM* (Sen/kg ÷ tỷ giá), không dùng FX ngoài. Kết quả 15/06 = **198,04 US cents/kg**. Đề nghị so với cách *giá ÷ tỷ giá × 10* của chuyên viên — **có khớp không?**
- [ ] Danh sách grade (CV/L/5/GP/10/20 + Latex) đủ chưa? Bản tin cần grade nào là chính?
- [ ] Dùng giá **sellers (chào bán)** đúng chưa (hay cần buyers/giá khác)?

---

## 5. Tỷ giá (FX) — USD/VND · CNY · THB · JPY · MYR

**Lấy gì:** tỷ giá USD. **Mục đích:** theo dõi USD/VNĐ + quy đổi giá các sàn về cùng mặt bằng.

| Bước | Chuyên viên (thủ công) | Hệ thống (tự động) |
|---|---|---|
| 1 | USD/CNY, USD/THB: `exchangerates.org.uk`; MYR: `bnm.gov.my` | Gọi 1 API gộp `open.er-api.com/v6/latest/USD` |
| 2 | Đọc từng cặp | Lấy 5 cặp: VND, CNY, THB, JPY, MYR theo phiên mới nhất |

**✅ Cần xác nhận:**
- [ ] Hệ thống dùng **một nguồn tỷ giá gộp** (open.er‑api) thay cho exchangerates.org.uk + BNM — **chấp nhận được không?** (nếu cần đúng BNM cho MYR, em đổi nguồn)
- [ ] Lưu ý: quy đổi **Latex** hiện **không phụ thuộc** FX này (dùng tỷ giá nội tại LGM) — xác nhận hướng này ổn.

---

## 6. SGX / SICOM (Singapore) — TSR20 (TF) & RSS3 (RT)

**Lấy gì:** settlement của hợp đồng giao **THÁNG SAU**. **Đơn vị:** US cents/kg · **Loại:** settlement.

| Bước | Chuyên viên (thủ công) | Hệ thống (tự động) |
|---|---|---|
| 1 | `sgx.com` → giá kỳ hạn cao su TF/RT | Gọi `api.sgx.com/derivatives/v1.0/contract-code/{TF\|RT}?category=futures` (header Origin/Referer sgx.com) |
| 2 | RSS3 = COM **RT**, TSR20 = COM **TF** | Nhận diện mã hợp đồng TF→TSR20, RT→RSS3 |
| 3 | Lấy hợp đồng giao **tháng sau** so với hiện tại | Lọc `delivery-month` = tháng-sau theo **giờ Singapore (UTC+8)**; vd 08/07/2026 → 2026-08 |
| 4 | Lấy giá **SETTLE** | Lấy `preliminary-settlement-price-abs` (cần > 0; sáng sớm chưa settle = 0 → bỏ, chờ phiên sau) |

**✅ Cần xác nhận:**
- [x] Kỳ hạn = **tháng sau** (next month, giờ SGP) → SETTLE. Verify 08/07/2026: RSS3 2.885, TSR20 2.168 (khớp bảng chuyên viên).
- [ ] Khi kỳ tháng-sau chưa ra settlement (sáng sớm) → để trống chờ phiên sau, có ổn không?

---

## Tổng hợp điểm cần chuyên viên xác nhận
1. [ ] **Quy ước T‑1** — chấp nhận "lấy báo cáo mới nhất có sẵn" khi hôm nay sàn chưa đăng?
2. [ ] **SHFE** — chọn kỳ hạn theo **Volume lớn nhất** → Settle.
3. [ ] **OSE/TOCOM** — chọn kỳ hạn theo **Trading Value lớn nhất** → Settlement; cách đọc Trading Value trong PDF.
4. [ ] 🔴 **LGM Latex** — cách quy đổi US cents/kg (198,04 ngày 15/06) khớp với *giá ÷ tỷ giá × 10*?
5. [ ] **FX** — nguồn tỷ giá gộp (open.er‑api) thay exchangerates.org.uk/BNM.
6. [ ] **SGX** — nguồn chính thức / phương án tạm.
7. [ ] **Lịch sử 2 năm** — nguồn Excel VRG / J‑QUANTS cho OSE.
8. [ ] **Danh mục grade & đơn vị** mỗi sàn đã đúng/đủ cho bản tin chưa.
