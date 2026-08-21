# Changelog Dự án

Ghi nhận thay đổi đáng kể. Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/).

## [Unreleased]
### Added
- **Ba nhóm biểu đồ theo ngày xem được nhiều chiều** (phản hồi 20/08/2026) — gom về họ API
  `/api/series/*` (thu mua · tồn kho · tiêu thụ), tất cả cùng khuôn cột chồng theo ngày:
  - **Thu mua**: mỗi loại mủ (nước · chén) xem theo *Giá & sản lượng* · **Khu vực** · **Đơn vị**.
  - **Tồn kho**: thêm cách xem **Tồn tự do theo chủng loại** = tồn − đã ký hợp đồng, trừ theo TỪNG
    chủng loại của TỪNG đơn vị (cắt trần, không âm) — trả lời "loại nào đang còn bán được".
  - **Tiêu thụ** (biểu đồ mới): sản lượng giao theo ngày chia theo **khu vực · công ty · chủng loại ·
    loại hợp đồng · hình thức hợp đồng**, kèm **đường doanh thu** (tỷ đồng, trục phải). Nguồn là các
    lần giao của hợp đồng bán hàng — cùng số với màn *Thống kê tiêu thụ*; dòng bán USD chưa khai tỷ
    giá thì vẫn tính sản lượng, không tính doanh thu và nói rõ có bao nhiêu dòng như vậy.
  - Nhận định AI của Bản tin biến động có thêm nhóm **Tiêu thụ**.
  - Ghi chú: hệ thống chỉ có số của các đơn vị thành viên VRG, **không có số liệu ngoài Tập đoàn**,
    nên không dựng được biểu đồ "toàn ngành".
### Fixed
- **Bỏ dòng "Độ phủ: 62/67 đơn vị" dưới biểu đồ tồn kho** — con số này nói sai về chính biểu đồ:
  tử số đếm mọi đơn vị có bất kỳ số tồn nào (kể cả đơn vị không có nhà máy, chỉ khai tồn nguyên
  liệu), còn mẫu số 67 là toàn bộ đơn vị đang hoạt động, trong đó 22 đơn vị không có nhà máy nên
  không bao giờ có tồn thành phẩm để khai. Nay chỉ còn một con số duy nhất và đúng, hiện trong
  tooltip: **số đơn vị thật sự có tồn thành phẩm** trong ngày đó.
- **Tồn kho · giá & sản lượng mủ nguyên liệu lấy thẳng từ số đơn vị nhập** (phản hồi 20/08/2026) —
  ba biểu đồ ở *Command Center* và *Bản tin biến động* đổi sang nguồn đơn vị thành viên tự khai:
  - **Tồn kho VRG theo ngày** (thay biểu đồ theo tuần): cộng khối *"Đã nhập kho"* của các đơn vị,
    **3 cách xem** — *Cơ cấu hợp đồng* (đã ký HĐ / tồn tự do) · **Chủng loại** · **Khu vực**. Chuỗi
    bắt đầu **24/07/2026** (ngày đầu tiên đủ đơn vị nhập; trước đó ≤ 12 đơn vị nên không cộng thành
    số Tập đoàn được). Mỗi ngày là **ảnh chụp** (không cộng dồn), đơn vị chưa nhập đúng ngày thì lấy
    số gần nhất trong 7 ngày, và luôn hiện **độ phủ** *n/N đơn vị có số*.
  - **Giá & sản lượng mủ nước · mủ chén**: một khung gồm **cột sản lượng thu mua trong ngày** (trục
    phải) + **dải giá thấp nhất–cao nhất giữa các đơn vị** và đường trung bình. Mủ chén **chuyển
    nguồn** từ phiếu *Báo giá mủ thị trường* sang **số đơn vị tự khai** (phiếu báo giá hay bỏ trống
    mục này) nên nay có cả sản lượng như mủ nước.
  - Mốc đọc số là **ngày gần nhất ĐỦ đơn vị khai**, ngày mới hơn còn thiếu đơn vị được nhắc riêng —
    trước đây lấy thẳng ngày cuối chuỗi thì "sản lượng giảm mạnh" chỉ là chưa ai nhập.
  - **Nhận định AI** của Bản tin biến động dùng đúng nguồn này: nhóm Tồn kho nói thêm **chủng loại**
    và **khu vực** lớn nhất, nhóm mủ nguyên liệu có thêm **sản lượng**.
  - API mới (chỉ đọc, chỉ cần đăng nhập): `GET /api/inventory/series` · `GET /api/prices/purchase-series`.
