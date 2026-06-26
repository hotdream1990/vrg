# Change Log — Tuần 3

> **Mục đích:** ghi nhận các thay đổi trong **Tuần 3** để anh xem nhanh trước, đồng thời làm
> **căn cứ cập nhật** `checklist-cong-viec.csv` ở lần kế tiếp.
>
> **Quy ước nhịp tuần:**
> - `checklist-cong-viec.csv` = **baseline Tuần 2** — toàn bộ task trong CSV là việc đã làm/đã chốt ở **2 tuần đầu**. *Chưa chỉnh CSV ở bước này.*
> - File này = **delta của Tuần 3** (chỉ những gì MỚI hoặc THAY ĐỔI so với CSV).
> - Khi merge vào CSV sau này: thêm cột **`Last Update`** (tuần cập nhật gần nhất); các dòng cũ để `Last Update = Tuần 2`, các thay đổi bên dưới ghi `Last Update = Tuần 3`.
> - Mục **chưa xong** sẽ vào CSV **Phần 2 (đang làm)** / **Phần 3 (backlog)** — *xử lý ở tương lai*.
>
> Mốc dự án: bắt đầu **15/06/2026** · Change log này lập ngày **26/06/2026**.

---

## Tóm tắt Tuần 3

| Nhóm thay đổi | Số lượng | Đích đến trong CSV (lần cập nhật sau) |
|---|---|---|
| **A. Mới hoàn thành** | 11 | → Phần 1 (Hoàn thành), `Last Update = Tuần 3` |
| **B. Cập nhật trạng thái/ghi chú** (mục Tuần 2) | 16 | cập nhật tại chỗ, `Last Update = Tuần 3` |
| **C. Đang làm / Backlog mới phát sinh** | 9 | → Phần 2 (đang làm) / Phần 3 (backlog) |

Điểm nhấn Tuần 3: hoàn thiện **xác thực & phân quyền (RBAC)**, **Bản tin ngày + xuất PPTX/PDF**, **màn Gợi ý điều chỉnh giá sàn (engine hồi quy + backtest)**; nhiều màn từ *bản demo* đã lên **dữ liệu/DB thật**; đã **nhận & import một phần** lịch sử giá sàn VRG.

---

## A. MỚI hoàn thành trong Tuần 3
*(chưa có trong CSV → đề xuất thêm vào Phần 1)*

| Hạng mục | Công việc | Trạng thái | Bằng chứng |
|---|---|---|---|
| 4. Hạ tầng, Bảo mật | Đăng nhập JWT + phân quyền theo vai trò (RBAC) + quản trị người dùng | Hoàn thành | commit `a354713`, `d8bc133` · `routers/auth.py`, `users.py` |
| 4. Hạ tầng, Bảo mật | Trang hồ sơ cá nhân + đổi mật khẩu | Hoàn thành | `ProfilePage.tsx` |
| 1. Dashboard | Nền tảng quản lý dữ liệu nội bộ + CRUD bản ghi giá | Hoàn thành | `0aaa7d4`, `c25dd0e` · `PriceSheetPage.tsx` |
| 1. Dashboard | Job quét giá tự động hằng ngày + bộ lập lịch (tích lũy lịch sử) | Hoàn thành | `68f772c` |
| 1. Dashboard | Quản lý & nhập lịch sử giá sàn VRG (49 lần ban hành 2023–2026) | Hoàn thành | `import_floor.py` · `VrgFloorPage.tsx` |
| 1. Dashboard | Bộ **công cụ** nhập lịch sử giá (sàn/FX/latex/physical) từ Excel Ban TTKD | Hoàn thành | `scripts/import-history/` — *công cụ đã xong; tiến độ NẠP dữ liệu xem mục Backfill ở phần C* |
| 1. Dashboard | Quản lý đơn vị thành viên | Hoàn thành | `member_unit.py` · `MemberUnitPage.tsx` |
| 1. Dashboard | Trang giá mủ nguyên liệu (giá mủ nước theo khu vực) | Hoàn thành | `RawMaterialPage.tsx` |
| 3. Trung tâm Điều hành AI | Trình tạo "Bản tin ngày" thị trường (soạn/sửa/xuất bản, danh sách + chi tiết) | Hoàn thành | `4f0235a`, `c25dd0e`, `b7d4b1a` · `services/bulletin/` |
| 3. Trung tâm Điều hành AI | Xuất "Bản tin ngày" ra PPTX & PDF | Hoàn thành | Playwright + Chrome |
| 2. Hệ thống Dự báo Giá | Màn "Gợi ý điều chỉnh giá sàn" — engine hồi quy + backtest toàn chuỗi + diễn giải NÂNG/GIỮ/HẠ | Hoàn thành | `32f28bb`, `e0d7c83`, `8a8ef3d` · `floor_suggest.py`, `floor_recommend.py` |

---

