---
name: bao-cao-nhap-lieu
description: Chụp ảnh bảng (kiểu Excel) thống kê tình trạng nhập liệu của đơn vị thành viên VRG — ai chưa nhập gì, ai nhập thiếu một phần, ai nhập sai đơn vị tính (giá mủ nguyên liệu đ/độ, giá bán triệu đ/tấn). Dùng khi cần nhắc/đốc thúc các đơn vị nhập liệu, gửi ảnh qua Zalo/email, hoặc rà soát chất lượng số liệu trước khi ra bản tin/báo cáo.
---

# Báo cáo tình trạng nhập liệu của đơn vị

Ra **2 ảnh PNG** gửi thẳng cho các đơn vị (không cần mở hệ thống):

| Ảnh | Nội dung |
|---|---|
| `A-don-vi-chua-nhap-lieu.png` | **Không nộp gì trong kỳ** + **Thiếu một phần**, theo 3 mục: Thu mua · Tiêu thụ–Tồn kho · Giá mủ nguyên liệu |
| `B-don-vi-nhap-sai-don-vi-tinh.png` | **Nhập sai đơn vị tính**: giá mủ nguyên liệu (phải là đ/độ) và giá bán ở biểu Tiêu thụ (phải là triệu đ/tấn) |

## Chạy

```bash
uv run --directory apps/api python .claude/skills/bao-cao-nhap-lieu/scripts/make-report.py
```

| Tuỳ chọn | Mặc định | Ý nghĩa |
|---|---|---|
| `--days N` | 7 | Kỳ xét "đã nộp chưa" = N ngày gần nhất |
| `--out DIR` | `plans/visuals` | Thư mục lưu ảnh (có plan đang mở thì trỏ vào `{plan_dir}/visuals/`) |
| `--local` | tắt | Lấy số liệu ở DB local thay vì prod (để thử) |

Số liệu lấy từ **DB prod** qua SSH (dùng chung `.claude/skills/deploy/dokploy-target.local.env`) — DB
không mở ra ngoài. Ảnh chụp bằng Playwright trong venv `apps/api`.

## Luật nghiệp vụ đã cài sẵn

**Thu mua — đơn vị không có chỉ tiêu thì KHÔNG tính là thiếu.** `member_unit.has_purchase_plan = false`
→ ô hiện *"không áp dụng"* (xám), không xếp vào nhóm chưa nộp. Admin bật/tắt cờ này ở
**Quản trị → Đơn vị thành viên**; sai cờ là báo oan đơn vị.

**Chia nhóm:** thiếu **mọi** mục áp dụng → *KHÔNG NỘP GÌ TRONG KỲ*; thiếu **ít nhất một** → *THIẾU MỘT PHẦN*.

**Giá mủ nguyên liệu** đọc cả `purchase` (mủ nước) lẫn `purchase_cup` (mủ chén) ở lớp `vrg_unit`
(đơn vị tự khai) — đơn vị chỉ mua mủ chén vẫn tính là đã nhập. Lớp `vrg` là giá chuyên viên chốt,
KHÔNG dùng ở đây.

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

- Truy vấn: `scripts/collect.sql` (3 nhóm A/B/C, mỗi dòng ra là chuỗi ngăn bằng `|`).
- HTML/CSS + chụp ảnh: `scripts/make-report.py` (`page_missing`, `page_wrong`, `CSS`).
- Đổi ngưỡng phát hiện thì sửa **cả** `collect.sql` lẫn tiêu đề mục trong `page_wrong` cho khớp.

## Sau khi có ảnh

Gửi kèm 1 câu chốt: kỳ nào, bao nhiêu đơn vị chưa nộp, bao nhiêu đơn vị sai đơn vị tính, hạn sửa.
Đơn vị sửa bằng cách mở lại phiếu ngày đó (**Báo cáo thu mua / Tiêu thụ / Giá mủ nguyên liệu**) — nếu
ngày đã ngoài cửa sổ sửa thì admin phải nới `MEMBER_EDIT_WINDOW_DAYS` ở **Quản trị → Cấu hình hệ thống**.