- **Biểu đồ thu mua mủ hết "giật"** (phản hồi 20/08/2026): ngày không có số hoặc bằng 0 bị **bỏ qua**
  (không vẽ cột 0, không để khoảng trống giữa chuỗi), và dải giá mặc định chỉ tính trên **rổ đơn vị
  khai đều** (đơn vị có giá ≥ 80% số ngày của đơn vị chăm nhất) — có nút *"Tất cả đơn vị"* để xem
  toàn bộ. Trước đó đáy/đỉnh nhảy dựng đứng chỉ vì hôm đó có thêm một đơn vị vùng giá thấp nộp muộn,
  nhìn như giá lao dốc. **Cột sản lượng luôn là tổng của mọi đơn vị** (số cộng, lọc bớt là báo thiếu hàng).
- **Tự động lấy giá mủ nguyên liệu từ đơn vị thành viên** (chốt 20/08/2026) — chuyên viên không phải
  gõ lại con số đơn vị vừa nộp:
  - Nút **"Tự động lấy số từ đơn vị"** ngay trên màn *Giá mủ nguyên liệu*: **công tắc tổng** +
    **chọn từng đơn vị** được lấy tự động. Do **chuyên viên** (quyền `raw_material` mức Sửa) tự bật,
    không phải admin — đây là quyết định nghiệp vụ về việc tin số của đơn vị nào.
  - Bật rồi thì mỗi lần đơn vị **thêm/sửa/xoá** giá mủ nước hoặc mủ chén của mình, ô tương ứng bên
    lưới chuyên viên đổi theo ngay (kể cả khi đơn vị nhập qua biểu Thu mua hay link công khai) —
    móc đặt ở tầng kho giá nên **mọi đường ghi** đều đi qua.
  - Cầu chảy **một chiều** `vrg_unit` → `vrg`: chuyên viên sửa lưới của mình **không** ghi ngược về
    số đơn vị đã khai. Với đơn vị đang bật, **số của đơn vị là số thắng** (ô sửa tay sẽ bị ghi đè ở
    lần đơn vị nộp sau) — muốn giữ số của mình thì bỏ đơn vị đó khỏi danh sách.
  - Nút **"Lấy số đã có (7 ngày gần nhất)"** để kéo nốt các ngày đơn vị đã nộp trước khi bật.
  - **Mặc định TẮT** — không bật thì hai lớp giá vẫn tách hẳn như cũ. Cột đang lấy tự động có dấu
    đồng bộ ở đầu.
- **Quản lý hợp đồng 2 cấp + khách hàng riêng từng đơn vị** (chốt buổi làm việc VRG 30/07/2026) —
  chuyển trục phân hệ báo cáo đơn vị thành viên:
  - **Khách hàng**: danh mục **riêng của từng đơn vị**, không dùng chung cấp Tập đoàn; hợp đồng chỉ
    gán được khách của chính đơn vị đó. Khách đã gắn hợp đồng chỉ ẩn được, không xoá.
  - **Hợp đồng 2 cấp**: hợp đồng mẹ có **loại giao** *Giao 1 lần* hoặc *Giao nhiều lần*. Loại nhiều
    lần: mẹ giữ tổng sản lượng cam kết, nhập **phụ lục** đến khi hết. **Mỗi phụ lục = một lần giao
    (tự chuyển ĐÃ GIAO) + một lần thanh toán**; hệ thống chặn phụ lục vượt sản lượng còn lại của mẹ.
  - **Tiêu thụ và "đã ký HĐ chưa giao" (khối 3) BỎ KHỎI nhập liệu** — hệ thống tự tính từ các lần
    giao (tiêu thụ = tổng đã giao; khối 3 = cam kết − đã giao **tại ngày báo cáo**). Khối 3 vẫn là
    phần **nằm trong** tồn kho thành phẩm: không cộng thêm, không trừ ra.
  - **Hình thức tiêu thụ**: Xuất khẩu/UTXK · Tiêu thụ trong nước · **Tiêu thụ nội bộ** (dùng đúng
    thuật ngữ này, không dùng "nội tiêu"); dòng nội bộ ghi rõ đơn vị nhận.
  - **Cây công ty mẹ – con** (`Đơn vị thành viên` thêm cột *Công ty mẹ*) + ô **chi phí tổng cấp công
    ty mẹ** ở biểu Tồn kho. Cố ý **không đối soát** với tổng chi phí dòng con — mẹ tự tính, tự chịu.
  - **Quy khô bắt buộc** khi bán LATEX và 2 loại mủ nguyên liệu; **chi phí trên từng dòng bán**;
    **loại tiền mở rộng** VND · USD · **LAK · KHR** (nội tệ đơn vị Lào/Campuchia, buộc có tỷ giá).
  - **Tái cấu trúc menu** theo trục mới: *Số liệu thị trường (tự động/thủ công)* · *Số liệu đơn vị
    thành viên* · *Quản lý hợp đồng* · *Báo cáo & Thống kê* · *Phân tích & Bản tin*.
  - Quyền mới `sales_contract` (2 cấp Xem/Sửa). **Hậu-deploy phải cấp lại quyền này** cho chuyên viên.
