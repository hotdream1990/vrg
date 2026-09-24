# Trợ lý AI — Khả năng truy vấn (hiện trạng TRƯỚC & SAU)

> Ghi lại **AI chạm được tới dữ liệu nào** trước và sau đợt mở rộng "gói kỹ năng" (09/2026).
> Mục đích chính của Trợ lý: **truy vấn thông tin nâng cao + hỗ trợ tư vấn điều chỉnh giá sàn**.

## 1. Hiện trạng TRƯỚC (tính đến 10/09/2026 — bản 0.4.54)

Toàn bộ khả năng nằm ở 6 công cụ trong `apps/api/app/services/assistant_tools.py`:

| # | Công cụ | Dữ liệu chạm tới | Giới hạn |
|---|---|---|---|
| 1 | `get_exchange_prices` | Giá mới nhất 5 sàn (OSE · SHFE · SGX · TOCOM · MRB/LGM) | Chỉ ảnh chụp mới nhất |
| 2 | `get_price_trend` | Chuỗi N ngày của 1 sàn + 1 chủng loại | Mỗi lần 1 cặp sàn–chủng loại |
| 3 | `get_floor_prices` | Giá sàn Tập đoàn lần ban hành mới nhất | Không có lịch sử, không so sánh |
| 4 | `suggest_floor_adjustment` | Gợi ý NÂNG/GIỮ/HẠ + chỉ số dẫn hướng | Không có kịch bản what-if |
| 5 | `get_inventory_trend` | Tồn kho thành phẩm theo tuần (`fact_inventory`) | Không có tồn kho từ báo cáo đơn vị |
| 6 | `get_market_quote` | Báo giá mủ — **chỉ mục "xuất khẩu VRG"** | Bỏ 4/5 mục còn lại |

**Những mảng dữ liệu AI KHÔNG chạm tới được (trước đợt này):**

- **Tỷ giá** (`source=fx`: USD/VND, JPY, CNY, MYR, THB) — không tool nào, dù giá sàn quy đổi trực tiếp qua tỷ giá.
- **Giá Physical Reuters** (`source=reuters`: RSS3 · STR20 · SMR20 · SIR20 · Thai Latex Bulk/Drums) — bị bỏ vì `get_exchange_prices` lọc cứng `source ∈ {ose, shfe, sgx, tocom, lgm}`.
- **Giá mủ nguyên liệu** (`source=vrg`/`vrg_unit`: mủ nước · mủ chén · mủ dây) — yếu tố nội địa quan trọng nhất về mức giá.
- **Lịch sử ban hành giá sàn** (80 lần, 01/2024→08/2026) và so sánh giữa các lần.
- **Kịch bản giá sàn** (`floor_suggest.scenarios` đã có sẵn nhưng không được gọi).
- **Toàn bộ dữ liệu đơn vị thành viên**: thu mua · tiêu thụ · tồn kho · kế hoạch năm · tình trạng nộp · nhu cầu thị trường.
- **Toàn bộ hợp đồng bán & khách hàng**: cam kết · đã giao · **đã ký chưa giao** · doanh thu.
- Bản tin/báo cáo đã phát hành; độ tươi dữ liệu (lần quét gần nhất, sàn nào lỗi).

**Giới hạn kiến trúc trước đợt này:** `run_tool()` không biết người hỏi là ai (không nhận quyền);
mọi tool nạp vào mỗi lượt gọi LLM (không bật/tắt được); artifact chỉ có `table` và `line`.

## 2. Ranking yếu tố ảnh hưởng tới điều chỉnh giá sàn

### ★ Đo lại 24/09/2026 — 83 lần ban hành (18/01/2024 → 09/09/2026), FOB `SVR 10 / CSR 10`

Đây là bảng Trợ lý đang dùng (`assistant_service._FACTOR_RANKING`). Các bảng bên dưới là lần đo
cũ (80 lần, 17/08/2026), giữ lại để đối chiếu.

