---
name: bao-cao-nhap-lieu
description: Xuất ảnh PNG + file Excel thống kê tình trạng nhập liệu của đơn vị thành viên VRG — ai chưa nhập gì, ai nhập thiếu một phần, ai nhập sai đơn vị tính (giá mủ nguyên liệu đ/độ, giá bán triệu đ/tấn), kế hoạch năm khai thiếu. Dùng khi cần nhắc/đốc thúc các đơn vị nhập liệu, gửi ảnh qua Zalo/email, hoặc rà soát chất lượng số liệu trước khi ra bản tin/báo cáo.
---

# Báo cáo tình trạng nhập liệu của đơn vị

Ra **5 ảnh PNG** gửi thẳng cho các đơn vị (không cần mở hệ thống):

| Ảnh | Nội dung |
|---|---|
| `A-don-vi-chua-nhap-lieu.png` | **Không nộp gì trong kỳ** + **Thiếu một phần** theo **2 biểu** (Thu mua · Tiêu thụ–Tồn kho), kèm bảng phụ **có mua nhưng chưa nhập đơn giá** |
| `B-don-vi-nhap-sai-don-vi-tinh.png` | **Nhập sai đơn vị tính**: giá mủ nguyên liệu (phải là đ/độ) và giá bán ở biểu Tiêu thụ (phải là triệu đ/tấn) |
| `C-don-vi-chua-nhap-ton-kho.png` | RIÊNG biểu **Tồn kho**, cùng khuôn ảnh A nhưng liệt kê **từng ngày còn thiếu** của mỗi đơn vị — dùng khi chỉ đốc thúc tồn kho (`--only stock`) |
| `D-don-vi-chua-nhap-thu-mua.png` | RIÊNG biểu **Thu mua** cho kỳ DÀI: gom theo **tháng** (T1…T12) thay vì liệt kê ngày — kỳ 200 ngày mà kể từng ngày thì không ai đọc (`--only purchase`) |
| `E-ke-hoach-nam-khai-thieu.png` | **Kế hoạch năm**: đơn vị bỏ trống chỉ tiêu nào trong **5 ô** của màn đó (`--only plan`) |

Kèm **1 file Excel** `tinh-trang-nhap-lieu-DD-MM-YYYY.xlsx` — 6 sheet đúng nội dung 5 ảnh (A ·
A2 thiếu đơn giá · B · C · D · E), nhưng **liệt kê ĐỦ MỌI ĐƠN VỊ** (kể cả đơn vị nộp đủ) và có cột
`Nhóm` · `Tỷ lệ nộp` để Ban TTKD tự lọc. Ảnh để gửi Zalo, Excel để làm việc.

## Kỳ CHUẨN (chốt với anh Trung 15/08/2026 — cứ thế mà chạy, không hỏi lại)

| Nội dung | Kỳ | Vì sao |
|---|---|---|
| Ảnh A · C (tình trạng nộp, tồn kho) | **từ 24/07** đến ngày chốt | Tài khoản đơn vị cấp giữa tháng 7, bản ghi sớm nhất 24–27/07 → kỳ này mới so được giữa các đơn vị |
| Ảnh D (thu mua) | **từ 01/01** đến ngày chốt | Xem cả năm, gom theo tháng |
| Ảnh B (sai đơn vị tính) | không giới hạn kỳ | Lỗi còn tồn là còn phải sửa |
| Ảnh E (kế hoạch năm) | theo năm của ngày chốt | — |

Ngày chốt do người yêu cầu nêu (vd 10/08) — truyền vào `--until`, KHÔNG mặc định hôm qua.

## Chạy

Bộ 3 lệnh cho một lần báo cáo đầy đủ (thay `10-08` bằng ngày chốt; 18 = số ngày từ 24/07 tới ngày
chốt, 222 = số ngày từ 01/01 tới ngày chốt — đếm cả 2 đầu):

