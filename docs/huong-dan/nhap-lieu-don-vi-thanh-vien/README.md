# Hướng dẫn nhập liệu — Đơn vị thành viên

Tài liệu dành cho cán bộ đơn vị thành viên VRG nhập số liệu hằng ngày trên Hệ thống Dự báo & Quản trị Giá Cao su. Tài khoản đơn vị chỉ thấy và chỉ nhập được số liệu của chính đơn vị mình. Có 5 mục cần nhập: Báo cáo thu mua, Báo cáo tiêu thụ, Báo cáo tồn kho và Nhu cầu thị trường (nhập theo NGÀY), cùng Kế hoạch năm (nhập 1 lần cho cả năm). Tài liệu bám theo phiên bản 0.2.77. Riêng 4 mục báo cáo còn có thể tải mẫu Excel về điền rồi nhập lên thay vì gõ tay (xem mục 9).

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
4. **Nhu cầu thị trường** — ghi nhận nhu cầu/tín hiệu thị trường của đơn vị, nhập **tự do bằng chữ**.
5. **Kế hoạch năm** — kế hoạch thu mua và hợp đồng dài hạn đã ký, **nhập 1 lần cho cả năm**.

> - Báo cáo tiêu thụ và Báo cáo tồn kho là **hai tab của cùng một phiếu ngày** — nhập bên này không làm mất số bên kia.
> - Chỉ nhập/sửa được ngày hôm nay và một số ngày gần nhất theo quy định; ngày cũ hơn chỉ để xem.

## 2. Màn hình danh sách và 3 nút thao tác

**Vị trí:** Menu → Báo cáo thu mua (các màn khác bố trí tương tự)

Mỗi màn báo cáo đều có danh sách các ngày đã nhập và 3 nút thao tác giống nhau.

![Hình 2. Danh sách theo ngày và các nút thao tác](img/02-thu-mua-danh-sach.png)

*Hình 2. Danh sách theo ngày và các nút thao tác*

1. **Thêm số liệu ngày** — mở phiếu nhập cho một ngày mới.
2. **Tải mẫu Excel** — tải file mẫu về để điền ngoại tuyến (xem mục 9).
3. **Nhập từ Excel** — nhập file đã điền lên hệ thống (xem mục 9).
4. **Biểu tượng bút** ở cuối mỗi dòng — mở lại phiếu của ngày đó để sửa.

> - Danh sách chỉ hiện những ngày **đã có số liệu**; ngày chưa nhập sẽ không xuất hiện.

## 3. Nhập Báo cáo thu mua — đơn vị trong nước

**Vị trí:** Báo cáo thu mua → Thêm số liệu ngày

Áp dụng cho các đơn vị tại Việt Nam. Phiếu chia theo loại mủ: mỗi loại nhập sản lượng và đơn giá đi liền nhau. Mủ chén phải chọn tính theo độ TSC hay độ DRC. Cuối phiếu là khối thu mua THÀNH PHẨM (mua lại mủ đã chế biến) — nhập theo **bảng, mỗi chủng loại một dòng**.

![Hình 3. Phiếu Thu mua của đơn vị trong nước](img/03-thu-mua-vn.png)

*Hình 3. Phiếu Thu mua của đơn vị trong nước*

1. Chọn **ngày báo cáo**.
2. **Mủ nước** — sản lượng (tấn, quy khô) và đơn giá (đồng/độ TSC).
3. **Mủ chén — Đơn giá tính theo**: chọn *Độ TSC* hoặc *Độ DRC*; nhãn ô đơn giá đổi theo lựa chọn này.
4. **Thu mua thành phẩm** — bảng nhập, **mỗi chủng loại mua trong ngày là một dòng riêng**.
5. **Một dòng chủng loại**: chọn **Chủng loại** · **SL thu mua** (tấn) · **Đơn giá** · **Tiền** (VNĐ hay USD) · **Tỷ giá** (chỉ hiện khi dòng đó chọn USD). Cột **Thành tiền** tự tính.
6. **Thêm chủng loại** — mua mấy chủng loại thì thêm bấy nhiêu dòng; nút thùng rác ở cuối dòng để xoá.
7. **Lấy tỷ giá VCB cho các dòng USD** — điền tỷ giá Vietcombank cho mọi dòng đang chọn USD. Xong bấm **Lưu số liệu**.

