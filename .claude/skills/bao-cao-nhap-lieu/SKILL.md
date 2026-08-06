---
name: bao-cao-nhap-lieu
description: Chụp ảnh bảng (kiểu Excel) thống kê tình trạng nhập liệu của đơn vị thành viên VRG — ai chưa nhập gì, ai nhập thiếu một phần, ai nhập sai đơn vị tính (giá mủ nguyên liệu đ/độ, giá bán triệu đ/tấn). Dùng khi cần nhắc/đốc thúc các đơn vị nhập liệu, gửi ảnh qua Zalo/email, hoặc rà soát chất lượng số liệu trước khi ra bản tin/báo cáo.
---

# Báo cáo tình trạng nhập liệu của đơn vị

Ra **3 ảnh PNG** gửi thẳng cho các đơn vị (không cần mở hệ thống):

| Ảnh | Nội dung |
|---|---|
| `A-don-vi-chua-nhap-lieu.png` | **Không nộp gì trong kỳ** + **Thiếu một phần** theo **2 biểu** (Thu mua · Tiêu thụ–Tồn kho), kèm bảng phụ **có mua nhưng chưa nhập đơn giá** |
| `B-don-vi-nhap-sai-don-vi-tinh.png` | **Nhập sai đơn vị tính**: giá mủ nguyên liệu (phải là đ/độ) và giá bán ở biểu Tiêu thụ (phải là triệu đ/tấn) |
| `C-don-vi-chua-nhap-ton-kho.png` | RIÊNG biểu **Tồn kho**, cùng khuôn ảnh A nhưng liệt kê **từng ngày còn thiếu** của mỗi đơn vị — dùng khi chỉ đốc thúc tồn kho (`--only stock`) |

## Chạy

```bash
uv run --directory apps/api python .claude/skills/bao-cao-nhap-lieu/scripts/make-report.py
```

| Tuỳ chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--days N` | 7 | Kỳ xét "đã nộp chưa" = N ngày |
| `--until NGÀY` | **hôm qua** | Ngày cuối kỳ. Mặc định BỎ hôm nay: hôm nay chưa hết ngày, đơn vị chưa nhập không phải là nợ — kể vào là nhắc oan và làm loãng danh sách thật |
| `--out DIR` | `plans/visuals` | Thư mục lưu ảnh (có plan đang mở thì trỏ vào `{plan_dir}/visuals/`) |
| `--local` | tắt | Lấy số liệu ở DB local thay vì prod (để thử) |
| `--only stock` | `all` | Chỉ dựng ảnh C (Tồn kho); mặc định dựng cả 3 ảnh |

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

- Truy vấn: `scripts/collect.sql` — 5 nhóm **A** tình trạng nộp · **D** thiếu đơn giá · **B** giá mủ
  sai đơn vị · **C** giá bán sai đơn vị · **E** tồn kho theo ngày; mỗi dòng ra là chuỗi ngăn bằng `|`, ký tự đầu là tên nhóm.
- HTML/CSS + chụp ảnh: `scripts/make-report.py` (`page_missing`, `page_wrong`,
  `page_stock_missing`, `CSS`). Bảng nhiều cột thì truyền bề ngang ở tham số thứ 3 của
  mỗi trang trong `shoot()`, không thì tên đơn vị vắt dòng và ảnh cao gấp mấy lần.
- Đổi ngưỡng phát hiện thì sửa **cả** `collect.sql` lẫn tiêu đề mục trong `page_wrong` cho khớp.

## Sau khi có ảnh

Gửi kèm 1 câu chốt: kỳ nào, bao nhiêu đơn vị chưa nộp, bao nhiêu đơn vị sai đơn vị tính, hạn sửa.
Đơn vị sửa bằng cách mở lại phiếu ngày đó (**Báo cáo thu mua / Tiêu thụ / Giá mủ nguyên liệu**) — nếu
ngày đã ngoài cửa sổ sửa thì admin phải nới `MEMBER_EDIT_WINDOW_DAYS` ở **Quản trị → Cấu hình hệ thống**.