| Hạng | Yếu tố | r(mức) | r(Δ%) | Đồng hướng | r riêng phần (trừ rổ 4 futures) | n |
|---|---|---|---|---|---|---|
| 1 | **SHFE RU** | +0,87 | **+0,67** | **89%** | +0,29 | 82 |
| 2 | MRB SMR20 | +0,97 | +0,64 | 78% | +0,16 | 82 |
| 3 | SGX TSR20 | +0,95 | +0,58 | 76% | — | 82 |
| 4 | OSE RSS3 | +0,90 | +0,40 | 75% | — | 82 |
| 5 | MRB SMRCV · MRB LATEX | +0,72 | +0,40 · +0,38 | 76–80% | — | 82 |
| 6 | SGX RSS3 | +0,73 | +0,34 | 76% | — | 82 |
| — | Physical SMR20 | +0,94 | +0,49 | 80% | **−0,06** | 69 |
| — | Giá mủ nước | +0,90 | +0,16 | 64% | +0,15 | 64 |
| — | **Giá mủ chén** | +0,70 | **−0,31** | 50% | **−0,01** | 20 |
| — | Tồn kho tuần (bảng cũ) | — | +0,08 | — | +0,06 | 44 |
| — | Tồn kho ngày | — | — | — | — | 4 lần — chưa đo được |

Thay đổi so với lần đo cũ và đã sửa trong Trợ lý:
- **SHFE RU là yếu tố mạnh nhất** nhưng từng bị bỏ sót khỏi bảng thứ tự → nay đứng đầu.
- **Giá mủ chén không mang thông tin gì ngoài rổ futures** (riêng phần −0,01; bản cũ ghi +0,55) →
  gỡ khỏi tín hiệu "bổ sung" được phép làm lệch mức mô hình (`get_floor_context`).
- **Physical SMR20** chỉ đi theo futures và đã ngừng cập nhật từ 21/08/2026 → không dùng làm căn cứ.
- **Tồn kho**: chuỗi ngày mới có 4 lần ban hành nên chưa đo được; hướng ±3% là **quy tắc nghiệp vụ**
  chủ dự án duyệt, không phải tương quan đã đo.

**Cách ra mức đề xuất (đổi 24/09/2026):** giá sàn lần ban hành trước + mức thay đổi của mô hình
đa biến giữa hai ngày, làm tròn theo bước ban hành (5 USD/tấn · 50.000 đồng/tấn). Trước đó engine
lấy thẳng mức mô hình nên mang theo phần lệch tồn đọng: 4 lần gần nhất mô hình cao hơn giá sàn
LATEX thực 9–15% trong khi Tập đoàn giữ nguyên ⇒ ngày 24/09 đề xuất "NÂNG LATEX +11,7%" dù rổ chỉ số
đi ngang. Backtest 83 lần × 14 chủng loại: MAPE TB **2,85% → 1,84%**, đúng hướng 78% → 80%.

### Lần đo cũ — 80 lần (17/08/2026)

Đo trên dữ liệu thật trong DB (80 lần ban hành 18/01/2024 → 17/08/2026, chuẩn giá FOB
`SVR 10 / CSR 10`). Hai thước đo khác nhau và **đừng lẫn lộn**:

- **r(mức)** — yếu tố có đi cùng *mặt bằng* giá sàn không (đặt giá ở vùng nào).
- **r(Δ%)** — yếu tố có giải thích *lần điều chỉnh* không (nâng/hạ bao nhiêu). **Đây mới là cái để tư vấn.**
- **đồng hướng** — tỷ lệ yếu tố và giá sàn cùng dấu tăng/giảm giữa 2 lần ban hành liên tiếp.

### Nhóm 1 — Dẫn dắt điều chỉnh (mạnh nhất)