> - **Đơn giá đi theo loại tiền của từng dòng**: chọn VNĐ thì nhập **triệu đ/tấn**, chọn USD thì nhập **USD/tấn**. Trong một ngày có thể vừa mua bằng VNĐ vừa mua bằng USD.
> - Ba ô cuối khối — **Tổng SL thành phẩm · Tổng giá trị · Đơn giá bình quân** — hệ thống tự cộng, không nhập tay.
> - Đơn giá mủ nước/mủ chén nhập ở đây đồng thời ghi vào kho “Giá mủ nguyên liệu”, kèm đúng đơn vị tính (độ TSC hay độ DRC) đã chọn.
> - **Sản lượng tiêu thụ và doanh thu đã chuyển sang biểu Tiêu thụ** — không còn nhập ở phiếu Thu mua nữa.
> - Ô **Hôm nay đơn vị KHÔNG tổ chức thu mua** chỉ tích khi thật sự không tổ chức mua. Có công bố giá, có tổ chức mua nhưng không mua được thì **đừng tích** — nhập **sản lượng 0** kèm **đúng mức giá đã công bố** (không mua được ở mọi mức thì nhập 0 với **mức giá thấp nhất**). Hai trường hợp này khác nhau khi tổng hợp báo cáo.

## 4. Nhập Báo cáo thu mua — đơn vị ngoài Việt Nam

**Vị trí:** Báo cáo thu mua → Thêm số liệu ngày (đơn vị tại Lào / Campuchia)

Đơn vị ở nước ngoài mua mủ bằng nội tệ (LAK/KHR) và bán bằng USD, nên phiếu có thêm ô nội tệ và HAI tỷ giá riêng. Các ô nền xám là hệ thống tự quy đổi, không nhập tay.

![Hình 4. Phiếu Thu mua của đơn vị nước ngoài (ví dụ đơn vị tại Lào — LAK)](img/04-thu-mua-nuoc-ngoai.png)

*Hình 4. Phiếu Thu mua của đơn vị nước ngoài (ví dụ đơn vị tại Lào — LAK)*

**Khác biệt so với đơn vị trong nước:**

1. **Đơn giá theo nội tệ** (LAK/KHR trên độ) — giá mua thực tế tại nước sở tại.
2. **Mủ chén — Đơn giá tính theo**: *Độ TSC* hoặc *Độ DRC*.
3. **Tỷ giá thu mua** (1 nội tệ = ? VND) — quy đơn giá về đồng.
4. **Thu mua thành phẩm** — bảng theo chủng loại, nhập y như đơn vị trong nước (mục 3).
5. **Một dòng chủng loại**: chọn **Tiền** là *USD* thì nhập **Tỷ giá** (1 USD = ? VND) ngay ở dòng đó — hoặc bấm *Lấy tỷ giá VCB cho các dòng USD*.

> - Hai tỷ giá **khác nhau và độc lập**: tỷ giá nội tệ cho đơn giá mủ nước/mủ chén; tỷ giá USD nằm trên từng dòng thành phẩm.
> - Ô nền xám là hệ thống **tự quy đổi**, chỉ để xem.
> - Sản lượng và cách lưu giống đơn vị trong nước (mục 3).

## 5. Nhập Báo cáo tiêu thụ

**Vị trí:** Menu → Báo cáo tiêu thụ → Thêm số liệu ngày

Mỗi hợp đồng bán là một dòng, hệ thống tự cộng lại. Phiếu có **2 bảng nhập tách riêng** — **Tiêu thụ mủ khai thác** và **Tiêu thụ mủ thu mua** — để lưu trữ riêng từng nguồn mủ; phần **Tổng hợp tiêu thụ** vẫn cộng chung cả hai.

Vì mỗi hợp đồng có nhiều thông tin nên một bản ghi được bố trí **2 hàng**: hàng trên là số liệu bán, hàng dưới là chứng từ đi kèm.