## B. CẬP NHẬT trạng thái / ghi chú (so với baseline Tuần 2)
*(mục đã có trong CSV → cập nhật tại chỗ)*

| Hạng mục | Công việc (theo CSV) | Cũ → Mới |
|---|---|---|
| 1. Dashboard | Khung giao diện Dashboard đa sàn | Ghi chú: *bản demo* → **Command Center hoàn chỉnh** (Ant Design, theme VRG, menu phân quyền) |
| 1. Dashboard | Bảng giá cập nhật + biểu đồ lịch sử | Ghi chú: *bản demo* → **dữ liệu thật** từ crawler |
| 1. Dashboard | Lưu trữ & tích lũy lịch sử giá hằng ngày | Ghi chú: *bản demo* → **DB thật TimescaleDB** (`fact_price`) |
| 4. Hạ tầng, Bảo mật | Thiết lập hệ thống & cơ sở dữ liệu | Ghi chú: *môi trường dev* → **TimescaleDB + pgvector** chạy thật |
| 1. Dashboard | Thu thập chỉ số vĩ mô (dầu, USD Index, PMI) | Ghi chú: **FX đã xong; dầu/USD Index/PMI chưa triển khai** (mới có `macro/fx.py`) |
| 1. Dashboard | Lấy giá Physical hằng ngày từ báo cáo anh Tâm | Ghi chú: đã có trang `PhysicalSheetPage` + `import_physical_staff.py`; còn **quy đổi THB/kg 2026** |
| 1. Dashboard | Xử lý & xuất báo cáo giá hằng ngày từ tài liệu anh Tâm | Ghi chú: một phần đã có qua **trình tạo Bản tin ngày**; còn tự động hóa từ file gốc |
| 1. Dashboard | So sánh giá sàn VRG ↔ quốc tế (Premium/Discount) | Ghi chú: đã có **tương quan giá sàn ↔ chỉ số quốc tế** trong màn Gợi ý; vẫn cần giá bán thực tế (HĐ Quý) |
| 2. Dự báo Giá | Mô hình dự báo SVR 10 (≤ 6% / 7 ngày) | Ghi chú: engine hồi quy giá sàn + backtest đã có (bước đệm); **mô hình chuỗi-thời-gian 7 ngày chưa làm** |
| 3. Trung tâm Điều hành AI | Cảnh báo đa kênh (Email/Zalo/Telegram) | Ghi chú: đã **phác thảo cơ chế ngưỡng lệch rổ/SHFE** (deferred) |
| 3. Trung tâm Điều hành AI | Báo cáo tự động 07:30 & 17:00 | Ghi chú: hạ tầng **job quét + scheduler đã có**; còn tự động phát theo giờ |
| 4. Hạ tầng, Bảo mật | Bảo mật: mã hóa, phân quyền, không lưu bên thứ ba | Trạng thái phần phân quyền: **RBAC đã xong**; còn mã hóa & data residency |
| 4. Hạ tầng, Bảo mật | Shadow testing (AI vs chuyên gia) | Ghi chú: đã có **backtest walk-forward toàn chuỗi** cho giá sàn (một dạng đối chiếu) |
| 5. VRG cung cấp | Lịch sử giá sàn (phạm vi cần: từ 2024) | Cần phối hợp → **đã nhận & nạp đủ phạm vi**: 30 lần ban hành (15/01/2024 → 09/06/2026). *Thống nhất chỉ lấy từ 2024, **không cần ≤ 2023**.* |
| 5. VRG cung cấp | Số liệu tồn kho & sản lượng (BCTM) | Ghi chú: đã có **biểu mẫu mẫu** (báo cáo tuần chị Hạnh, báo cáo năm anh Triều); **chưa đủ chuỗi & chưa import** |
| 5. VRG cung cấp | Giá Physical + biểu mẫu báo cáo | Ghi chú: có **báo cáo ngày của anh Tâm**, đang xử lý/nhập |

---

## C. Đang làm / Backlog mới phát sinh (Tuần 3)
*(chưa xong → đề xuất đưa vào CSV Phần 2/Phần 3 ở lần cập nhật sau — xử lý ở các tuần tới)*