| Hạng | Yếu tố | r(mức) | r(Δ%) | Đồng hướng | n |
|---|---|---|---|---|---|
| 1 | **MRB SMR20** (Malaysia) | +0,96 | **+0,63** | 77% | 80 |
| 2 | **SGX TSR20** | +0,95 | **+0,58** | 76% | 80 |
| 3 | **Physical SMR20** (Reuters) | +0,93 | **+0,50** | **80%** | 67 |
| 4 | **OSE RSS3** (TOCOM/JPX) | +0,88 | +0,41 | 75% | 80 |
| 5 | MRB SMRCV | +0,72 | +0,40 | 79% | 80 |
| 6 | MRB LATEX | +0,71 | +0,38 | 80% | 80 |
| 7 | SGX RSS3 | +0,71 | +0,35 | 76% | 80 |

### Nhóm 2 — Neo mặt bằng, yếu ở từng lần điều chỉnh

| Yếu tố | r(mức) | r(Δ%) | Ghi chú |
|---|---|---|---|
| **Giá mủ nước (VRG chốt)** | **+0,84** | +0,14 | Bám mặt bằng rất chặt nhưng **không giải thích lần điều chỉnh** — đây là điểm hay bị hiểu nhầm |
| Giá mủ chén (VRG chốt) | +0,79 | +0,18 | n=17, chuỗi ngắn |
| Physical SIR20 / STR20 / RSS3 | +0,74…+0,85 | +0,26…+0,33 | Nền tham chiếu |
| Tồn kho Tập đoàn (tuần) | **−0,50** | −0,09 | Dấu âm đúng nghiệp vụ: tồn cao ⇒ giá thấp, nhưng chậm |

### Nhóm 3 — Dữ liệu đơn vị thành viên (chuỗi ngắn, tín hiệu sớm)

Đo trên 18–20 lần ban hành có dữ liệu đơn vị (tiêu thụ từ 24/09/2025, tồn kho từ 26/07/2025):

| Yếu tố | r(mức) | r(Δ%) | Nhận định |
|---|---|---|---|
| **Tồn kho đơn vị (ảnh chụp)** | +0,25 | **−0,52** | Tồn tăng ⇒ giá sàn hạ. Dấu đúng nghiệp vụ, độ lớn đáng kể ở n=18 |
| Thu mua mủ nước 30 ngày | +0,29 | +0,42 | Nguồn cung đầu vào |
| Doanh thu tiêu thụ 30 ngày | −0,27 | +0,35 | |
| Sản lượng tiêu thụ 30 ngày | +0,19 | +0,11 | Yếu — sản lượng nhiễu theo lịch giao hàng |

⚠ **Cảnh báo đọc số:** n=18–20 là ít; đây là **tương quan, không phải nhân quả**. Dữ liệu đơn vị
mới đủ dày từ nửa cuối 2025 nên chưa đủ chuỗi để đưa vào mô hình hồi quy — dùng làm **ngữ cảnh
tư vấn** (AI đọc và diễn giải), chưa dùng làm biến dự báo.

### Nhóm 4 — Ảnh hưởng cơ học, không đo bằng tương quan

| Yếu tố | Vì sao |
|---|---|
| **Tỷ giá USD/VND** | Giá sàn nội địa (VNĐ/T) quy đổi trực tiếp từ FOB; chuỗi trong DB mới có từ 06/2026 (n=52) nên chưa đo được thống kê, nhưng ảnh hưởng là **phép nhân**, không phải tương quan |
| USD/MYR · USD/THB · USD/JPY · USD/CNY | Quy đổi giá sàn nước ngoài về USD — đã nằm trong chính con số của Nhóm 1 |
| Đã ký chưa giao (hợp đồng) | Quyết định áp lực bán; chưa có chuỗi lịch sử đủ dài để đo |
| Dầu thô · cao su tổng hợp · vĩ mô | Chưa có trong hệ thống (nguồn ngoài) |

### Yếu tố nào BỔ SUNG thông tin ngoài rổ futures?