![Hình 5. Phiếu Tiêu thụ — 2 bảng theo nguồn mủ, mỗi bản ghi 2 hàng](img/05-tieu-thu.png)

*Hình 5. Phiếu Tiêu thụ — 2 bảng theo nguồn mủ, mỗi bản ghi 2 hàng*

1. *(Hàng trên)* **Loại HĐ** (Dài hạn / Chuyến) · **Hình thức** (XK-UTXK / Nội tiêu) · **Loại mủ** · **SL (tấn)** · **Giá bán**.
2. *(Hàng trên)* **Loại tiền** — chọn VND hoặc USD **cho từng dòng**; chọn USD thì nhập **Tỷ giá** ngay ở dòng đó.
3. *(Hàng dưới)* **Ngày xuất kho** · **Ngày xuất hoá đơn** và 3 chứng từ đính kèm **Bộ Hợp đồng** · **Phiếu xuất kho** · **Hoá đơn** (PDF hoặc ảnh) — chưa có thì để trống; bấm tên file để mở lại.
4. **Tiêu thụ mủ thu mua** — bảng riêng ngay bên dưới, nhập y hệt bảng mủ khai thác.
5. **Tổng hợp tiêu thụ** — hệ thống tự cộng cả 2 bảng; **Giá BQ** = doanh thu ÷ sản lượng. Xong bấm **Lưu số liệu**.

> - **Mủ khai thác và mủ thu mua nhập ở 2 bảng riêng** để lưu trữ tách bạch, nhưng mọi số tổng (SL · doanh thu · giá BQ) đều cộng chung cả hai.
> - **Loại tiền chọn theo từng dòng** — trong ngày vừa bán USD vừa bán VNĐ vẫn nhập chung một phiếu.
> - Nút **Lấy tỷ giá VCB cho các dòng USD** điền tỷ giá Vietcombank cho mọi dòng đang chọn USD của **cả 2 bảng**.
> - Khối **Tổng hợp tiêu thụ** và cột **Doanh thu** từng dòng đều tự tính — không nhập tay.

## 6. Nhập Báo cáo tồn kho

**Vị trí:** Menu → Báo cáo tồn kho → Thêm số liệu ngày

Tồn kho là số liệu **tại thời điểm cuối ngày** (không cộng dồn giữa các ngày), đơn vị tính là **tấn**. Phiếu chia thành 4 khối theo tình trạng hàng. Riêng khối 3 — **hợp đồng đã ký** — **không phải nhập lại mỗi ngày**: mỗi hợp đồng nhập **một lần** rồi hệ thống tự tính vào tồn kho cho tới khi giao hàng.

![Hình 6. Phiếu Tồn kho — khối 3 là hợp đồng có vòng đời riêng](img/06-ton-kho.png)

*Hình 6. Phiếu Tồn kho — khối 3 là hợp đồng có vòng đời riêng*

**Bốn khối tồn kho:**

1. **Lấy tồn ngày trước** — chép khối 1, 2 và 4 của ngày gần nhất sang rồi sửa lại cho đúng ngày này.
2. **1. Tồn kho thành phẩm chế biến chưa nhập kho** — chủng loại + số lượng (tấn).
3. **2. Tồn kho thành phẩm đã nhập kho** — chủng loại + số lượng (tấn).
4. **3. Số lượng đã ký hợp đồng chưa giao** — nhập **một lần cho mỗi hợp đồng**, mỗi hợp đồng trải **2 hàng**.
5. *(Hàng trên)* **Chủng loại** · **Mã HĐ/PL** · **SL (tấn)** · **Đơn giá** · **Tiền** (VND/USD) · **Tỷ giá** khi chọn USD; **Thành tiền** tự tính. Cuối hàng có nút **lưu** và **xoá** của riêng hợp đồng đó.
6. *(Hàng dưới)* **Bắt đầu tồn kho** · **Lịch giao** · **Ngày giao** · **HĐ đã ký (scan)** — đính kèm bản Hợp đồng đã ký có đóng dấu (PDF hoặc ảnh).
7. **4. Tồn kho nguyên liệu chưa sản xuất (quy khô)** — 1 ô số lượng (tấn). Xong bấm **Lưu số liệu**.

