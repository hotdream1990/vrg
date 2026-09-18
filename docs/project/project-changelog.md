# Changelog Dự án

Ghi nhận thay đổi đáng kể. Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/).

## [Unreleased]
### Added
- **Nhu cầu thị trường nhập theo phiếu có trường** (17/09/2026) — thay cho ô chữ tự do theo ngày.
  - Mỗi dòng là **một nhu cầu của một chủng loại**: ngày nhận · khách hàng · chủng loại · số lượng
    (tấn/container) · đơn giá (triệu đ/tấn hoặc USD/tấn) · giao tại · thời gian giao · kết quả ·
    ghi chú. Khách hỏi 2 loại thì bấm *Nhân bản*.
  - **Thời gian giao** và **Kết quả** gõ tự do (vd "Đến 30/11/2026", "Đã ký HĐMB số 1752 ngày
    17/09/2026"). Kết quả và ghi chú **sửa được cả khi ngày nhận đã khoá**; sửa nội dung khác của
    phiếu cũ thì gửi *Đề nghị sửa số liệu*.
  - Màn tổng hợp lọc theo đơn vị, chủng loại, tìm theo khách/kết quả/ghi chú.
  - Dữ liệu cũ (34 bản ghi chữ, 6 đơn vị) chuyển thành 67 phiếu; nguyên văn cũ giữ trong Ghi chú.
  - Bản 0.4.74 từng có tình trạng · số hợp đồng · ngày ký · giá tạm tính · giao từ–đến ngày; chủ dự án
    thấy rắc rối nên rút gọn ngay trong ngày — số đã nhập được gộp thành chữ khi khởi động.
- **Lãnh đạo đơn vị xem Cảnh báo bất thường của đơn vị mình** (17/09/2026) — mục mới ngay dưới
  *Hỗ trợ & Thông báo* trong menu lãnh đạo đơn vị: thấy nhân viên nhập liệu đang sai/thiếu gì (giá
  bán hoặc giá mủ sai đơn vị tính · chưa nộp biểu · ngừng nộp nhiều ngày · thiếu đơn giá · kế hoạch
  năm khai thiếu · chưa gộp tồn kho sau sáp nhập) để nhắc đúng việc.
  - Chỉ thấy các đơn vị được gán cho tài khoản, cộng đơn vị đã sáp nhập vào đơn vị mình — máy chủ
    tự lọc. Không có nhóm *Doanh thu một ngày bất thường* (tính trên số gộp cả Tập đoàn), không có
    *Cấu hình ngưỡng*, không có *Đăng nhập hộ*.
  - Vẫn dùng được *Xuất Excel* và *Chế độ chụp* để gửi cho nhân viên.
  - Sổ tay lãnh đạo đơn vị (`docs/huong-dan/lanh-dao-don-vi/`) thêm mục 9 *Cảnh báo bất thường*,
    chụp lại toàn bộ ảnh theo menu mới, cập nhật mục *Những tình huống hay gặp*.
- **Mô tả các nhóm cảnh báo viết lại cho dễ hiểu** (17/09/2026) — bỏ tên bảng/cột kỹ thuật, ngày ghi
  DD/MM/YYYY, số có dấu chấm ngăn nghìn; áp cho cả màn quản trị và file Excel.
- **Lịch sử truy cập** (16/09/2026) — Quản trị → *Lịch sử truy cập*: theo dõi **ai đăng nhập lúc
  nào và vào những trang nào**, để biết tài khoản đã cấp (nhất là lãnh đạo đơn vị thành viên) có
  thực sự được dùng hay không.
  - **Tab "Theo tài khoản"**: đăng nhập gần nhất · hoạt động gần nhất · số lần đăng nhập (kèm số
    lần gõ sai mật khẩu) · số lượt xem trang · số ngày hoạt động · trang hay vào nhất. Kèm bảng
    *Trang được xem nhiều nhất*.
  - Bảng này liệt kê **cả tài khoản chưa truy cập lần nào** (ghi rõ bằng chữ đỏ) — biết ai được cấp
    tài khoản mà không dùng mới là điều đáng giá nhất. Ô lọc *Tài khoản* cũng liệt kê đủ mọi tài
    khoản, không chỉ người đã có vết.
  - Lượt quản trị **"đăng nhập hộ"** không tính vào thống kê sử dụng của chủ tài khoản (tab *Chi
    tiết* vẫn hiện đủ, ghi rõ ai đăng nhập hộ ai) — tính cả vào thì tưởng người ta đang dùng.
  - **Tab "Chi tiết lượt truy cập"**: từng lượt đăng nhập / vào trang, có tên trang tiếng Việt,
    đơn vị, IP và ghi rõ khi quản trị đang "đăng nhập hộ".
  - Lọc theo khoảng ngày · tài khoản · vai trò · đơn vị · loại sự kiện, xuất Excel 2 sheet.
  - Chỉ ghi **trang đã mở**, không ghi nội dung/bộ lọc đang xem. Lưu 400 ngày, tự dọn phần cũ hơn.
  - Xem được khi có quyền *Nhật ký hoạt động + Lịch sử truy cập* (`audit`); quản trị viên mặc định có.
  - ⚠ Không hồi tố: lịch sử chỉ tính từ ngày bản này lên máy chủ.
- **Giá mủ tư nhân** (13/09/2026) — Báo giá mủ thị trường bỏ mục 6 "Giá mủ khu vực" (số mủ nước/mủ
  chén của đơn vị nay lấy thẳng từ đơn vị), thay bằng mục 6 **"Giá mủ tư nhân"**:
  - Mỗi đơn vị tư nhân nhập **một giá** hoặc **khoảng giá** (Giá – Giá max, đồng/độ TSC). Giá max nhỏ
    hơn Giá thì báo đỏ và tạm không lưu.
  - Danh mục đơn vị tư nhân dùng chung mọi phiếu: chuyên viên **thêm** được, chỉ quản trị viên **xoá**
    được; xoá khỏi danh mục không mất giá ở phiếu cũ.
  - Cột **Giá thành SVR 3L** tự tính = giá mủ × 1,08 × 100.000 + chi phí gia công chế biến (mặc định
    2.000.000 đồng/tấn, sửa theo phiếu) — theo công thức chuyên viên.
  - Tài khoản chỉ có quyền "Giá mủ nguyên liệu" không còn vào màn Báo giá.
- **Dashboard: khối "Giá mủ tư nhân"** (13/09/2026) — giá mới nhất của từng đơn vị trong 14 ngày (có
  ngày giá), so với lần báo trước, giá thành SVR 3L, vùng giá sàn hợp lý (giá thành + 700.000–1.000.000)
  và chênh lệch với giá sàn nội địa SVR 3L hiện hành.
- **Trợ lý AI tư vấn giá sàn theo giá mủ tư nhân + tồn kho** (13/09/2026) — theo chuyên viên, giá sàn
  nội địa SVR 3L hợp lý khi cao hơn giá thành tư nhân 700.000–1.000.000 đồng/tấn; tồn kho tăng chọn
  mép dưới, giảm chọn mép trên. Mức "Có điều chỉnh" được kéo mức mô hình về vùng này; mức "Theo mô
  hình" giữ nguyên số mô hình, chỉ ghi chú vị trí; mức "Chỉ tra số" liệt kê giá tư nhân từng đơn vị.
- **Vai trò "Lãnh đạo Tập đoàn"** (13/09/2026) — tài khoản cho lãnh đạo cấp Tập đoàn: xem được mọi
  báo cáo, thống kê, số liệu, hợp đồng và dùng Trợ lý AI như quản trị viên, nhưng **chỉ xem**.
  - Menu riêng, xếp phần hay dùng lên đầu: Phân tích & Bản tin (Trợ lý AI, Gợi ý giá sàn, Bản tin
    biến động, Bản tin ngày, Báo cáo tuần) → Báo cáo & Thống kê → Số liệu thị trường / đơn vị /
    hợp đồng (ghi rõ "chỉ xem").
  - Không có phần kỹ thuật & vận hành: Quét đa sàn, Chốt số liệu, danh mục Đơn vị thành viên,
    Hỗ trợ & Thông báo, Nhật ký hoạt động, Quản trị.
  - Vẫn dùng được: hỏi Trợ lý AI, bấm "Tạo nhận định bằng AI", đổi mật khẩu, sửa hồ sơ. Mọi thao
    tác nhập/sửa/xoá khác bị chặn ở máy chủ, kể cả khi gọi thẳng API.
  - Tạo ở Quản trị → Người dùng, chọn vai trò "Lãnh đạo Tập đoàn" — không cần tích quyền.
- **Sổ tay Lãnh đạo Tập đoàn** (13/09/2026) — `docs/huong-dan/lanh-dao-tap-doan/`, 21 mục, 20 ảnh
  chú thích, bản Word.

### Security
- **Nút “Hoàn thành hợp đồng” không còn lách được cửa sổ nhập liệu và chốt số liệu** (17/09/2026) —
  hợp đồng giao 1 lần chưa có ngày giao, khi bấm Hoàn thành hệ thống ghi luôn ngày giao; trước đây
  bước này không bị kiểm nên đơn vị ghi được ngày giao lùi (kể cả vào kỳ đã chốt) dù cửa sổ đặt 0
  ngày. Nay ngày giao đó phải qua đúng hai hàng rào như khi nhập đợt giao thường; bị chặn thì gửi
  *Đề nghị sửa số liệu*.
- **File Excel Cảnh báo bất thường** chặn công thức Excel ở ô chữ do đơn vị nhập (mã hợp đồng…),
  vì file nay đến tay cả lãnh đạo đơn vị.

### Fixed
- **Đề nghị sửa hợp đồng trùng số không còn lọt tới lúc Ban duyệt** (18/09/2026) — hai đề nghị
  (#36 Dầu Tiếng Campuchia, #51 Lai Châu II) bấm Duyệt là báo "đã có đợt giao/hợp đồng số …": đơn
  vị bấm **Thêm** rồi gõ lại số của một đợt/hợp đồng đã có, nhưng hệ thống kiểm hạn nhập TRƯỚC khi
  kiểm trùng nên mời gửi đề nghị luôn.
  - Lưu hợp đồng/đợt giao nay kiểm **luật nghiệp vụ trước hạn nhập**: trùng số, vượt 110% sản lượng,
    thêm đợt vào hợp đồng giao 1 lần… báo đỏ ngay trên biểu. Gửi đề nghị cũng kiểm đúng bộ luật đó.
  - Câu báo trùng nêu bản ghi đang có (ngày giao · sản lượng) và phân biệt **thêm mới** (đặt số
    khác, hoặc mở bản ghi cũ để sửa) với **sửa đổi sang số đã có**.
  - **Sửa mà giữ nguyên số thì không kiểm trùng nữa** — 20 hợp đồng cũ trên prod trùng số sẵn
    (3 nhóm) trước đây sửa ô nào cũng bị báo trùng.
  - Thêm đợt giao kiểm **hợp đồng cha thuộc đúng đơn vị trước** khi báo trùng — câu báo nay nêu ngày
    giao · sản lượng, kiểm sau thì đoán mã hợp đồng của đơn vị khác là đọc được số của họ.
  - Trang duyệt: thẻ **Thêm mới / Sửa / Xoá**, cột trống ghi "(chưa có)" khi thêm mới; đề nghị
    không duyệt được thì báo trước bằng khung đỏ và làm mờ nút Duyệt. Sổ tay duyệt và sổ tay đơn vị
    cập nhật theo.
- **Cảnh báo *Giá bán sai đơn vị tính* không còn ghi “Thiếu tỷ giá: Có” cho hợp đồng VND**
  (17/09/2026) — tiền Việt không cần tỷ giá; cột này nay chỉ đánh dấu dòng ngoại tệ chưa có tỷ giá.
- **Người chỉ xem tải được PDF Báo cáo tuần** (13/09/2026) — trước đây nút "Xuất PDF" lưu báo cáo
  rồi mới xuất, nên tài khoản chỉ xem (Lãnh đạo Tập đoàn…) bấm là báo lỗi. Nay xuất thẳng bản đã lưu.
- **Màn Thống kê và Theo dõi nộp báo cáo hiện đúng kỳ vừa chọn** (13/09/2026) — đổi kỳ nhanh trong
  lúc bảng đang tải thì kết quả của kỳ cũ về sau đè lên: nút ghi "Tháng trước" mà số liệu là của
  "Tuần này". Nay chỉ hiện kết quả của lần chọn mới nhất.
- **Giá sàn Tập đoàn**: người chỉ xem thấy tiêu đề "Biểu giá" thay vì "Sửa biểu giá".
- **Thôi nhắc "chưa nhập đơn giá" với ngày đơn vị đã khai là KHÔNG CÓ GIÁ** (07/09/2026) — đơn vị
  báo: những ngày chỉ có *sản lượng chênh lệch sau chế biến* thì không có giá, Ban đã thống nhất
  nhập 0, vậy mà ảnh đốc thúc vẫn ghi "chưa nhập đơn giá".
  - Gốc vấn đề: đơn giá 0 **không được lưu thành một mức giá** (để không kéo tụt giá bình quân và
    không lọt vào bản tin) nên sau khi lưu không còn dấu vết — hệ thống không phân biệt được "quên
    khai" với "đã khai là không có giá".
  - Nay lời khai được giữ lại bằng cờ trong phiếu; mở phiếu ra **ô đơn giá hiện lại số 0** thay vì
    trắng trơn như trước. Bản ghi CŨ của đơn vị nước ngoài (đơn giá nội tệ = 0) cũng được đọc như
    một lời khai nên **không phải nhập lại**.
  - Ảnh đốc thúc và cảnh báo trong báo cáo Thu mua thôi nhắc những ngày đó, chuyển sang câu ghi
    nhận đúng bản chất: *"N ngày đơn vị khai không có đơn giá"*. Ngày chưa nói gì về giá thì vẫn
    nhắc như cũ.
  - Đo trên dữ liệu thật: 11 ngày bị nhắc oan ở 5 đơn vị → còn 6 ngày (những ngày thật sự chưa
    khai gì). Giá bình quân · bản tin · báo cáo **không đổi** — số 0 vẫn không vào kho giá.

### Changed
- **Cảnh báo "Chưa nộp / thiếu một phần" ghi rõ ngày thiếu** (17/09/2026) — trước chỉ ghi
  "2/55 ngày thiếu", người đọc không biết phải nhắc ngày nào; biểu đủ cũng hiện "0/259 ngày thiếu".
  - Nay mỗi biểu có 2 cột: *Thiếu N/T ngày* (hoặc *Đủ*) và *Ngày thiếu*, ngày liền nhau gộp thành
    đoạn (vd "24/05, 21/08–16/09"). Áp cho cả màn quản trị, màn lãnh đạo đơn vị và file Excel.
  - Đổi tên cột "Biểu Tiêu thụ–Tồn kho" thành **Tồn kho** cho khớp menu *Tồn kho (theo ngày)*.
  - Sổ tay lãnh đạo đơn vị: chụp lại ảnh 17.
- **Cấu hình › Cửa sổ nhập liệu ghi rõ phạm vi và cách tính** (17/09/2026) — ô của đơn vị thành
  viên đổi nhãn thành “Thu mua · Tồn kho · Giá mủ · Nhu cầu thị trường · ngày giao hợp đồng” (nhãn cũ
  chỉ ghi “Giá mủ đơn vị”), gợi ý “0 = chỉ hôm nay · 1 = hôm nay và hôm qua”. Câu báo khi bị chặn
  đổi thành “chỉ được nhập/sửa hôm nay” / “hôm nay và N ngày trước” thay cho “trong N ngày gần
  nhất” (đặt 0 từng ra câu “trong 0 ngày”).
- **Đơn vị đang bật "tự động lấy số" thì chuyên viên chỉ xem, không sửa được** (06/09/2026) —
  trước đây chuyên viên vẫn gõ đè được ô của những đơn vị này, nhưng lần đơn vị nộp sau lại ghi đè
  ngược, nên con số nhìn thấy tuỳ thuộc ai ghi sau cùng. Nay khoá hẳn:
  - Lưới **Giá mủ nguyên liệu**: cột của đơn vị đang bật cầu chuyển sang **chỉ xem** (vẫn có dấu
    đồng bộ ở đầu cột để biết vì sao).
  - **Xoá cả ngày** chỉ dọn ô chuyên viên tự nhập, **giữ nguyên** số của đơn vị đang lấy tự động —
    xoá sạch thì bản tin mất số cho tới lần đơn vị nộp kế tiếp.
  - Bịt luôn **cửa sau**: Mục 6 màn *Báo giá mủ thị trường* cũng khoá dòng của các đơn vị đó (bỏ
    qua khi lưu, không báo lỗi — màn này tự động lưu, ném lỗi là mất cả phiếu vì một ô).
  - Chặn ở **tầng dữ liệu** chứ không chỉ ẩn nút: gọi thẳng API cũng bị từ chối, kèm câu chỉ rõ
    cách mở khoá (bỏ đơn vị khỏi danh sách ở nút *Tự động lấy số từ đơn vị*).
  - Đơn vị **không chọn** vẫn nhập tay như cũ.

### Changed
- **Mỗi thẻ hỗ trợ = MỘT trường hợp, khép rồi là khép hẳn** (29/08/2026) — trước đây phản hồi vào
  thẻ đã đóng sẽ **tự mở lại** thẻ, thành ra một thẻ gánh nhiều việc và nhìn vào không còn biết
  trường hợp nào đã xong.
  - Thẻ đã khép: **không nhận thêm phản hồi** (server chặn), màn chi tiết bỏ luôn ô nhập và mời
    **mở thẻ mới** ngay tại đó — khỏi gõ xong mới bị báo lỗi.
  - **Mở lại** chỉ còn ở phía **Tập đoàn** (bên tiếp nhận & xử lý ca) như van sửa sai khi bấm nhầm;
    phía đơn vị bỏ nút này — để đơn vị tự mở lại là quay về đúng cái vừa bỏ.
  - Đóng thẻ thì cả hai bên vẫn làm được (đơn vị có quyền nói *"thôi không cần nữa"*).

### Added
- **Nút "Hoàn thành" ngay trên danh sách hợp đồng** (29/08/2026) — hợp đồng đã giao **đạt từ 95%**
  sản lượng ký mà chưa chốt thì hiện luôn nút *Hoàn thành* ở cột Thao tác, bấm là mở hộp thoại
  chốt; trước đây phải mở từng hợp đồng vào màn chi tiết mới tìm được nút.
  - Chỉ hiện ở dòng **còn thao tác được** (đứng cạnh Sửa · Xoá). Dòng đã chuyển sang *(chỉ xem)*
    hoặc đã chốt thì không có nút — chỉ xem thì không mọc thêm nút bấm được.
  - Ngưỡng 95% là **một hằng số** (`DONE_RATIO`) — muốn chặt/lỏng hơn thì đổi đúng một chỗ.

- **Lãnh đạo đơn vị xem được số liệu của đơn vị mình** (29/08/2026) — vai trò *Lãnh đạo đơn vị
  thành viên* nay không chỉ có hộp thư, mà **theo dõi được toàn bộ số liệu đơn vị mình** ở chế độ
  **CHỈ XEM**: Thu mua · Tồn kho · Nhu cầu thị trường · Kế hoạch năm · Khách hàng · Hợp đồng mẹ ·
  Hợp đồng & đợt giao · Báo cáo tiêu thụ. Menu ghi rõ **"(chỉ xem)"**, mỗi màn có dòng nhắc
  *"việc nhập/sửa do tài khoản nhập liệu của đơn vị thực hiện"*.
  - **Chặn ghi ở MỘT chỗ duy nhất** (theo method HTTP tại dependency), không gắn tay từng
    endpoint: hơn 20 endpoint của `/api/member`, gắn tay là kiểu gì cũng sót — và endpoint thêm
    sau này cũng tự động được bảo vệ.
  - Mở được **phiếu số liệu từng ngày** để xem đủ chỉ tiêu (trước đây tài khoản không có quyền
    sửa thì mất luôn nút mở phiếu, chỉ đọc được vài cột đầu của bảng).
  - Phiếu ngày nói **đúng lý do khoá**: tài khoản chỉ xem · ngày đã chốt · ngoài cửa sổ nhập là ba
    chuyện khác nhau, cách xử lý cũng khác.

### Fixed
- **Bốn màn tồn kho nay nói cùng một con số** (06/09/2026) — biểu đồ *Tồn kho VRG theo ngày*
  (Dashboard · Bản tin biến động) lệch hẳn so với *Báo cáo tồn kho* và *Thống kê tồn kho*. Đo trên
  dữ liệu thật ngày 03/09/2026: biểu đồ **56.678 tấn** trong khi dòng lũy kế của Báo cáo tồn kho
  **74.597 tấn** — chênh **17.919 tấn (+31,6%)**. Ba nguyên nhân, đã xử lý cả ba:
  - **Định nghĩa**: biểu đồ chỉ cộng khối *"Đã nhập kho"* nhưng nhãn lại ghi *"tồn kho tổng"* (bỏ
    sót 16-18%, tức 11.400-12.100 tấn mỗi ngày). Nay **tồn kho thành phẩm = chưa nhập kho + đã nhập
    kho** như mọi màn khác, và biểu đồ mặc định vẽ **cột chồng 2 lớp** *Đã / chưa nhập kho* — vẫn
    đọc riêng được lớp "đã nhập kho" để đối chiếu số tay Ban TTKD (chuỗi tồn kho tuần giữ nguyên
    cách tính cũ, có chủ ý).
  - **Đơn vị đã sáp nhập**: luật "kho của đơn vị cũ đã nằm trong số của đơn vị nhận" trước đây chỉ
    có ở 2/4 màn; nay biểu đồ theo ngày và dòng lũy kế của Báo cáo tồn kho cũng áp dụng, không còn
    đếm hai lần cùng một lô hàng.
  - **Số đã cũ**: dòng lũy kế lấy ảnh chụp mới nhất của từng đơn vị trong cả khoảng (mặc định 90
    ngày) nhưng chỉ khoe ngày mới nhất. Nay ghi rõ **số đơn vị có số** và cảnh báo đỏ *"N đơn vị số
    đã cũ hơn 7 ngày (cũ nhất …)"* — vẫn cộng đủ, không bỏ đơn vị chậm nộp ra khỏi tổng.
  - *Thống kê tồn kho* xem theo **Ngày** trước đây chỉ áp luật sáp nhập cho dòng *Tổng cộng*, còn
    từng dòng ngày vẫn cộng cả hai đơn vị — chính bảng đó tự cãi nhau. Nay xét theo **từng ngày**:
    ngày trước ngày hiệu lực vẫn cộng đủ hai kho (lúc đó còn khai riêng thật), từ ngày hiệu lực
    trở đi chỉ tính đơn vị nhận.
  - Sửa luôn phần chữ đã lỗi thời ở *Thống kê tồn kho* (còn nhắc ô "số ngày được phép lùi" đã gỡ
    từ 21/08/2026).

- **`ensure_schema()` không tạo bảng nào trên Postgres không có TimescaleDB** (06/09/2026) — lệnh
  tạo hypertable nằm chung transaction với `CREATE TABLE`; thiếu extension thì lệnh đó lỗi làm hỏng
  cả transaction, `except` chỉ biến commit thành rollback nên hàm chạy êm mà DB trống trơn. Nay
  hypertable chạy ở transaction riêng — dựng DB test trên Postgres thường đã đúng như tài liệu.

- **Bịt lỗ đơn vị đọc được số liệu của đơn vị khác qua API** (29/08/2026) — `/api/series/*` (chuỗi
  số liệu mức Tập đoàn, **chia được theo từng đơn vị**) trước đây chỉ gác đăng nhập, nên một tài
  khoản đơn vị gọi thẳng API là xem được sản lượng · tồn kho · tiêu thụ của mọi đơn vị khác. Nay
  chặn hẳn tài khoản đơn vị ở tầng API. Không ảnh hưởng ai: hai màn dùng chuỗi này (Dashboard,
  Bản tin biến động) vốn không có trong menu của tài khoản đơn vị.

- **Hỗ trợ & Thông báo + Nhắc lịch cho lãnh đạo đơn vị** (29/08/2026) — hộp thư hai chiều giữa
  **Tập đoàn** và **lãnh đạo các đơn vị thành viên**, kèm gửi **email** báo tin mới.
  - **Vai trò mới `Lãnh đạo đơn vị thành viên`**: gán vào một hoặc nhiều đơn vị (như tài khoản đơn
    vị thành viên), nhưng **chỉ thấy mục Hỗ trợ & Thông báo** — không nhập số liệu. Tài khoản
    `Đơn vị thành viên` (nhập liệu) **không** vào được hộp thư này.
  - **Hai chiều**: đơn vị gửi **yêu cầu hỗ trợ** lên Tập đoàn; Tập đoàn gửi **thông báo** xuống
    **1 đơn vị · một khu vực · tất cả đơn vị**. Mỗi tin có **nội dung · file đính kèm · hình ảnh ·
    phản hồi qua lại**, đóng/mở lại được.
  - ⚠ **Các đơn vị không thấy tin và phản hồi của nhau**: gửi cho N đơn vị là tạo **N luồng riêng**
    (không phải một luồng nhiều người nhận), nên cách ly là tính chất của **dữ liệu** chứ không
    phải của giao diện. Đơn vị gõ thẳng đường dẫn tin của đơn vị khác vẫn báo *không tìm thấy*;
    file đính kèm cũng chặn tải chéo đơn vị.
  - Phía Tập đoàn có 2 khay: **Đơn vị gửi lên** và **Đã gửi đơn vị** (gom 1 dòng cho mỗi đợt gửi,
    hiện số đơn vị nhận + số phản hồi chưa đọc; bấm vào xem từng đơn vị).
  - **Nhắc lịch**: hẹn giờ (một lần · hằng ngày · tuần · tháng) cho phạm vi đơn vị đã chọn; tới hạn
    hệ thống tự gửi thông báo + email. Hệ thống rà 5 phút một lần; máy chủ tắt qua giờ hẹn thì
    **gửi bù một lần** khi chạy lại. Có nút **Gửi ngay** (không đụng mốc định kỳ).
  - **Email**: khai SMTP ở *Quản trị → Cấu hình hệ thống → tab **Email*** (máy chủ · cổng · bảo mật ·
    tài khoản · địa chỉ người gửi · **Địa chỉ hệ thống** để dựng link), kèm nút **Gửi thử**. Địa chỉ
    nhận lấy ở ô **Email** của tài khoản (bỏ trống thì lấy tên đăng nhập nếu là email). **Chưa khai
    SMTP thì tính năng vẫn chạy bình thường**, chỉ không gửi mail.
  - Quyền mới **`Hỗ trợ & Thông báo`** (2 mức Xem/Sửa) cho chuyên viên; quản trị mặc định đủ quyền.

- **Hàng có chứng chỉ + Premium trên hợp đồng** (26/08/2026) — khối mới *Hàng có chứng chỉ* ở **cả
  hợp đồng gốc (HĐNT/HĐDH) lẫn hợp đồng bán (gồm HĐ chuyến)**: chọn **nhiều** chứng chỉ trong danh
  mục **PEFC · EUDR · VRG GREEN**, kèm ô **Premium** khách trả thêm — **tự nhập số tiền**, chọn
  **USD** hay **VNĐ**. Không có premium thì **để trống** (bỏ trống số tiền thì loại tiền cũng xoá
  theo, không đọng lại giá trị mồ côi).
  - Trước đây đơn vị phải nhét chữ "PEFC"/"EUDR" vào **số hợp đồng** hoặc **tên file scan** (dữ liệu
    thật trên prod: `194.SEP.NEW KOREA SVR10 EUDR SPOT.pdf`) — không lọc, không thống kê được.
  - **Premium KHÔNG tự cộng vào đơn giá/doanh thu**: đơn giá trên dòng hợp đồng là giá bán thực tế
    đã chốt với khách (thường đã gồm premium), cộng thêm lần nữa là thổi doanh thu. Đây là số ghi
    nhận riêng để sau thống kê "bán bao nhiêu tấn hàng có chứng chỉ, premium bình quân bao nhiêu".
  - Khai ở **cấp hợp đồng**; **đợt giao thừa kế** của hợp đồng cha (đợt tự khai thì cùng một lô
    hàng có hai câu trả lời). Chứng chỉ ngoài danh mục hoặc loại tiền khác USD/VNĐ đều **báo lỗi**.
  - Màn chi tiết của cả hai loại hợp đồng hiện chip chứng chỉ + khoản premium.
- **Chốt số liệu đơn vị thành viên** (25/08/2026) — Ban TTKD phát yêu cầu *"chốt số liệu đến hết
  ngày X"*, đơn vị rà số rồi **xác nhận**; xác nhận xong là đơn vị **hết tự sửa** số liệu của
  những ngày đó.
  - **Màn quản trị mới**: *Báo cáo & Thống kê → **Chốt số liệu đơn vị*** — tạo/sửa/huỷ đợt chốt,
    bảng theo dõi từng đơn vị (đã chốt · chưa xác nhận · ai xác nhận · lúc nào), **lọc "chỉ đơn vị
    chưa xác nhận"**, và nút **khoá hộ / mở khoá** (từng đơn vị hoặc cả loạt). Xem trang cần quyền
    *Báo cáo đơn vị theo ngày*; tạo đợt và khoá/mở là **quản trị**.
  - **Cảnh báo trên mọi màn của đơn vị**: hàng đỏ "yêu cầu chốt đến ngày…", bấm là mở **bảng số
    liệu sẽ chốt** (thu mua · tiêu thụ · tồn kho tại ngày chốt, kèm số ngày còn thiếu) rồi mới xác
    nhận. Chốt xong hàng đổi thành dòng xanh kèm nhắc *báo Ban TTKD nếu cần sửa*.
  - **Phạm vi khoá**: 2 biểu ngày đơn vị nhập (**Thu mua** · **Tồn kho**), **mọi bản ghi đã giao có ngày giao
    ≤ ngày chốt** (đợt giao / HĐ giao-1-lần — để con số tiêu thụ đã chốt không đổi được nữa), đơn
    giá mủ nguyên liệu đơn vị tự khai, và tồn kho đã ký HĐ. **Hợp đồng vẫn cập nhật bình thường**,
    vẫn thêm đợt giao mới sau ngày chốt.
  - **Ngoại lệ biểu Tồn kho**: cảnh báo *"còn N ngày chưa nộp"* chỉ rà **từ 24/07/2026** (mốc các đơn vị bắt đầu nộp tồn kho); ngày trước đó không ai phải nộp nên không tính là thiếu. Màn hình ghi rõ *"chỉ tính từ 24/07/2026"*. Biểu Thu mua vẫn rà cả kỳ.
  - Chuyên viên và quản trị **không** bị chặn — sau khi chốt, đó là đường sửa duy nhất.
  - Chốt số liệu và *cửa sổ nhập liệu* là **hai hàng rào độc lập**: cái nào chặn tới ngày mới hơn
    thì cái đó quyết định.
  - Con số trong bảng xác nhận **được chụp lại** lúc bấm — trang theo dõi hiện luôn số đã chốt của
    từng đơn vị để đối chiếu về sau.

### Changed
- **Báo cáo kỳ + Theo dõi nộp báo cáo nhanh hơn ~20 lần** (25/08/2026) — hai chỗ này gọi
  `unit_daily_repo.in_range` với mặc định *gắn khối "đã ký HĐ chưa giao" cho TỪNG NGÀY* (một truy
  vấn hợp đồng mỗi ngày, kỳ 8 tháng = 237 truy vấn) trong khi cả hai **không đọc khối đó**: báo cáo
  kỳ lấy khối 3 một lần ở ngày cuối kỳ, còn bảng theo dõi chỉ hỏi "đã nộp hay chưa". Đo trên dữ
  liệu thật: báo cáo kỳ 2,0s → 0,17s; bảng ngày thiếu 1,76s → 0,05s.
- **Hợp đồng mẹ bỏ ĐƠN GIÁ, thêm QUY KHÔ** (chốt 25/08/2026) — khối *Chủng loại & sản lượng cam
  kết* chỉ còn **Chủng loại · SL (tấn)**; bỏ hẳn *Đơn giá*, *Loại tiền*, *Tỷ giá*. Giá là số của
  từng chuyến nên khai ở phụ lục; giá đi theo công thức thì ghi ở ô **Công thức giá** (HĐ dài hạn).
  - **LATEX và 2 loại mủ nguyên liệu** nay có ô **Quy khô (tấn)** và ô SL đổi nhãn thành **SL
    nước**, đúng như phiếu hợp đồng và đợt giao. Đã ghi số lượng thì **bắt buộc** ghi quy khô;
    chưa cam kết số lượng thì để trống cả hai (HĐNT thường chỉ chốt chủng loại).
  - Ô số lượng không còn chữ mờ *"chưa cam kết" / "chưa chốt"* — để trống như các màn khác.
  - Đơn giá/loại tiền/tỷ giá của hồ sơ **đã nhập trước đây** sẽ bị bỏ ở lần **lưu** kế tiếp; không
    báo lỗi, vì người dùng không còn ô nào để sửa 3 giá trị đó nữa.
- **Hồ sơ hợp đồng mẹ nay gắn theo LOẠI HỢP ĐỒNG** (chốt 24/08/2026):
  - **HĐ chuyến** bán đứt từng chuyến ⇒ **không có hợp đồng mẹ**; ô đó tự khoá lại, đổi loại sang
    HĐ chuyến thì hồ sơ đang chọn bị bỏ.
  - **HĐ dài hạn** là **phụ lục** của một hợp đồng mẹ ⇒ **bắt buộc** chọn hồ sơ, **cả lúc tạo lẫn
    lúc sửa**. 942 hợp đồng dài hạn nhập trước khi có cấp hồ sơ sẽ phải gắn hồ sơ ở lần sửa tiếp
    theo — đây là cách dọn dần hồ sơ cũ.
  - Không đụng tới: *Hoàn thành hợp đồng*, *Chuyển loại giao* và mọi thao tác trên **đợt giao**
    (đợt giao không mang loại hợp đồng).

### Added
- **Sáp nhập đơn vị thành viên** (24/08/2026) — cột **Sáp nhập** ở màn *Đơn vị thành viên*: chọn
  đơn vị nhận + **ngày hiệu lực** (chọn lùi ngày được), có nút **Gỡ** để hoàn tác.
  - **Số liệu trước ngày hiệu lực giữ nguyên tên đơn vị cũ** — cố ý KHÔNG chuyển sang đơn vị mới
    như thao tác *đổi tên*, để còn tách được "trước / sau sáp nhập". Nhờ vậy gỡ sáp nhập không
    phải khôi phục dữ liệu.
  - Từ ngày hiệu lực: đơn vị cũ biến khỏi các form nhập liệu, mọi endpoint ghi chặn kèm câu chỉ rõ
    phải nhập vào đơn vị nào; **ngày trước đó vẫn sửa được**. Tài khoản chuyển hẳn sang đơn vị mới,
    đơn vị con trong cây mẹ–con trỏ sang đơn vị mới.
  - Thống kê (thu mua · tiêu thụ · tồn kho) và **Báo cáo tổng hợp** mặc định **GỘP** số của đơn vị
    cũ vào đơn vị hiện hành, có công tắc **Tách đơn vị đã sáp nhập**. Chỉ tiêu kế hoạch năm cộng
    theo — gộp tử số mà bỏ mẫu số thì % thực hiện tự đẹp lên. Kỳ kết thúc **trước** ngày hiệu lực
    vẫn để hai đơn vị đứng riêng (lúc đó chúng còn độc lập; với tồn kho, gộp là cộng trùng).
  - **Theo dõi nộp báo cáo** không đòi đơn vị đã sáp nhập nộp cho những ngày sau ngày hiệu lực
    (ô trạng thái riêng, không tính vào mẫu số).
  - **Hợp đồng đã ký của đơn vị cũ vẫn chạy hết**: thêm đợt giao / chốt hoàn thành bình thường,
    chỉ chặn ký hợp đồng (và mở hồ sơ hợp đồng mẹ) MỚI — chuyển hợp đồng sang đơn vị mới sẽ kéo
    theo cả sản lượng đã giao trước đó nhảy đơn vị.
- **Kế hoạch doanh thu năm cho đơn vị** (24/08/2026) — thêm ô *Kế hoạch doanh thu* (**tỷ đồng**) vào
  màn **Kế hoạch năm**, cạnh các chỉ tiêu sản lượng đang có; nhập/xuất được qua biểu Excel Kế hoạch.
  Màn **Thống kê tiêu thụ** thêm 2 dòng: *KH doanh thu* và ***% thực hiện*** = doanh thu kỳ / kế
  hoạch năm. Đơn vị tính chọn **tỷ đồng** cho trùng `revenue_ty` của báo cáo kỳ → phép chia cùng
  đơn vị, không phải quy đổi. Doanh thu để trống (có lần giao thiếu tỷ giá) thì **% cũng để trống**,
  không coi là 0.
- **Hợp đồng mẹ HĐNT/HĐDH + phụ lục hợp đồng** (phản hồi 21/08/2026) — thêm cấp hồ sơ gốc phía trên
  hợp đồng bán hàng, trước đây hệ thống không quản lý:
  - Màn mới **Quản lý hợp đồng → Hợp đồng mẹ (HĐNT/HĐDH)**: số hợp đồng · loại (*HĐ nguyên tắc* /
    *HĐ dài hạn*) · **khách hàng** · **nhiều chủng loại, mỗi chủng loại một đơn giá** · **file
    scan** · ngày ký/thời hạn. Số lượng và đơn giá **được để trống** khi hợp đồng chưa chốt.
    **Công thức giá** (text tự do) **chỉ có ở HĐ dài hạn** — HĐ nguyên tắc không có phần này, ở cả
    form nhập lẫn màn chi tiết; đổi loại sang nguyên tắc thì công thức cũ được bỏ (server cũng bỏ,
    không nhận chữ từ ô đã ẩn).
  - Màn **Hợp đồng & đợt giao** giữ NGUYÊN như trước, **chỉ thêm đúng một ô** *Hợp đồng mẹ* để nối
    bản ghi vào hồ sơ (chốt 24/08/2026). Nối hồ sơ **không đổi khách hàng, loại hợp đồng hay bất kỳ
    số liệu nào** — hợp đồng vẫn tự khai khách như cũ. Bản đầu từng ghi đè khách theo hồ sơ mẹ: gắn
    một hợp đồng cũ vào hồ sơ là lặng lẽ đổi số liệu “theo khách hàng” của một kỳ đã chốt.
  - Danh sách hợp đồng hiện *“phụ lục của HĐ …”* dưới số hợp đồng; màn chi tiết hiện hợp đồng mẹ và
    **công thức giá** của nó. Màn hợp đồng mẹ đếm **số phụ lục + sản lượng đã ký** để đối chiếu cam kết.
  - **Lọc theo hợp đồng mẹ ở màn Hợp đồng & đợt giao** (22/08/2026): ô *Hợp đồng mẹ* (gõ để tìm)
    xem trọn các phụ lục của một hồ sơ ngay trên danh sách — kèm dòng Tổng cộng của đúng hồ sơ đó;
    cạnh nó là ô tick **Chưa gắn hồ sơ** để rà những hợp đồng còn phải đưa vào hồ sơ. Hai điều kiện
    loại trừ nhau (chọn cái này thì bỏ cái kia).
  - **Nhập phụ lục ngay trên màn hợp đồng mẹ** (22/08/2026): nút *Thêm phụ lục* mở thẳng form hợp
    đồng với **đơn vị + hợp đồng mẹ khoá sẵn, khách hàng và loại HĐ điền sẵn** — chỉ còn gõ số phụ
    lục và chi tiết hàng. Trước đó phải sang màn *Hợp đồng & đợt giao* rồi gõ lại số hợp đồng mẹ để
    tìm, dù đang mở đúng hồ sơ đó.
  - **Gắn hợp đồng ĐÃ CÓ vào hồ sơ**: ở màn chi tiết hợp đồng mẹ bấm *Gắn hợp đồng có sẵn* → chọn
    nhiều hợp đồng (chỉ hiện hợp đồng **của đúng đơn vị** và **chưa thuộc hồ sơ nào**), gắn một lượt
    tối đa 200. Mỗi phụ lục có nút **gỡ**. Gắn/gỡ **chỉ đổi liên kết**, không đụng số liệu.
  - Bảng danh sách **không có cột Công thức giá** (đoạn văn dài, chiếm chỗ mọi cột khác mà đọc vẫn
    cụt — xem đủ ở màn chi tiết) và **chốt bề rộng từng cột** (`table-layout: fixed`): tên đơn vị /
    khách hàng dài không còn bóp cột thành một chữ mỗi dòng. Ngày ký + thời hạn gộp thành cột
    **Hiệu lực**; màn hẹp thì cuộn ngang nhưng cột **Thao tác ghim bên phải** để luôn bấm được.
  - ⚠ Hợp đồng mẹ **không góp số vào bất kỳ báo cáo sản lượng nào** — tiêu thụ và *“đã ký HĐ chưa
    giao”* vẫn tính trên hợp đồng/đợt giao (cộng cả hai cấp là đếm hai lần). Đợt giao không nối
    thẳng vào hợp đồng mẹ. Dùng chung quyền `sales_contract`, không phải cấp quyền mới.
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
### Changed
- **Tồn kho không còn đắp số ngày trước** (chốt 21/08/2026) — quy tắc lấy số của một đơn vị cho một
  ngày, áp dụng ở **mọi nơi tính tồn kho** (biểu đồ Bản tin biến động · màn Thống kê tồn kho · chức
  năng tự tính tồn kho tuần của Tập đoàn):
  - đơn vị **khai tồn** ngày nào → lấy đúng số ngày đó;
  - đơn vị tick **“không phát sinh tồn kho để khai”** → giữ nguyên số của lần khai gần nhất;
  - đơn vị **không khai gì** → KHÔNG có số (trước đây số cũ được đắp sang trong 7 ngày, nên biểu đồ
    hiện tồn kho cho cả những đơn vị chưa hề nộp).
  - Màn Thống kê tồn kho bỏ ô *“số ngày được phép lùi”*; khi nhóm theo NGÀY có ô *“xem lại N ngày”*
    thay thế — nó chỉ mở rộng phạm vi ngày xem, không đắp số.
  - Biểu đồ **không vẽ các ngày cuối đang nhập dở** (độ phủ dưới 85% ngày tốt nhất) và ghi rõ đã bỏ
    những ngày nào, mới bao nhiêu đơn vị — nếu không, ngày đang nhập tụt thành vách đá trông như
    Tập đoàn bán sạch kho trong một đêm.

### Fixed
- **Tỷ giá chỉ bắt buộc khi đã có NGÀY GIAO** (phản hồi 22/08/2026) — trước đây hễ dòng bán bằng
  ngoại tệ là đòi tỷ giá ngay lúc ký hợp đồng, trong khi tỷ giá chỉ biết được lúc giao hàng: đơn vị
  buộc phải bịa một con số và con số bịa ấy đi thẳng vào doanh thu.
  - Hợp đồng **giao nhiều lần**: cấp hợp đồng không bao giờ bị hỏi tỷ giá — khai ở từng **đợt giao**.
  - Hợp đồng **giao 1 lần** và **đợt giao**: chỉ bắt buộc khi đã điền *Ngày giao*; chưa giao thì để
    trống vẫn lưu được, ô ghi *"khi giao"* thay vì *"bắt buộc"*.
  - Thiếu tỷ giá thì **doanh thu để trống (không biết)**, tuyệt đối không tính bằng 0 — dòng tổng ở
    danh sách hợp đồng ghi rõ *"chưa gồm N HĐ chưa quy đổi được"*.
  - Tỷ giá **đã nhập** thì vẫn phải lớn hơn 0 ở mọi trạng thái.
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
### Changed
- **Tồn kho không còn đắp số ngày trước** (chốt 21/08/2026) — quy tắc lấy số của một đơn vị cho một
  ngày, áp dụng ở **mọi nơi tính tồn kho** (biểu đồ Bản tin biến động · màn Thống kê tồn kho · chức
  năng tự tính tồn kho tuần của Tập đoàn):
  - đơn vị **khai tồn** ngày nào → lấy đúng số ngày đó;
  - đơn vị tick **“không phát sinh tồn kho để khai”** → giữ nguyên số của lần khai gần nhất;
  - đơn vị **không khai gì** → KHÔNG có số (trước đây số cũ được đắp sang trong 7 ngày, nên biểu đồ
    hiện tồn kho cho cả những đơn vị chưa hề nộp).
  - Màn Thống kê tồn kho bỏ ô *“số ngày được phép lùi”*; khi nhóm theo NGÀY có ô *“xem lại N ngày”*
    thay thế — nó chỉ mở rộng phạm vi ngày xem, không đắp số.
  - Biểu đồ **không vẽ các ngày cuối đang nhập dở** (độ phủ dưới 85% ngày tốt nhất) và ghi rõ đã bỏ
    những ngày nào, mới bao nhiêu đơn vị — nếu không, ngày đang nhập tụt thành vách đá trông như
    Tập đoàn bán sạch kho trong một đêm.

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