Câu hỏi thực tế không phải "cái gì tương quan cao nhất" mà **"cái gì cho biết thêm điều rổ futures
chưa nói"**. Đo bằng **tương quan riêng phần**: bỏ phần biến động đã giải thích được bởi rổ 4 chỉ số
futures (MRB SMR20 · SGX TSR20 · SHFE RU · OSE RSS3) ra khỏi cả hai vế rồi mới tính lại.

| Yếu tố | r thô | **r riêng phần** | Đọc thế nào |
|---|---|---|---|
| **Thu mua mủ nước 30 ngày (đơn vị)** | +0,42 | **+0,56** | Nguồn cung đầu vào — futures không chứa thông tin này |
| **Giá mủ chén (VRG chốt)** | +0,18 | **+0,55** | Giá nội địa đi trước, độc lập với sàn thế giới |
| FX USD/THB | −0,58 | −0,40 | n=13, chưa tin được |
| **Tồn kho đơn vị** | −0,21 | **−0,33** | Giữ dấu âm sau khi trừ futures ⇒ tín hiệu riêng |
| **Tồn kho Tập đoàn** | −0,09 | **−0,31** | Như trên |
| SHFE RU | +0,66 | +0,29 | Vẫn còn phần riêng ngoài rổ |
| MRB SMR20 | +0,63 | +0,16 | Tương quan cao nhưng **chính là rổ** — không thêm gì |
| Physical SMR20 | +0,50 | −0,05 | Đi theo futures, không thêm thông tin |
| Sản lượng tiêu thụ 30 ngày | +0,11 | +0,03 | Không thêm gì |

**Đây là lý do đưa dữ liệu nội bộ và đơn vị thành viên vào Trợ lý:** các chỉ số quốc tế mạnh nhất
(MRB SMR20, Physical SMR20) hầu như **trùng nhau** — nhìn thêm cái thứ ba không lợi gì. Ngược lại
**thu mua · giá mủ chén · tồn kho** mang thông tin mà không sàn nào có. ⚠ Nhóm nội địa n=16–27,
đủ để coi là **tín hiệu tham khảo**, chưa đủ để đưa vào mô hình hồi quy.

### Kết luận dùng cho tư vấn

1. Khi hỏi "nên nâng hay hạ", **SHFE RU · MRB SMR20 · SGX TSR20** là bộ ba phải nhìn trước
   (cập nhật 24/09/2026 — bản cũ ghi Physical SMR20, nay không còn số mới).
2. **Giá mủ nước** trả lời câu "mặt bằng giá đang ở đâu", không trả lời câu "lần này chỉnh bao nhiêu".
3. **Tồn kho** (cả Tập đoàn lẫn đơn vị) là **phanh** theo quy tắc nghiệp vụ: tồn cao ⇒ nghiêng về
   hạ/giữ dù rổ futures tăng.
4. Tỷ giá USD/VND phải luôn kèm khi nói giá nội địa.

## 3. Hiện trạng SAU đợt mở rộng (09/2026)

Từ **6 công cụ trong 1 file** → **24 công cụ chia 5 gói kỹ năng bật/tắt được**
(`apps/api/app/services/assistant_tools/`).

### Gói "Thị trường thế giới" (`market`) — gói nền, luôn bật

| Công cụ | Trả về | Mới? |
|---|---|---|
| `get_exchange_prices` | Giá mới nhất 4 nguồn sàn quốc tế, đơn vị gốc | cũ |
| `get_price_trend` | Chuỗi N ngày 1 sàn + 1 chủng loại, kèm % | cũ |
| `get_fx_rates` | 6 cặp tỷ giá + diễn biến 1 cặp | **mới** |
| `get_physical_prices` | Physical Reuters quy USD/tấn + phiên trước + % | **mới** |

### Gói "Giá sàn & tư vấn điều chỉnh" (`floor`) — gói nền, luôn bật