```bash
R=.claude/skills/bao-cao-nhap-lieu/scripts; O="$PWD/plans/visuals/2026-08-10"
uv run --directory apps/api python "$PWD/$R/make-report.py" --days 18 --until 2026-08-10 --out "$O"
uv run --directory apps/api python "$PWD/$R/make-report.py" --only purchase --days 222 --until 2026-08-10 --out "$O"
uv run --directory apps/api --with openpyxl python "$PWD/$R/make-xlsx.py" --days 18 --purchase-days 222 --until 2026-08-10 --out "$O"
```

⚠ Truyền **đường dẫn tuyệt đối** cho cả script lẫn `--out`: `uv run --directory apps/api` đổi thư
mục làm việc sang `apps/api`, đường dẫn tương đối sẽ trỏ sai chỗ.

Lệnh 2 chạy sau lệnh 1 để **ghi đè ảnh D** bằng bản kỳ dài (lệnh 1 dựng D theo kỳ ngắn).

| Tuỳ chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--days N` | 7 | Kỳ xét "đã nộp chưa" = N ngày |
| `--until NGÀY` | **hôm qua** | Ngày cuối kỳ. Mặc định BỎ hôm nay: hôm nay chưa hết ngày, đơn vị chưa nhập không phải là nợ — kể vào là nhắc oan và làm loãng danh sách thật |
| `--out DIR` | `plans/visuals` | Thư mục lưu ảnh (có plan đang mở thì trỏ vào `{plan_dir}/visuals/`) |
| `--local` | tắt | Lấy số liệu ở DB local thay vì prod (để thử) |
| `--only` | `all` | `stock` · `purchase` · `plan` = chỉ dựng ảnh của riêng biểu đó |

`make-xlsx.py` dùng chung `--days` · `--until` · `--out` · `--local`, thêm `--purchase-days N` cho
sheet Thu mua khi kỳ thu mua khác kỳ chung (script tự hỏi lại DB đúng kỳ đó). Cần `--with openpyxl`.

Số liệu lấy từ **DB prod** qua SSH (dùng chung `.claude/skills/deploy/dokploy-target.local.env`) — DB
không mở ra ngoài. Ảnh chụp bằng Playwright trong venv `apps/api`.

## Luật nghiệp vụ đã cài sẵn

**Thu mua — đơn vị không có chỉ tiêu thì KHÔNG tính là thiếu.** Công tắc là **số kế hoạch thu mua
của năm gần nhất ≤ năm nay**: `> 0` mới phải nộp, không thì ô hiện *"không áp dụng"* (xám). Đơn vị sửa
số này ở **Kế hoạch năm** (cờ `member_unit.has_purchase_plan` đã BỎ từ 03/08/2026 — đừng dùng lại).

**"Đã nộp" = có ô số liệu THẬT của chính biểu đó**, không phải "có bản ghi": biểu Tồn kho còn mang
hàng trăm bản ghi cũ của biểu Tiêu thụ nên đếm theo bản ghi sẽ ra tỷ lệ nộp ảo. Luật này phải khớp
`unit_daily_fields.has_data` — cùng luật với màn *Theo dõi nộp báo cáo* và bảng nhắc việc của đơn vị.

**Chia nhóm:** thiếu **mọi** biểu áp dụng → *KHÔNG NỘP GÌ TRONG KỲ*; thiếu **ít nhất một** → *THIẾU MỘT PHẦN*.

**Kế hoạch năm — khai số 0 là ĐÃ KHAI** (nghĩa là "không có"), chỉ ô **NULL** mới tính là bỏ trống.
Gộp hai thứ này là báo oan đơn vị cố ý khai 0. 5 chỉ tiêu theo đúng thứ tự cột trên màn hình.

⚠ **Kỳ dài không phản ánh ý thức đơn vị nếu hệ thống chưa chạy**: bản ghi thu mua sớm nhất trên prod
chỉ ghi từ **24–27/07/2026** (tài khoản đơn vị cấp giữa tháng 7), nên báo cáo "từ đầu năm" cho ra
~22% là do chưa có hệ thống, không phải đơn vị lười. Muốn so sánh giữa các đơn vị thì lấy kỳ **từ
24/07/2026** trở đi.

**Chỉ có 2 biểu phải nộp — KHÔNG tách "Giá mủ nguyên liệu" thành mục thứ 3.** Đơn giá mủ nước/mủ chén
nhập **ngay trong biểu Thu mua** (ô "Đơn giá thu mua"), chỉ là được lưu sang kho giá `vrg_unit` cho các
màn khác dùng. Đã đo trên prod: **0 trường hợp** có đơn giá mà không có biểu Thu mua. Tách ra thành cột
riêng là đếm trùng và **báo oan** đơn vị có ngày `no_purchase` (không tổ chức thu mua → ngày đó vốn
không có giá): làm vậy nhóm "thiếu một phần" phình từ 7 lên 29 đơn vị.

**Thiếu đơn giá** vì thế là lỗi *bên trong* biểu Thu mua → bảng phụ riêng ở cuối ảnh A: ngày có tổ chức
thu mua mà ô đơn giá còn trống. Ngày `no_purchase = true` được loại ra; ngày có tổ chức mà mua được
0 tấn thì **vẫn phải có giá đã công bố** nên giữ lại. Đọc cả `purchase` lẫn `purchase_cup` ở lớp
`vrg_unit` (đơn vị tự khai) — lớp `vrg` là giá chuyên viên chốt, KHÔNG dùng ở đây.

**Ngưỡng "sai đơn vị tính"** (mốc phát hiện, không phải mốc nghiệp vụ):

| Chỉ tiêu | Đơn vị đúng | Mặt bằng | Bắt lỗi khi |
|---|---|---|---|
| Giá mủ nguyên liệu | đồng/độ TSC | 100 – 1.500 | `> 1.500` (gõ nhầm đồng/kg hoặc đồng/tấn) |
| Giá bán (VND) | triệu đồng/tấn | 40 – 70 | `> 200` (gõ nhầm đồng/tấn) |
| Giá bán (USD) | USD/tấn | 1.400 – 2.200 | `> 10.000` |

⚠ **Loại tiền của dòng bán phải suy đúng như form nhập**: dòng → `sales_ccy` của ngày → mặc định của
đơn vị (trong nước VND · nước ngoài USD). Bỏ bước này thì 1.640 USD/tấn bị đọc thành 1.640 triệu đ/tấn
→ **báo oan các đơn vị Lào/Campuchia**.

Ảnh B **không giới hạn kỳ**: sai đơn vị tính là lỗi còn tồn trên hệ thống, còn sai là còn phải sửa.
Ảnh A thì giới hạn theo `--days`.

## Sửa nội dung/bố cục

- Truy vấn: `scripts/collect.sql` — 7 nhóm **A** tình trạng nộp · **D** thiếu đơn giá · **B** giá mủ
  sai đơn vị · **C** giá bán sai đơn vị · **E** tồn kho theo ngày · **F** thu mua theo tháng · **G** kế hoạch năm; mỗi dòng ra là chuỗi ngăn bằng `|`, ký tự đầu là tên nhóm.
- HTML/CSS + chụp ảnh: `scripts/make-report.py` (`page_missing`, `page_wrong`,
  `page_stock_missing`, `page_purchase_months`, `page_year_plan`, `CSS`). Bảng nhiều cột thì truyền bề ngang ở tham số thứ 3 của
  mỗi trang trong `shoot()`, không thì tên đơn vị vắt dòng và ảnh cao gấp mấy lần.
- Đổi ngưỡng phát hiện thì sửa **cả** `collect.sql` lẫn tiêu đề mục trong `page_wrong` cho khớp.
- Bản Excel: `scripts/make-xlsx.py` — **nạp lại `collect()` của make-report.py**, không tự truy vấn,
  nên ảnh và Excel không bao giờ lệch số. Thêm/bớt cột thì sửa hàm `build()` trong file này.

## Sau khi có ảnh

Gửi kèm 1 câu chốt: kỳ nào, bao nhiêu đơn vị chưa nộp, bao nhiêu đơn vị sai đơn vị tính, hạn sửa.
Đơn vị sửa bằng cách mở lại phiếu ngày đó (**Báo cáo thu mua / Tiêu thụ / Giá mủ nguyên liệu**) — nếu
ngày đã ngoài cửa sổ sửa thì admin phải nới `MEMBER_EDIT_WINDOW_DAYS` ở **Quản trị → Cấu hình hệ thống**.