| Hạng mục | Công việc | Trạng thái | → CSV |
|---|---|---|---|
| 1. Dashboard | **Backfill dữ liệu lịch sử vào hệ thống** (nạp giá quá khứ từ Excel Ban TTKD) — *đã nạp đến đâu: xem bảng bên dưới* | Đang làm | Phần 2 |
| 1. Dashboard | Hoàn tất trang Physical: quy đổi giá THB/kg (2026) → USD/T + đưa vào chuỗi | Đang làm | Phần 2 |
| 1. Dashboard | Gắn route/menu cho màn Gợi ý + Physical (chờ tách khỏi nhánh chung) | Đang làm | Phần 2 |
| 2. Dự báo Giá | **Trang quản lý Tồn kho & Tiêu thụ** — *CHƯA có trong hệ thống* (chưa có bảng DB), **chờ dữ liệu chuỗi từ chuyên viên** (chị Hạnh báo cáo tuần / anh Triều báo cáo năm) | Chờ phối hợp | Phần 3 |
| 1. Dashboard | **Crawler giá Physical từ marketscreener.com** ("Asian physical rubber prices", [link](https://www.marketscreener.com/search/?q=Asian+physical+rubber+prices)) — nguồn chính cho physical **2026+** theo yêu cầu ban đầu | Backlog | Phần 3 |
| 1. Dashboard | **Gỡ/ngưng ANRPC** (không còn cần) — dọn wiring ở bản tin / KPI / scan / crawler khi nguồn physical mới vào | Backlog | Phần 3 |
| 1. Dashboard | Crawler vĩ mô: dầu thô / butadiene / USD Index / PMI | Backlog | Phần 3 |
| 2. Dự báo Giá | Cải tiến mô hình giá sàn (giảm "thổi phồng" biên độ điều chỉnh) khi có thêm dữ liệu | Backlog | Phần 3 |
| 3. Trung tâm Điều hành AI | Cảnh báo tự động theo ngưỡng lệch rổ/SHFE | Backlog | Phần 3 |

---

## D. Backfill — đã nạp đến đâu *(chốt 26/06/2026)*

> Backfill = nạp dữ liệu giá **quá khứ** vào DB (`fact_price`, `vrg_floor_price`) bằng bộ công cụ
> `scripts/import-history/`. Khác với *tính năng quản lý số liệu* (đã xong ở mục A).
>
> **Phạm vi dữ liệu thống nhất: từ 2024 trở đi** — *không cần dữ liệu ≤ 2023.*

| Nhóm dữ liệu | Nguồn | Khoảng ĐÃ NẠP | Số ngày | Tình trạng |
|---|---|---|---|---|
| Tỷ giá | `fx` | 02/01/2024 → 24/06/2026 | 596 | Đủ (5 loại) |
| Physical Malaysia | `lgm` | 02/01/2024 → 19/06/2026 | 479 | Đủ (7 grade) |
| Physical (chuyên viên) | `reuters` | 14/05/2024 → 29/12/2025 | 269 | Lịch sử tới 2025; **physical 2026+ chuyển sang marketscreener** (backlog) |
| Settlement SGX | `sgx` | 02/01/2024 → 09/06/2026 | 501 | Đủ (2 grade) |
| Settlement SHFE | `shfe` | 02/01/2024 → 18/06/2026 | 569 | Đủ |
| Settlement TOCOM/OSE | `tocom` | 04/01/2024 → 19/06/2026 | 511 | Đủ (2 grade) |
| Giá mủ nước (thu mua) | `vrg/purchase` | 21/06/2024 → 20/06/2026 | 302 | Đủ (12 loại) |
| Giá mủ nước (theo khu vực) | `vrg/region` | 08/07/2024 → 09/06/2026 | 312 | Đủ (4 KV) |
| **Giá sàn VRG (target)** | `vrg_floor_price` | 15/01/2024 → 09/06/2026 | 30 lần | Đủ (đúng phạm vi cần — **từ 2024**) |
| ~~ANRPC~~ | `anrpc` | 15–16/06/2026 | 2 | **Không còn cần** — không vào model/lưới physical; sẽ bỏ, thay bằng nguồn physical mới (marketscreener) |
| Vĩ mô (dầu/USD Index/PMI) | — | — | 0 | **Chưa nạp** |
| Tồn kho / Tiêu thụ | — | — | 0 | **Chưa có bảng — chờ dữ liệu chuyên viên** |

**Việc backfill còn lại (trong phạm vi từ 2024):** (1) vĩ mô (dầu/USD Index/PMI), (2) tồn kho/tiêu thụ (chặn vì thiếu dữ liệu chuỗi từ chuyên viên). *Physical 2026+ sẽ lấy từ **marketscreener** (xem backlog phần C); **ANRPC bỏ** — không backfill.*

---

## Hướng dẫn cập nhật `checklist-cong-viec.csv` (cho lần sau)

1. Thêm cột **`Last Update`** vào CSV (giá trị: `Tuần 2`, `Tuần 3`, …).
2. Toàn bộ dòng hiện có → đặt `Last Update = Tuần 2`.
3. **Mục A** → thêm vào **Phần 1 (Đã hoàn thành)**, `Last Update = Tuần 3`.
4. **Mục B** → sửa Trạng thái/Ghi chú tương ứng, `Last Update = Tuần 3`.
5. **Mục C** → thêm vào **Phần 2 / Phần 3**, `Last Update = Tuần 3`.
6. Tuần 4 lặp lại: tạo `change-log-week-04.md`, rồi merge vào CSV.