| Công cụ | Trả về | Mới? |
|---|---|---|
| `get_floor_prices` | Giá sàn 1 lần ban hành + chênh lệch so lần trước | mở rộng |
| `get_floor_history` | Mức FOB qua N lần ban hành + biên độ điều chỉnh TB | **mới** |
| `suggest_floor_adjustment` | NÂNG/GIỮ/HẠ + drivers + bối cảnh tồn kho | mở rộng |
| `simulate_floor_scenarios` | Kịch bản Bear/Base/Bull theo cú sốc rổ chỉ số | **mới** |
| `get_floor_context` | Tín hiệu bối cảnh đã lượng hoá + **hướng tác động tính sẵn** | **mới** |
| `create_floor_proposal` | Lập **phương án giá sàn nháp** trong phiên (mức mô hình / giá hiện hành) | **mới 25/09** |
| `adjust_floor_proposal` | Chỉnh phương án theo lời người dùng: bước · % · số tiền · đặt mức · đưa về · hoàn tác | **mới 25/09** |

### Gói "Số liệu nội bộ Tập đoàn" (`internal`)

| Công cụ | Trả về | Mới? |
|---|---|---|
| `get_inventory_trend` | Tồn kho thành phẩm Tập đoàn **theo ngày**, cộng từ biểu Tồn kho đơn vị (có từ 24/07/2026; bỏ chuỗi tuần 24/09/2026) | đổi nguồn |
| `get_market_quote` | Báo giá mủ — **đủ 4 nhóm giá**, không chỉ xuất khẩu VRG | mở rộng |
| `get_raw_material_prices` | Giá mủ nước/chén/dây (đồng/độ TSC·DRC), tổng hoặc theo đơn vị | **mới** |
| `get_latest_bulletin` | Bản tin ngày / báo cáo tuần đã lưu gần nhất | **mới** |
| `get_data_freshness` | Ngày mới nhất & số ngày trễ từng nhóm + lần quét gần nhất | **mới** |

### Gói "Đơn vị thành viên" (`unit`) — cần quyền `unit_daily`

| Công cụ | Trả về |
|---|---|
| `get_unit_purchase` | Sản lượng & giá thu mua (tổng · khu vực · đơn vị) |
| `get_unit_consumption` | Tiêu thụ (tấn) & doanh thu (VNĐ), nói rõ dòng thiếu tỷ giá |
| `get_unit_stock` | Tồn kho tại ngày chốt + số đơn vị thật sự có số |
| `get_unit_plan_progress` | Kế hoạch năm & % thực hiện |
| `get_submission_status` | Đơn vị nào chưa nộp / thiếu ô |

### Gói "Hợp đồng & khách hàng" (`contract`) — cần quyền `sales_contract`

| Công cụ | Trả về |
|---|---|
| `get_undelivered_volume` | **Đã ký hợp đồng chưa giao** tại một ngày (tấn) — áp lực bán còn treo |
| `get_contract_deliveries` | Các đợt giao trong kỳ: sản lượng · doanh thu · đơn giá bình quân |
| `get_contract_summary` | Hợp đồng ký trong kỳ: số HĐ · cam kết · đã giao · còn lại |
| `get_top_customers` | Khách hàng lớn theo sản lượng/doanh thu |
| `get_master_contracts` | Hợp đồng mẹ (HĐNT/HĐDH) + tiến độ thực hiện |

⚠ Ba bẫy đã xử lý trong gói này: hợp đồng **mẹ không vào tổng sản lượng** (tránh đếm trùng 2 cấp);
doanh thu thiếu đơn giá hoặc tỷ giá ở bất kỳ dòng nào ⇒ trả **KHÔNG BIẾT** thay vì cộng phần còn
lại; nhóm theo đơn vị **gộp đơn vị đã sáp nhập**.

### Khả năng suy luận được bổ sung