- Script chuyển dữ liệu cũ `scripts/migrate-sales-contracts.py` (mặc định chạy thử; `--commit` mới
  ghi). **Không xoá, không sửa dữ liệu cũ**: hợp đồng tồn kho cũ và từng dòng tiêu thụ đã khai được
  sao sang cấu trúc mới, bản gốc giữ nguyên và được đánh dấu để **không bị đếm hai lần**. Ngày nào có
  dòng thiếu chủng loại/số lượng thì **bỏ qua cả ngày** và in ra để rà tay — không suy diễn số liệu.

### Removed
- **Bỏ 2 chỉ tiêu thu mua mủ nguyên liệu** *Mủ NL nước chưa cán vắt (chén)* và *Mủ NL đã cán vắt
  (RSS)* (khách chốt 14/08/2026 — đơn vị **không thu mua** 2 loại này; chúng được thêm ngày
  30/07/2026 rồi bỏ). Gỡ khỏi **cả** biểu nhập Thu mua, bảng tổng hợp, báo cáo kỳ, Excel báo cáo
  kỳ, màn Thống kê thu mua và Excel thống kê.
  - **Không mất số liệu**: đo trên prod trước khi bỏ — 5.828 bản ghi thu mua, đúng **1** bản ghi
    từng chạm 2 khoá này và giá trị đều là **0** (ngày không phát sinh), không có đơn giá nào.
  - ⚠ **Hai tên đó VẪN là chủng loại BÁN hợp lệ** (`market_meta.RAW_MATERIAL_GRADES`: danh mục chủng
    loại dùng chung + quy khô bắt buộc) — prod đang có **39 hợp đồng** bán 2 loại này. Chỉ bỏ ô
    THU MUA, tuyệt đối không gỡ khỏi danh mục chủng loại.

### Changed
- **Cảnh báo "ô cần kiểm tra" ra thẳng bảng việc đầu màn của đơn vị** (19/08/2026) — trước đây bộ
  cảnh báo nhầm-đơn-vị-tính chỉ chạy **trong form lúc đang nhập**: lưu xong đóng form là không ai
  thấy nữa, còn con số sai vẫn nằm im và chảy vào báo cáo tổng hợp. Nay server rà lại **số đã lưu**
  (`member_data_check`, rà từ đầu năm) và đưa lên bảng nhắc việc: biểu Thu mua · Tồn kho · đơn giá
  mủ nguyên liệu · đơn giá trên hợp đồng. Mỗi ô nói rõ **ngày · bảng · dòng · cột + lý do**, bấm vào
  mở đúng phiếu; ô ngoài cửa sổ sửa để **chữ xám** kèm nhắc báo Ban TTKD. Bộ biên dùng **chung một
  bộ số** với form (`app/core/entry_bounds.py` ↔ `entry-bounds.ts`, test khoá 2 bên không lệch).
  Hai tinh chỉnh kèm theo để cảnh báo không kêu oan: **chủng loại "gom"** (*Chủng loại khác*, *Mủ
  ngoại lệ*) không áp biên đơn giá (mủ tạp bán 0,7–2,8 triệu đ/tấn là thật), và biểu Tồn kho **thôi
  soát 2 mảng tiêu thụ cũ** `sales`/`sales_own` — form đã không hiện chúng từ 30/07/2026, nhắc ô
  người dùng không nhìn thấy là bắt họ đi tìm một ô không tồn tại (một phiếu cũ đang báo tới 9 ô).
