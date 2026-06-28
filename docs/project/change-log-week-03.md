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
> Mốc dự án: bắt đầu **15/06/2026** · Change log lập **26/06/2026** · **cập nhật 28/06/2026** (bổ sung tồn kho, marketscreener, scheduler, cấu hình, AI bản tin — xem Phần E).

---

## Tóm tắt Tuần 3

| Nhóm thay đổi | Số lượng | Đích đến trong CSV (lần cập nhật sau) |
|---|---|---|
| **A. Mới hoàn thành** | 11 | → Phần 1 (Hoàn thành), `Last Update = Tuần 3` |
| **B. Cập nhật trạng thái/ghi chú** (mục Tuần 2) | 16 | cập nhật tại chỗ, `Last Update = Tuần 3` |
| **C. Đang làm / Backlog mới phát sinh** | 9 | → Phần 2 (đang làm) / Phần 3 (backlog) |

Điểm nhấn Tuần 3: hoàn thiện **xác thực & phân quyền (RBAC)**, **Bản tin ngày + xuất PPTX/PDF**, **màn Gợi ý điều chỉnh giá sàn (engine hồi quy + backtest)**; nhiều màn từ *bản demo* đã lên **dữ liệu/DB thật**; đã **nhận & import một phần** lịch sử giá sàn VRG.

> ⭐ **2 trọng tâm của tuần (nhấn mạnh):**
>
> **1. Backfill dữ liệu lịch sử — khối lượng lớn, tốn nhiều công.** Đây là phần nặng nhất tuần: nạp **~3.500+ điểm dữ liệu** giá quá khứ (2024→nay) từ file Excel Ban TTKD vào DB — tỷ giá, giá 4 sàn quốc tế (settlement), giá mủ nước, **30 lần ban hành giá sàn VRG** (target của mô hình). Mỗi nguồn 1 định dạng riêng, phải viết bộ công cụ parse + đối chiếu + sửa lỗi quy đổi (vd LATEX). **Không có chuỗi lịch sử này thì không thể chạy gợi ý giá sàn.**
>
> **2. Gợi ý giá sàn — tính năng quan trọng nhất + các màn nhập liệu phục vụ nó.** Màn **"Gợi ý điều chỉnh giá sàn"** (NÂNG/GIỮ/HẠ kèm diễn giải + backtest toàn chuỗi + ma trận kịch bản + **xuất tờ trình**) là đầu ra cốt lõi cho lãnh đạo. Để nó chạy đúng, tuần này dựng/hoàn thiện **các màn nhập liệu nuôi mô hình**: Bảng giá các sàn · Tỷ giá · Giá Physical · **Tồn kho** · Giá sàn Tập đoàn — admin/chuyên viên nhập & sửa trực tiếp, dữ liệu chảy thẳng vào engine + backtest.

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
| Physical (chuyên viên) | `reuters` | 14/05/2024 → 29/12/2025 | 269 | Lịch sử tới 2025 (Excel chuyên viên) |
| Physical 2026 (marketscreener) | `reuters` | 28/04/2026 → 26/06/2026 | 37 | **ĐÃ NỐI TIẾP** — crawler marketscreener (Reuters); còn lấp 01–04/2026 |
| Tồn kho (báo cáo tuần) | `fact_inventory` | (từ báo cáo chị Hạnh) | 71 tuần | **ĐÃ NẠP** — tồn kho + đã có hợp đồng; đưa vào mô hình giá sàn |
| Settlement SGX | `sgx` | 02/01/2024 → 09/06/2026 | 501 | Đủ (2 grade) |
| Settlement SHFE | `shfe` | 02/01/2024 → 18/06/2026 | 569 | Đủ |
| Settlement TOCOM/OSE | `tocom` | 04/01/2024 → 19/06/2026 | 511 | Đủ (2 grade) |
| Giá mủ nước (thu mua) | `vrg/purchase` | 21/06/2024 → 20/06/2026 | 302 | Đủ (12 loại) |
| Giá mủ nước (theo khu vực) | `vrg/region` | 08/07/2024 → 09/06/2026 | 312 | Đủ (4 KV) |
| **Giá sàn VRG (target)** | `vrg_floor_price` | 15/01/2024 → 09/06/2026 | 30 lần | Đủ (đúng phạm vi cần — **từ 2024**) |
| ~~ANRPC~~ | `anrpc` | 15–16/06/2026 | 2 | **ĐÃ GỠ** — thay bằng nguồn Reuters (marketscreener) |
| Vĩ mô (dầu/USD Index/PMI) | — | — | 0 | **Chưa nạp** |
| Tồn kho / Tiêu thụ | — | — | 0 | **Chưa có bảng — chờ dữ liệu chuyên viên** |

