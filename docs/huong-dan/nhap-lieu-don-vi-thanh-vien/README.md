# Hướng dẫn nhập liệu — Đơn vị thành viên

Tài liệu dành cho cán bộ đơn vị thành viên VRG nhập số liệu hằng ngày trên Hệ thống Dự báo & Quản trị Giá Cao su. Tài khoản đơn vị chỉ thấy và chỉ nhập được số liệu của chính đơn vị mình. Có 5 mục cần nhập: Báo cáo thu mua, Báo cáo tiêu thụ, Báo cáo tồn kho và Nhu cầu thị trường (nhập theo NGÀY), cùng Kế hoạch năm (nhập 1 lần cho cả năm). Tài liệu bám theo phiên bản 0.2.71. Riêng 4 mục báo cáo còn có thể tải mẫu Excel về điền rồi nhập lên thay vì gõ tay (xem mục 9).

> Bản Word đầy đủ (có ảnh chú thích): [Huong-dan-nhap-lieu-don-vi-thanh-vien.docx](./Huong-dan-nhap-lieu-don-vi-thanh-vien.docx)

## 1. Đăng nhập và các mục cần nhập

**Vị trí:** Menu bên trái, nhóm “Quản lý số liệu (thủ công)”

Sau khi đăng nhập bằng tài khoản đơn vị, menu bên trái hiển thị đúng các mục đơn vị cần làm. Số liệu nhập vào luôn tự gắn với đơn vị của tài khoản — không cần và không thể chọn đơn vị khác.

![Hình 1. Menu của tài khoản đơn vị thành viên](img/01-menu.png)

*Hình 1. Menu của tài khoản đơn vị thành viên*

**Năm mục cần nhập:**

1. **Báo cáo thu mua** — sản lượng và đơn giá thu mua mủ nguyên liệu **theo ngày**.
2. **Báo cáo tiêu thụ** — sản lượng bán theo từng hợp đồng, giá bán và doanh thu **theo ngày**.
3. **Báo cáo tồn kho** — tồn kho thành phẩm (đã / chưa có hợp đồng) và tồn kho nguyên liệu **theo ngày**.
4. **Kế hoạch năm** — kế hoạch thu mua và hợp đồng dài hạn đã ký, **nhập 1 lần cho cả năm**.
5. **Nhu cầu thị trường** — ghi nhận nhu cầu/tín hiệu thị trường của đơn vị, nhập **tự do bằng chữ**.

> - Báo cáo tiêu thụ và Báo cáo tồn kho là **hai tab của cùng một phiếu ngày** — nhập bên này không làm mất số bên kia.
> - Chỉ nhập/sửa được ngày hôm nay và một số ngày gần nhất theo quy định; ngày cũ hơn chỉ để xem.

## 2. Màn hình danh sách và 3 nút thao tác

**Vị trí:** Menu → Báo cáo thu mua (các màn khác bố trí tương tự)

Mỗi màn báo cáo đều có danh sách các ngày đã nhập và 3 nút thao tác giống nhau.

![Hình 2. Danh sách theo ngày và các nút thao tác](img/02-thu-mua-danh-sach.png)

*Hình 2. Danh sách theo ngày và các nút thao tác*

1. **Thêm số liệu ngày** — mở phiếu nhập cho một ngày mới.
2. **Tải mẫu Excel** — tải file mẫu về để điền ngoại tuyến (xem mục 8).
3. **Nhập từ Excel** — nhập file đã điền lên hệ thống (xem mục 8).
4. **Biểu tượng bút** ở cuối mỗi dòng — mở lại phiếu của ngày đó để sửa.

> - Danh sách chỉ hiện những ngày **đã có số liệu**; ngày chưa nhập sẽ không xuất hiện.

## 3. Nhập Báo cáo thu mua — đơn vị trong nước

**Vị trí:** Báo cáo thu mua → Thêm số liệu ngày

Áp dụng cho các đơn vị tại Việt Nam (giao dịch bằng đồng Việt Nam). Phiếu chia theo loại mủ: mỗi loại nhập sản lượng và đơn giá đi liền nhau. Riêng mủ chén phải chọn đơn giá tính theo độ TSC hay độ DRC trước khi nhập giá.

![Hình 3. Phiếu Thu mua của đơn vị trong nước](img/03-thu-mua-vn.png)

*Hình 3. Phiếu Thu mua của đơn vị trong nước*