- **Quy khô thành ô BẮT BUỘC ở mọi lần lưu hợp đồng** (siết lại đúng chốt Q4 — 19/08/2026) — trước
  đây chỉ ép khi bản ghi **đã giao**, nên phần cam kết của hợp đồng giao-nhiều-lần vào sổ bằng số
  **mủ nước** còn phần đã giao bằng số **khô**: khối *"đã ký HĐ chưa giao"* thành hiệu của hai đơn
  vị tính khác nhau. Nay bán **LATEX** và 2 loại mủ nguyên liệu là phải khai quy khô mới lưu được —
  tạo mới lẫn sửa, hợp đồng lẫn đợt giao, đã giao hay chưa. Bản ghi cũ thiếu quy khô (211 dòng /
  204 bản ghi ở 6 đơn vị, phần lớn do script chuyển dữ liệu cũ tạo ra) **bị chặn khi mở ra sửa** cho
  tới khi bổ sung — hệ thống không tự suy ra hộ một con số đơn vị chưa khai.
- **Báo cáo tiêu thụ · Xuất Excel nay ra 2 sheet**: tổng hợp theo đơn vị (như cũ) + **Chi tiết lần
  giao** — mỗi **dòng bán** một dòng, 20 cột (ngày giao · đơn vị · số HĐ · đợt · khách hàng · loại HĐ
  · hình thức · chủng loại · mủ nước / quy khô / SL tính tiêu thụ · đơn giá · loại tiền · tỷ giá ·
  thành tiền · doanh thu · hoá đơn · ngày thanh toán · mã bản ghi), **bật sẵn bộ lọc của Excel**.
  Cộng cột *SL tính tiêu thụ* luôn khớp sản lượng của sheet tổng hợp (cùng nguồn, cùng bộ lọc).
- **Thống kê tồn kho đổi trục từ "kỳ báo cáo" sang "NGÀY CHỐT"** — tồn kho là số **thời điểm** nên
  "tổng của một khoảng ngày" vốn không có nghĩa; trục cũ làm số hiển thị sai lệch nặng (đo trên
  prod 10/08/2026: kỳ mặc định *Tuần này* rơi đúng Thứ 2 → chỉ 4/52 đơn vị đã nhập → **250,8 tấn**
  thay vì ~**100.000 tấn**):
  - Chọn **1 ngày chốt** + **số cũ tối đa N ngày** (mặc định 7): mỗi đơn vị lấy bản ghi tồn **mới
    nhất ≤ ngày chốt**; cũ quá hạn thì coi như **chưa có số**, không lấy đại số cũ đắp vào.
  - Mỗi dòng luôn kèm **Ngày lấy số** + **Số cũ (ngày)** — không nơi nào được hiểu số cũ là số của
    đúng ngày chốt.
  - **Dải độ phủ** đầu bảng + cảnh báo: *x/y đơn vị có số · đơn vị nào số cũ · đơn vị nào chưa nhập*
    (trước đây chỉ cảnh báo khi người dùng tự chọn đơn vị ở bộ lọc → xem toàn Tập đoàn là thiếu đơn
    vị mà không hề biết). Đơn vị khai *"không phát sinh tồn kho"* tách thành nhóm riêng: **đã nộp**
    nhưng không có số để cộng — không đếm thành thiếu, cũng không tự suy thành tồn = 0.
  - **Dòng Tổng cộng khi nhóm theo NGÀY** nay là ảnh chụp tại ngày chốt (mỗi đơn vị lấy số mới nhất
    của mình) thay vì chỉ gom các đơn vị nhập đúng **ngày cuối cùng có dữ liệu** — bẫy cũ làm rơi
    khỏi tổng mọi đơn vị nhập sớm hơn, kể cả khi thẻ KPI đầu màn đọc chính con số đó.
  - API đổi tham số: `GET /api/unit-daily/analytics/stock[.xlsx]?as_of=&max_age_days=` (bỏ
    `date_from`/`date_to`). Các màn Thu mua · Tiêu thụ · Theo dõi nộp báo cáo giữ nguyên trục kỳ.