**Việc backfill còn lại (trong phạm vi từ 2024):** (1) vĩ mô (dầu/USD Index/PMI) — chưa nạp; (2) tiêu thụ — chờ dữ liệu chuỗi từ chuyên viên; (3) physical **01–04/2026** (marketscreener không cho tra cứu bài cũ). *Đã xong trong tuần: **physical 2026 (marketscreener)**, **tồn kho 71 tuần**; **ANRPC đã gỡ**.*

---

## E. Bổ sung cuối Tuần 3 *(27–28/06 — sau bản chốt 26/06)*

*Nhiều mục ở Phần C đã chuyển từ "backlog/đang làm" sang **Hoàn thành**.*

| Hạng mục | Công việc | Trạng thái | Bằng chứng |
|---|---|---|---|
| 2. Dự báo Giá ⭐ | **Tồn kho** đưa vào mô hình gợi ý giá sàn — import báo cáo tuần (chị Hạnh) + **trang nhập liệu Tồn kho** + biến thể mô hình có tồn kho (tổng & tồn tự do) + so sánh trước/sau + vẽ tồn kho tự do trên backtest | Hoàn thành | `6550107`, `d062193`, `58212de`, `eb83edb`, `b6e1169`, `161a8af` |
| 1. Dashboard | **Crawler giá Physical từ marketscreener.com** (chuỗi Reuters "Asian physical rubber prices"; Firefox vượt chặn bot + đăng nhập) — lấp giá giao ngay **2026** | Hoàn thành | `c12c907`, `4e9b4aa` |
| 1. Dashboard | **Gỡ ANRPC**, chuyển nguồn physical sang Reuters | Hoàn thành | `d45d4b1` |
| 1. Dashboard | **Lịch chạy tự động trong ứng dụng** (scheduler thay cron hệ điều hành) + trang "Lịch chạy" (xem/sửa giờ, bật-tắt, chạy ngay) | Hoàn thành | `f0eaddb`, `8e4d90f` |
| 1. Dashboard | **Nhật ký quét giá** trên giao diện + nút **"Quét ngay" theo nguồn** trên từng màn | Hoàn thành | `9277069`, `8b0eb84`, `5a316ac` |
| 4. Hạ tầng | **Trang Cấu hình hệ thống (admin)** — tài khoản nguồn dữ liệu/proxy/AI theo tab; mật khẩu được ẩn; model AI chọn từ danh sách | Hoàn thành | `d17d407`, `c43352e`, `6664ae9`, `14bab67` |
| 3. Trung tâm Điều hành AI | **AI phân tích thông tin thị trường** cho Bản tin ngày — lấy tin vietnambiz.vn → AI viết đoạn nhận định (OpenAI) | Hoàn thành | `094acc3`, `234c32e`, `c5d8d29` |

---

## Hướng dẫn cập nhật `checklist-cong-viec.csv` (cho lần sau)

1. Thêm cột **`Last Update`** vào CSV (giá trị: `Tuần 2`, `Tuần 3`, …).
2. Toàn bộ dòng hiện có → đặt `Last Update = Tuần 2`.
3. **Mục A** → thêm vào **Phần 1 (Đã hoàn thành)**, `Last Update = Tuần 3`.
4. **Mục B** → sửa Trạng thái/Ghi chú tương ứng, `Last Update = Tuần 3`.
5. **Mục C** → thêm vào **Phần 2 / Phần 3**, `Last Update = Tuần 3`.
6. Tuần 4 lặp lại: tạo `change-log-week-04.md`, rồi merge vào CSV.