1. Chọn **ngày báo cáo**.
2. **Mủ nước — Sản lượng thu mua** (tấn, quy khô).
3. **Mủ nước — Đơn giá thu mua** (đồng/độ TSC).
4. **Mủ chén — Sản lượng thu mua** (tấn, quy khô).
5. **Mủ chén — Đơn giá tính theo**: chọn *Độ TSC* hoặc *Độ DRC* theo cách đơn vị đang tính.
6. **Mủ chén — Đơn giá thu mua**: nhãn ô này đổi theo bước 5 (*đồng/độ TSC* hoặc *đồng/độ DRC*).
7. **Sản lượng tiêu thụ mủ thu mua** (tấn).
8. **Doanh thu** (tỷ đồng) — doanh thu đã xuất hóa đơn. Xong bấm **Lưu số liệu**.

> - Ô **Giá bán bình quân** hệ thống **tự tính** = Doanh thu ÷ Sản lượng tiêu thụ — không cần nhập.
> - Đơn giá nhập ở đây đồng thời được ghi vào kho “Giá mủ nguyên liệu”, không phải nhập lại ở nơi khác. Đơn vị tính (TSC hay DRC) được lưu kèm giá nên về sau vẫn biết giá đó tính theo độ nào.
> - Mủ nước luôn tính theo **độ TSC** — chỉ mủ chén mới có lựa chọn TSC/DRC.

## 4. Nhập Báo cáo thu mua — đơn vị ngoài Việt Nam

**Vị trí:** Báo cáo thu mua → Thêm số liệu ngày (đơn vị tại Lào / Campuchia)

Đơn vị ở nước ngoài mua mủ bằng nội tệ (LAK/KHR) và bán bằng USD, nên phiếu có thêm ô nội tệ và HAI tỷ giá riêng. Các ô nền xám là hệ thống tự quy đổi, không nhập tay.

![Hình 4. Phiếu Thu mua của đơn vị nước ngoài (ví dụ đơn vị tại Lào — LAK)](img/04-thu-mua-nuoc-ngoai.png)

*Hình 4. Phiếu Thu mua của đơn vị nước ngoài (ví dụ đơn vị tại Lào — LAK)*

**Khác biệt so với đơn vị trong nước:**

1. **Đơn giá thu mua theo nội tệ** (LAK/KHR trên độ) — nhập giá mua thực tế tại nước sở tại.
2. **Mủ chén — Đơn giá tính theo**: chọn *Độ TSC* hoặc *Độ DRC* (giống đơn vị trong nước).
3. **Tỷ giá thu mua** (1 nội tệ = ? VND) — dùng để quy đơn giá về đồng.
4. **Doanh thu theo USD** — doanh thu bán hàng tính bằng đô-la Mỹ.
5. **Tỷ giá USD** (1 USD = ? VND) — dùng để quy doanh thu về đồng.
6. **Lấy tỷ giá hiện tại** — bấm để hệ thống tự điền tỷ giá USD của Vietcombank.

> - Hai tỷ giá là **khác nhau và độc lập**: tỷ giá nội tệ dùng cho đơn giá thu mua, tỷ giá USD dùng cho doanh thu.
> - Các ô nền xám (**đơn giá quy ra đồng**, **doanh thu quy ra tỷ đồng**) là hệ thống tự quy đổi, chỉ để xem.
> - Nếu chưa nhập tỷ giá USD thì hệ thống **để trống doanh thu** chứ không tự suy đoán.
> - Sản lượng, sản lượng tiêu thụ và cách lưu vẫn giống đơn vị trong nước (mục 3).

## 5. Nhập Báo cáo tiêu thụ

**Vị trí:** Menu → Báo cáo tiêu thụ → Thêm số liệu ngày

Mỗi hợp đồng bán là một dòng. Trong ngày bán bao nhiêu hợp đồng thì thêm bấy nhiêu dòng, hệ thống tự cộng lại. Mỗi dòng ghi kèm ngày xuất hoá đơn và file bộ Hợp đồng.

![Hình 5. Phiếu Tiêu thụ — bảng nhiều dòng](img/05-tieu-thu.png)

*Hình 5. Phiếu Tiêu thụ — bảng nhiều dòng*

1. **Loại HĐ** (Dài hạn / Chuyến) · **Hình thức** (XK-UTXK / Nội tiêu) · **Loại mủ**.
2. **SL (tấn)** — số lượng bán của dòng này.
3. **Giá bán** — đơn vị tính theo loại tiền chọn ở bước 7 (triệu đ/tấn hoặc USD/tấn).
4. **Ngày xuất hoá đơn** — ngày hoá đơn của dòng bán này; chưa xuất thì để trống.
5. **Bộ Hợp đồng** — bấm *Chọn* để đính kèm file (PDF hoặc ảnh); bấm vào tên file để mở lại.
6. **Thêm dòng** nếu trong ngày có nhiều hợp đồng.
7. **Giá bán nhập bằng** — chọn *VND* hoặc *USD*. Chọn USD thì hiện thêm ô **Tỷ giá** (có nút lấy tỷ giá Vietcombank). Xong bấm **Lưu số liệu**.