- **Tách kho "Giá mủ nguyên liệu" làm 2 lớp theo người nhập** — trước đây chuyên viên và đơn vị
  thành viên ghi chung một ô nên đơn vị lưu biểu Thu mua là **đè mất số chuyên viên đã chốt**
  (chuyên viên thấy "giá nhảy loạn xạ", có ngày lên 53.500 do đơn vị nhập sai đơn vị tính):
  - `source='vrg'` — giá **chuyên viên** chốt: lưới *Giá mủ nguyên liệu*, **bản tin ngày**,
    **báo cáo tuần III.3**, **gợi ý giá sàn**, Báo giá mủ thị trường Mục 5.
  - `source='vrg_unit'` — giá **đơn vị tự khai**: biểu *Báo cáo thu mua*, link công khai
    `/nhap-gia-mu`, màn giá của đơn vị, và **giá BQ ở Thống kê thu mua + Báo cáo tổng hợp**
    (khớp với sản lượng cũng do đơn vị khai).
  - Đổi tên đơn vị chuyển theo cả hai lớp. Migration prod: 205 ô có dấu vết đơn vị ghi được
    chuyển sang lớp đơn vị; 57 ô bị ghi đè được **trả lại số chuyên viên trước khi bị đè**
    (lấy từ Nhật ký hoạt động); ô cũ không truy được tác giả giữ nguyên bên chuyên viên.
### Added
- **Drill-down nhiều lớp cho 3 màn Thống kê** — bấm vào dòng (hoặc cột trong biểu đồ) để đi sâu:
  `Toàn Tập đoàn → Khu vực → Công ty → Ngày → chi tiết` (thu mua: loại mủ · tiêu thụ: từng dòng bán ·
  tồn kho: chủng loại). Đường dẫn phía trên bảng để quay lại lớp bất kỳ; mỗi lớp có **thẻ KPI tổng**
  + **biểu đồ cột** của lớp đang xem. Bộ lọc người dùng chọn được giữ nguyên và áp chồng lên nhánh
  đang mở. Tồn kho thêm cách nhóm **theo ngày** (mỗi ngày là ảnh chụp riêng; dòng Tổng cộng lấy ngày
  cuối, KHÔNG cộng dồn — có cảnh báo ghi rõ).
- **Thống kê / kiểm tra số liệu đơn vị nhập** (4 màn mới, quyền `unit_daily` mức Xem):
  - `Thống kê thu mua` — lọc đơn vị · khu vực · kỳ · loại mủ (mủ nước/mủ chén/thành phẩm) ·
    chủng loại; chân bảng có Tổng sản lượng + **3 đơn giá BQ tách riêng theo đơn vị tính**
    (mủ nước & mủ chén = đồng/độ, thành phẩm = triệu đ/tấn), tất cả BQ **gia quyền theo sản lượng**.
  - `Thống kê tiêu thụ` (tách khỏi tồn kho) — lọc thêm loại HĐ · hình thức HĐ · **nguồn mủ**
    (mủ thu mua / mủ khai thác); có chế độ **Chi tiết từng dòng** để đối chiếu chứng từ.
  - `Thống kê tồn kho` — số **thời điểm**: lấy ngày cuối cùng có nhập tồn của TỪNG đơn vị, hiện rõ
    cột *Ngày lấy số*; nhóm gồm nhiều ngày thì để trống thay vì hiện một ngày (tránh hiểu sai).
  - `Theo dõi nộp báo cáo` — ma trận đơn vị × ngày (đã nhập / không tổ chức thu mua / chưa nhập) + KPI.
  - API `GET /api/unit-daily/analytics/{filters,purchase,consumption,stock,status}` + bản `.xlsx`
    xuất đúng bộ lọc đang xem. `Thống kê hợp đồng` bổ sung lọc **khu vực + chủng loại** và cột Khu vực.