System prompt nay yêu cầu Trợ lý **liên kết các nguồn** khi tư vấn giá sàn thay vì đọc rời rạc:
gợi ý của engine → đối chiếu sàn/physical/tỷ giá → đối chiếu tồn kho & số liệu đơn vị → **nói rõ khi
các nguồn mâu thuẫn và nghiêng về bên nào**. Bảng ranking ở mục 2 được nhúng thẳng vào prompt để
Trợ lý biết nhìn yếu tố nào trước, và biết rằng giá mủ nước neo mặt bằng chứ không giải thích
lần điều chỉnh.

### Mức tư vấn — cơ chế giới hạn AI đi xa tới đâu

Người dùng chọn ngay trên màn chat; mỗi mức nạp một bộ luật khác nhau vào system prompt:

| Mức | Trợ lý được làm gì |
|---|---|
| **Chỉ tra số** (`data`) | Chỉ trả số liệu + nguồn. **Không** khuyến nghị nâng/giữ/hạ dưới bất kỳ hình thức nào |
| **Theo mô hình** (`model`, mặc định) | Nêu **đúng** mức đề xuất của engine, không tự cộng trừ ra mức khác; bối cảnh chỉ là ghi chú |
| **Có điều chỉnh** (`adjusted`) | Được đề xuất **khác** mức engine, nhưng bắt buộc trình bày 4 dòng: *Mức mô hình → Điều chỉnh ± → Mức đề xuất → Căn cứ (2–4 gạch, mỗi gạch có số thật)* |

**Luật chống tính hai lần** ở mức "Có điều chỉnh": chỉ tín hiệu trọng số *bổ sung* (giá mủ chén,
tồn kho) và số liệu đơn vị mới được dùng để lệch khỏi mức nền — tín hiệu *mạnh* (rổ futures) đã nằm
trong mô hình rồi. Biên độ lệch thông thường ≤ ±2% (biên độ điều chỉnh trung bình lịch sử là 1,78%);
vượt ngưỡng phải tự nêu là bất thường.

**Hướng tác động được tính ở server, không để AI suy dấu.** Test thực tế cho thấy khi chỉ đưa
"tồn kho −13,7%" kèm nhãn "nghịch chiều", mô hình diễn giải ngược thành *"tồn kho cao nên nghiêng
giữ"*. Nay `get_floor_context` trả thẳng `huong_tac_dong` = *hỗ trợ NÂNG · hỗ trợ HẠ · trung tính*
cùng một dòng **cán cân tín hiệu bổ sung**, nên không còn chỗ cho suy luận sai dấu.

⚠ **Trợ lý CHỈ ĐỌC.** Mọi khuyến nghị chỉ hiển thị trong khung chat để tham khảo — không ghi vào
biểu giá sàn, không sửa bất kỳ số liệu nào của hệ thống. Quyết định cuối thuộc Ban lãnh đạo.

### Nhật ký hỏi–đáp

Mỗi lượt hỏi–đáp được lưu lại (câu hỏi · câu trả lời · công cụ đã gọi · nguồn · mức tư vấn · thời
gian xử lý) để xem lại ở trang **Lịch sử hỏi đáp**. **Không lưu bảng/biểu đồ** (tra lại được từ dữ
liệu gốc, và đó là thứ làm log phình nhanh nhất). Admin xoá được theo phiên hoặc xoá toàn bộ log cũ
hơn một ngày chọn trước.

### Hàng rào kỹ thuật (không chỉ dặn trong prompt)