> - Cột **Doanh thu** của từng dòng và toàn bộ khối **Tổng hợp tiêu thụ** đều **tự tính** — không nhập tay.
> - Chọn USD mà **chưa nhập tỷ giá** thì doanh thu để trống, hệ thống không tự đoán tỷ giá.
> - Loại tiền áp cho **cả phiếu**, không phải từng dòng — trong ngày có cả bán USD lẫn VNĐ thì nhập thành 2 ngày phiếu hoặc quy về một loại tiền.
> - Xoá một dòng bằng biểu tượng thùng rác ở cuối dòng.

## 6. Nhập Báo cáo tồn kho

**Vị trí:** Menu → Báo cáo tồn kho → Thêm số liệu ngày

Tồn kho là số liệu **tại thời điểm cuối ngày** (không cộng dồn giữa các ngày), đơn vị tính là **tấn**. Phiếu chia thành 4 khối theo tình trạng hàng.

![Hình 6. Phiếu Tồn kho — hai bảng theo tình trạng hợp đồng](img/06-ton-kho.png)

*Hình 6. Phiếu Tồn kho — hai bảng theo tình trạng hợp đồng*

**Bốn khối tồn kho:**

1. **Lấy tồn ngày trước** — chép toàn bộ tồn kho của ngày gần nhất sang, rồi sửa lại cho đúng ngày này.
2. **1. Tồn kho thành phẩm chế biến chưa nhập kho** — chủng loại + số lượng (tấn).
3. **2. Tồn kho thành phẩm đã nhập kho** — chủng loại + số lượng (tấn).
4. **3. Số lượng đã ký hợp đồng chưa giao** — thêm đơn giá, lịch giao và **file Hợp đồng đã ký scan có đóng dấu**.
5. **Đơn giá nhập bằng** — chọn *VND* hoặc *USD* cho đơn giá ở khối 3 (chọn USD thì hiện ô tỷ giá).
6. **4. Tồn kho nguyên liệu chưa sản xuất** — 1 ô số lượng (tấn). Xong bấm **Lưu số liệu**.

> - Khối **4** hiện với **mọi đơn vị**. Câu “đối với các đơn vị chưa có nhà máy chế biến” là ghi chú của biểu mẫu cho biết ai thường có số này — đơn vị đã có nhà máy cứ **để trống ô đó**.
> - Nút **Lấy tồn ngày trước** chỉ chép **tồn kho**, KHÔNG chép các dòng bán ở tab Tiêu thụ — vì tiêu thụ là số phát sinh trong ngày, chép sang sẽ thành khai khống.
> - Khối **Tổng hợp tồn kho** tự tính: *Tồn kho thành phẩm* = khối 1 + khối 2. Khối 3 (**đã ký HĐ chưa giao**) là **cam kết giao hàng**, đứng riêng — không cộng vào và không trừ khỏi tồn kho thành phẩm, nên ký nhiều hơn lượng đang có cũng không sao.
> - Chủng loại tách theo từng loại giống bảng Giá sàn Tập đoàn — **SVR CV 50** và **SVR CV60** là 2 loại riêng.

## 7. Nhập Kế hoạch năm

**Vị trí:** Menu → Kế hoạch năm

Đây là số liệu của cả năm, chỉ nhập một lần và cập nhật lại khi có thay đổi — KHÔNG nhập hằng ngày. Số liệu này dùng để tính % thực hiện kế hoạch trong báo cáo.

![Hình 7. Màn Kế hoạch năm](img/07-ke-hoach-nam.png)

*Hình 7. Màn Kế hoạch năm*

1. Chọn **năm** cần khai.
2. **Kế hoạch thu mua** (tấn) — chỉ tiêu Tập đoàn giao hoặc kế hoạch của công ty.
3. **HĐ dài hạn đã ký** (tấn) — tổng sản lượng đã ký hợp đồng dài hạn trong năm.
4. **HĐ dài hạn năm trước chuyển sang** (tấn).
5. **HĐ chuyến năm trước chuyển sang** (tấn).
6. Số liệu **tự lưu khi rời khỏi ô** — không có nút Lưu riêng.

> - Nếu tài khoản được giao nhiều đơn vị thì màn này hiện đủ các đơn vị đó.

## 8. Nhập Nhu cầu thị trường

**Vị trí:** Menu → Nhu cầu thị trường

Mục này ghi lại nhu cầu và tín hiệu thị trường mà đơn vị nắm được: khách hỏi mua, chào giá, đơn hàng sắp ký… Đây là phần nhập **tự do bằng chữ**, không có ô số liệu, giúp Ban Thị trường Kinh doanh nắm tình hình thực tế tại đơn vị.