- **Cảnh báo nhập liệu bất thường** trên mọi màn nhập báo cáo ngày: ô nghi sai đơn vị tính / lệch
  quá xa kỳ trước được tô viền + banner "N ô cần kiểm tra" chỉ rõ bảng·dòng·cột. Biên lấy từ dữ liệu
  thật trên production rồi nới rộng — **chỉ cảnh báo, không chặn gõ/lưu, không đổi số liệu**.
- Danh sách báo cáo ngày (timeline) chọn được **khoảng ngày tự chọn**, ngoài các mốc 30/60/90/180 ngày.
### Fixed
- **Doanh thu tiêu thụ của bản ghi cũ bị sai 1.000 lần**: dòng bán lưu trước khi có loại tiền theo
  từng dòng (`ccy` rỗng) bị đọc thành VNĐ, khiến giá 1.640 USD/tấn thành 1.640 triệu đ/tấn. Nay
  lấy loại tiền mức ngày (`sales_ccy`/`fx_revenue`), thiếu nữa thì theo đơn vị (nước ngoài = USD).
- Màn thống kê tiêu thụ **cảnh báo** khi doanh thu đã lưu của ngày lệch >1% so với tổng các dòng bán
  (dấu hiệu đổi loại tiền sau khi lưu) — chỉ báo để rà lại, không tự sửa dữ liệu gốc.
- **Đổi tên đơn vị thành viên** nay chuyển theo MỌI dữ liệu gắn theo tên đơn vị (báo cáo ngày, hợp
  đồng tồn kho, kế hoạch năm, nhu cầu thị trường, danh sách đơn vị của tài khoản) — trước chỉ chuyển
  giá mủ nguyên liệu nên các bảng còn lại thành mồ côi và đơn vị **mất quyền vào chính đơn vị mình**.
- **Nhật ký hoạt động (audit log)** — ghi vết MỌI thay đổi số liệu: ai · lúc nào · bản ghi nào ·
  giá trị trước → sau. Bảng `audit_log` độc lập (không ghi đè), gắn ở tầng repo nên bao phủ mọi lối
  vào: màn chuyên viên, màn đơn vị thành viên, nhập từ file Excel, link công khai, job tự chạy.
  API `GET /api/audit` (chỉ đọc) + màn **Quản trị → Nhật ký hoạt động**, quyền mới `audit`.
  Không lưu mật khẩu/secret; xoá bản ghi vẫn giữ nguyên giá trị cũ trong nhật ký.
- Khởi tạo cấu trúc repo (scaffold) cho Đề án A — AI Dự báo Giá Cao su.
- `AGENTS.md` (chuẩn chung Claude + Antigravity) + `CLAUDE.md` import.
- Khung `knowledge/` (Markdown + YAML frontmatter) — tri thức dùng chung cho agent & RAG.
- Tài liệu kiến trúc (`docs/architecture/`) + quản trị dự án (`docs/project/`).
- `.env.example`, cập nhật `.gitignore` (bảo vệ dữ liệu mật VRG).
- **Skeleton chạy được** (verified): `apps/api` (FastAPI/uv — pytest 2 passed, ruff clean, HTTP `/health` OK), `apps/web` (React+TS+Vite/pnpm — `pnpm build` OK), `infra/docker` (TimescaleDB+pgvector — `compose config` hợp lệ).
- **Knowledge nghiệp vụ** (`knowledge/business-process/`): quy trình báo cáo tuần/năm, cấu trúc giá Physical, báo cáo ký kết HĐ, bản tin phân tích tuần — trích xuất từ biểu mẫu thật.
- **Plan Sprint 1** (`plans/260615-sprint-01-dashboard-mvp/`): Dashboard MVP + crawler 4 sàn.

### Notes
- Skeleton verified chạy được; chưa cài heavy ML libs (Prophet/XGBoost/LSTM) — bổ sung ở Sprint 2.
- pnpm 11 cần `apps/web/pnpm-workspace.yaml` → `allowBuilds: esbuild: true` để build tự động.
- Dữ liệu mật (`docs/data/`, `docs/bieu-mau/`, `data/raw/`) giữ local, không commit.