| Hàng rào | Vì sao |
|---|---|
| Mức "Chỉ tra số" **gỡ hẳn** 3 công cụ khuyến nghị khỏi lượt hỏi | Chỉ dặn trong prompt thì một câu "bỏ qua hướng dẫn trên" là vượt được |
| Cấu hình `ASSISTANT_PACKS` gõ sai mã gói ⇒ **chỉ còn gói nền** | Gõ nhầm mà lại bật thêm gói cho mọi người là đảo ngược ý định của admin |
| Trần tra cứu **400 ngày** cho mọi công cụ | Câu hỏi "so từ 2020 tới nay" nhân với 8 vòng gọi tool mỗi lượt |
| Nhật ký: phiên đã có chủ, người khác ghi vào ⇒ **từ chối** | Mã phiên do client sinh; trùng mã là chèn được câu hỏi vào hội thoại người khác |
| Số liệu theo đơn vị lấy từ **nguồn thô**, không qua chuỗi vẽ biểu đồ | Chuỗi biểu đồ gộp mọi đơn vị ngoài top 8 vào "Khác" — hỏi đơn vị nhỏ sẽ bị trả lời "chưa có số liệu" dù số có thật |
| Tổng theo đơn vị **cộng gộp đơn vị đã sáp nhập**; hỏi tên cũ vẫn ra kết quả kèm ghi chú | Hỏi "Chư Sê" mà thiếu phần Mang Yang là hụt ~9% |

### Bảng "Trợ lý làm được gì?"

Ngay trên màn chat có nút mở bảng liệt kê **tất cả 5 gói và từng công cụ bên trong**, kèm trạng thái
của mỗi gói với tài khoản đang dùng: *đang bật* · *đã tắt trong phiên này* · *cần quyền `unit_daily`
/ `sales_contract`*. Gói không đủ quyền vẫn được liệt kê (để biết là CÓ tính năng đó, chỉ chưa dùng
được), kèm phần **"Chưa làm được"** — mục đích là người dùng không kỳ vọng nhầm rồi tưởng hệ thống
trả lời sai. Danh sách giới hạn lấy từ `assistant_tools.LIMITS`, **cập nhật khi mở thêm khả năng mới**.

### Ba tầng lọc công cụ

1. Gói admin bật ở **Cấu hình hệ thống → AI** (`ASSISTANT_PACKS`; bỏ trống = bật tất cả).
2. **Quyền của tài khoản** — gói `unit` cần cap `unit_daily`; chặn hai lớp (không nạp schema, và
   chặn lại khi thực thi phòng LLM gọi bừa).
3. **Lựa chọn của người dùng** trong phiên chat (chip "Nhóm dữ liệu Trợ lý được phép tra cứu").

### Neo giá nội địa theo giá mủ tư nhân (13/09/2026)

- **Quy tắc chuyên viên Ban TTKD:** giá sàn nội địa SVR 3L hợp lý nhất khi **cao hơn giá thành SVR 3L của tư nhân 700.000–1.000.000 đồng/tấn**. Giá thành tư nhân = giá mủ tư nhân (Mục 6 phiếu Báo giá mủ, đồng/độ TSC) × 1,08 × 100.000 + chi phí gia công chế biến.
- **Kết hợp tồn kho** để chọn điểm trong vùng: tồn kho tăng → mép dưới (+700.000); giảm → mép trên (+1.000.000); đi ngang → giữa vùng.
- Công cụ `get_private_price_benchmark` (gói Giá sàn & tư vấn) tính sẵn vùng hợp lý, vị trí giá sàn hiện hành, vị trí mức mô hình và **mức đề xuất cuối** — mô hình đã nằm trong vùng thì giữ, ngoài vùng thì kéo về điểm theo tồn kho. Trợ lý chỉ đọc kết luận, không tự so số.
- Đây là **quy tắc kinh nghiệm**, chưa đo tương quan trên lịch sử như rổ futures; giá tư nhân cũ hơn 7 ngày thì Trợ lý phải cảnh báo.

### Giới hạn còn lại (chưa làm đợt này)