![Hình 9. Nhập Nhu cầu thị trường](img/09-nhu-cau-thi-truong.png)

*Hình 9. Nhập Nhu cầu thị trường*

1. Bấm **Thêm nhu cầu** để mở ô nhập.
2. Chọn **ngày** ghi nhận nhu cầu.
3. Chọn **đơn vị** (tài khoản chỉ có đơn vị của mình).
4. Nhập **nội dung** — viết tự do, nên ghi rõ: khách hàng, chủng loại, số lượng, giá chào và thời điểm giao.
5. Bấm **Lưu**.
6. Muốn sửa nội dung đã ghi: bấm **biểu tượng bút** ở dòng tương ứng trong danh sách bên dưới.

> - Danh sách bên dưới xếp theo **dòng thời gian**, chỉ hiện những ngày đã có nhập.
> - Mỗi ngày mỗi đơn vị chỉ có **một nội dung**; nhập lại cho ngày đã có sẽ được nhắc dùng chức năng Sửa.
> - Mục này **không có nhập bằng Excel** — chỉ nhập trực tiếp trên màn hình.
> - Cũng áp dụng cửa sổ thời gian như các báo cáo khác: ngày quá cũ chỉ để xem.

## 9. Nhập nhanh bằng Excel (tải mẫu → nhập lên)

**Vị trí:** Có ở 4 màn báo cáo: Thu mua / Tiêu thụ / Tồn kho / Kế hoạch năm

Thay vì gõ tay từng ngày, có thể tải file Excel mẫu về điền rồi nhập lên. Hệ thống đọc file và cho **xem trước** — dòng nào sai sẽ chỉ rõ sai ở đâu, chỉ những dòng hợp lệ mới được ghi.

![Hình 9. Bảng xem trước trước khi ghi](img/08-import-xem-truoc.png)

*Hình 9. Bảng xem trước trước khi ghi*

**Cách làm:**

1. **Tải mẫu Excel** ở màn danh sách → điền số vào file (mỗi biểu một mẫu riêng).
2. **Nhập từ Excel** → chọn file vừa điền, hệ thống mở bảng **xem trước**.
3. Dòng tóm tắt cho biết đọc được bao nhiêu dòng, **bao nhiêu hợp lệ / bao nhiêu lỗi**.
4. Các cột **chọn từ danh sách** (vd *Đơn giá mủ chén tính theo*) hiện đúng giá trị đã điền — để trống thì hệ thống dùng mặc định ghi ngay trên tiêu đề cột.
5. Cột **Ghi chú** nói rõ dòng lỗi sai ở đâu (vd *Ngày: ngày không hợp lệ*).
6. Bấm **Xác nhận ghi N dòng** — chỉ ghi các dòng hợp lệ, dòng lỗi bị bỏ qua.

> - File mẫu của đơn vị **không có cột “Đơn vị”** — hệ thống tự gán đúng đơn vị của tài khoản, không cần gõ tên.
> - **Không đổi tên hoặc xoá dòng tiêu đề** của file mẫu; nếu thiếu cột bắt buộc hệ thống sẽ báo và không đọc file.
> - Muốn sửa dòng lỗi: sửa lại trong file Excel rồi nhập lên lần nữa — các dòng đã ghi đúng sẽ được ghi đè, không bị nhân đôi.
> - Nhập Tiêu thụ không làm mất số Tồn kho của cùng ngày và ngược lại.
> - **Mẫu Excel đã đổi cột** — luôn bấm *Tải mẫu Excel* để lấy file mới nhất, đừng dùng lại file tải từ trước (sai cột sẽ báo lỗi khi nhập lên).
> - Ba cột **chọn từ danh sách** mới có, phải điền đúng thì số mới vào đúng đơn vị tính: *Đơn giá mủ chén tính theo* (Độ TSC / Độ DRC) ở mẫu **Thu mua**; *Giá bán bằng* (VND / USD) ở mẫu **Tiêu thụ**; *Đơn giá bằng* (VND / USD) ở mẫu **Tồn kho**. Bỏ trống thì hệ thống hiểu là Độ TSC và VND.
> - Mẫu **Tồn kho**: cột *Nhóm* có 3 lựa chọn — Chế biến chưa nhập kho · Đã nhập kho · Đã ký HĐ chưa giao. Số lượng tính bằng **tấn**. Riêng *Tồn kho nguyên liệu chưa sản xuất* là cột cuối, điền ở 1 dòng bất kỳ của ngày đó.
> - Mẫu **Tiêu thụ** có cột *Ngày xuất hoá đơn*. Riêng **file bộ Hợp đồng phải đính kèm trên web** — file Excel không mang theo file đính kèm được.