> - **Hợp đồng đã ký tính vào tồn kho từ *Bắt đầu tồn kho* đến hết ngày TRƯỚC *Ngày giao*.** Lúc mới ký chỉ cần điền *Bắt đầu tồn kho* (để trống *Ngày giao*) — hợp đồng sẽ tự hiện ở tồn kho mọi ngày sau đó. Khi đã xuất kho thì **chỉ cần mở ra điền *Ngày giao*** là xong, không phải nhập lại gì nữa.
> - **Ngày bắt đầu phải trước *Ngày giao* (và *Lịch giao*) ít nhất 1 ngày** — nhập sai hệ thống sẽ báo và không cho lưu.
> - Mỗi hợp đồng **lưu riêng bằng nút lưu ở cuối hàng trên**, KHÔNG đi kèm nút *Lưu số liệu* của phiếu ngày (vì hợp đồng không thuộc riêng một ngày nào).
> - Nút **Lấy tồn ngày trước** KHÔNG chép khối 3 — hợp đồng tự nối sang ngày mới theo vòng đời của nó, chép lại sẽ thành nhân đôi. Nút này cũng không chép các dòng bán ở tab Tiêu thụ, vì tiêu thụ là số phát sinh trong ngày.
> - Khối **4** hiện với **mọi đơn vị**, **không phân biệt** đơn vị có nhà máy hay không. Đơn vị nào không có số thì để trống.
> - Khối **Tổng hợp tồn kho**: *Tồn kho thành phẩm* = khối 1 + khối 2. Khối 3 là **cam kết giao hàng**, đứng riêng — không cộng vào và không trừ khỏi tồn kho, nên ký nhiều hơn lượng đang có cũng không sao.
> - Chủng loại tách theo từng loại giống bảng Giá sàn Tập đoàn — **SVR CV 50** và **SVR CV60** là 2 loại riêng.

## 7. Nhập Nhu cầu thị trường

**Vị trí:** Menu → Nhu cầu thị trường

Ghi nhận **các lời chào hàng từ khách hàng, nhà sản xuất** và nhu cầu thị trường mà đơn vị nắm được trong ngày — dùng để phân tích yếu tố **Cầu** trong quan hệ Cung – Cầu.

![Hình 7. Nhập Nhu cầu thị trường](img/09-nhu-cau-thi-truong.png)

*Hình 7. Nhập Nhu cầu thị trường*

1. Bấm **Thêm nhu cầu** để mở ô nhập.
2. Chọn **ngày** ghi nhận nhu cầu.
3. Chọn **đơn vị** (tài khoản chỉ có đơn vị của mình).
4. Nhập **nội dung** — viết tự do, nên ghi rõ: khách hàng, chủng loại, số lượng, giá chào và thời điểm giao.
5. Bấm **Lưu**.
6. Muốn sửa nội dung đã ghi: bấm **biểu tượng bút** ở dòng tương ứng trong danh sách bên dưới.

> - Nên ghi rõ: **khách hàng hoặc nhà sản xuất nào · chủng loại · số lượng · mức giá chào · thời điểm giao hàng**. Càng cụ thể thì phần phân tích Cung – Cầu càng dùng được.
> - Đây là mục nhập **tự do bằng chữ**, không có ô số liệu.
> - Mỗi ngày mỗi đơn vị chỉ có **một nội dung** — nhập lại ngày đã có sẽ được nhắc dùng chức năng Sửa.
> - Mục này **không có nhập bằng Excel**.

## 8. Nhập Kế hoạch năm

**Vị trí:** Menu → Kế hoạch năm

Đây là số liệu của cả năm, chỉ nhập một lần và cập nhật lại khi có thay đổi — KHÔNG nhập hằng ngày. Số liệu này dùng để tính % thực hiện kế hoạch trong báo cáo.

![Hình 8. Màn Kế hoạch năm](img/07-ke-hoach-nam.png)