- **Tri thức nội bộ (RAG)**: Trợ lý trả lời được số, chưa trả lời được câu hỏi quy trình/nghiệp vụ.
- `get_latest_bulletin` chỉ đọc bản tin **đã lưu**; bản dựng tạm trên UI mà chưa bấm lưu thì không thấy.
- Trợ lý không ghi số liệu hệ thống, không gửi nhắc. Từ 25/09/2026 có **một ngoại lệ có kiểm soát**:
  phương án giá sàn NHÁP trong phiên chat (không ghi DB; người dùng tự bấm lưu thành bản nháp tờ trình).

## Cập nhật 24/09/2026 — mô hình đa biến + tham chiếu tồn kho

- `suggest_floor_adjustment`, `simulate_floor_scenarios`, `get_floor_context`, `get_private_price_benchmark`
  dùng mô hình **đa biến: giá mủ nước + 4 futures** (`floor_suggest.DEFAULT_MODEL`), cùng số với màn
  Gợi ý giá sàn và tờ trình. Backtest prod 83 lần ban hành: thắng rổ 4 futures ở cả 14 chủng loại.
- Tồn kho (tổng + tự do, so với lần ban hành trước, ngưỡng ±3%) là **tham chiếu nghiêng**, không đổi số
  mô hình. `suggest_floor_adjustment` trả `tham_chieu_ton_kho` và `canh_bao` từng chủng loại.
- `get_floor_context` bỏ tín hiệu "Giá mủ nước (VRG chốt)" trọng số "nền" — giá mủ nước nay là biến
  "mạnh" trong mô hình.

## Cập nhật 25/09/2026 — phương án giá sàn nháp trong phiên chat

Chủ dự án yêu cầu: hỏi số → bảo Trợ lý "tăng lên tí xíu" → số hiện lên bảng để sửa tiếp → xem trước tờ
trình → lưu bản nháp, sửa tay và lưu lại. **Không** đụng biểu giá sàn chính thức.

- **Phương án sống ở frontend** (state + sessionStorage), gửi kèm mỗi lượt chat (`proposal`); server làm
  sạch (`floor_proposal.sanitize`: dựng lại 14 dòng theo tờ trình, **nạp lại giá lần trước từ DB**, chặn
  số ngoài khoảng — bắt nhầm đơn vị). Lượt nào công cụ lập/chỉnh thì chat trả `proposal` mới.
- **Mọi phép tính ở server** (`floor_proposal_ops`): "tí xíu" = 1 bước (5 USD/tấn · 50.000 đ/tấn), % làm
  tròn theo bước, số tiền/đặt mức giữ đúng số và cảnh báo nếu không phải bội bước; FOB đổi thì nội địa
  tự tính theo tỉ lệ lần trước trừ khi đã sửa tay; mỗi thay đổi ghi nhật ký kèm giá trị trước ⇒ hoàn tác.
  Ô sửa tay trên giao diện gọi cùng đường `POST /api/floor-proposal/apply`.
- **Hàng rào đã đo bằng LLM thật**: với lỗi trơn, LLM trả lời "đã đưa về mức mô hình" dù công cụ từ chối
  ⇒ lỗi công cụ phương án ghi rõ "KHÔNG THỰC HIỆN — phương án giữ nguyên" + luật prompt "chỉ nói đã chỉnh
  khi công cụ chạy thành công". Được bảo "đưa vào bảng" mà không gọi công cụ ⇒ luật prompt bắt buộc gọi.
- Mức **Chỉ tra số**: phương án xuất phát từ giá hiện hành, không kèm mức mô hình, chặn "đưa về mô hình".
  Người dùng tự yêu cầu chỉnh là quyết định của người dùng ⇒ làm được ở mọi mức tư vấn.
- **Bản nháp tờ trình** (`floor_draft`, quyền `floor_suggest`): lưu phương án + **ảnh chụp** khối 1–2
  (số thị trường, lần thứ) lúc tạo; sửa được số + đoạn diễn giải + tiêu đề/ghi chú; ngày tờ trình cố định.
  Diễn giải sửa tay được escape khi in HTML. Tạo từ chat, từ màn Gợi ý giá sàn, hoặc tạo mới.