*Hình 8. Màn Kế hoạch năm*

1. Chọn **năm** cần khai.
2. **Kế hoạch thu mua** (tấn) — chỉ tiêu Tập đoàn giao hoặc kế hoạch của công ty.
3. **HĐ dài hạn đã ký** (tấn) — tổng sản lượng đã ký hợp đồng dài hạn trong năm.
4. **HĐ dài hạn năm trước chuyển sang** (tấn).
5. **HĐ chuyến năm trước chuyển sang** (tấn).

> - Số liệu **tự lưu khi rời khỏi ô** — không có nút Lưu riêng.
> - Màn này **chỉ hiện những đơn vị được giao kế hoạch thu mua**. Nếu không thấy đơn vị của mình, đề nghị quản trị viên bật ô **Có giao KH** ở Quản trị → Đơn vị thành viên.
> - Nếu tài khoản được giao nhiều đơn vị thì màn này hiện đủ các đơn vị đó (trừ đơn vị không được giao kế hoạch).

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

> - Chi tiết từng cột của ba biểu mẫu (kèm file mẫu và cách xử lý dòng lỗi): xem tài liệu riêng **Hướng dẫn nhập liệu bằng Excel** trong thư mục `docs/huong-dan/nhap-lieu-bang-excel/`.
> - File mẫu của đơn vị **không có cột “Đơn vị”** — hệ thống tự gán đúng đơn vị của tài khoản, không cần gõ tên.
> - **Không đổi tên hoặc xoá dòng tiêu đề** của file mẫu; nếu thiếu cột bắt buộc hệ thống sẽ báo và không đọc file.
> - Muốn sửa dòng lỗi: sửa lại trong file Excel rồi nhập lên lần nữa — các dòng đã ghi đúng sẽ được ghi đè, không bị nhân đôi.
> - Nhập Tiêu thụ không làm mất số Tồn kho của cùng ngày và ngược lại.
> - File **Tiêu thụ** ghi đè **toàn bộ** phần tiêu thụ của ngày đó, **cả mủ thu mua lẫn mủ khai thác**. Dòng nào đã nhập trên web mà không có trong file sẽ bị xoá — nên chép đủ cả 2 nguồn mủ vào file trước khi nhập lên.
> - **Mẫu Excel đã đổi cột** — luôn bấm *Tải mẫu Excel* để lấy file mới nhất, đừng dùng lại file tải từ trước (sai cột sẽ báo lỗi khi nhập lên).
> - Bốn cột **chọn từ danh sách** để trống được, nhưng phải điền đúng thì số mới vào đúng chỗ: *Đơn giá mủ chén tính theo* (Độ TSC / Độ DRC) ở mẫu **Thu mua**; *Nguồn mủ* (Mủ thu mua / Mủ khai thác) và *Giá bán bằng* (VND / USD) ở mẫu **Tiêu thụ**; *Đơn giá bằng* (VND / USD) ở mẫu **Tồn kho**. Bỏ trống thì hệ thống hiểu là Độ TSC · Mủ thu mua · VND.
> - Mẫu **Thu mua** đã bỏ 2 cột *SL tiêu thụ* và *Doanh thu* (chuyển sang biểu Tiêu thụ), thêm 3 cột: *SL thu mua thành phẩm* · *Đơn giá thành phẩm (VNĐ)* · *Đơn giá thành phẩm (ngoại tệ)*.
> - Mẫu **Tồn kho**: cột *Nhóm* có 3 lựa chọn — Chế biến chưa nhập kho · Đã nhập kho · **Đã ký HĐ**. Số lượng tính bằng **tấn**.
> - Mẫu **Tiêu thụ** có cột *Nguồn mủ* (chọn *Mủ thu mua* hoặc *Mủ khai thác* — để trống thì hiểu là **mủ thu mua**), cùng 2 cột ngày: *Ngày xuất kho* và *Ngày xuất hoá đơn*. Riêng **3 file đính kèm — bộ Hợp đồng · phiếu xuất kho · hoá đơn — phải tải lên trên web**, file Excel không mang theo file đính kèm được.
