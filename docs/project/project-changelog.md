# Changelog Dự án

Ghi nhận thay đổi đáng kể. Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/).

## [Unreleased]
### Added
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
  - **2 loại mủ nguyên liệu mới** ở biểu Thu mua: *Mủ nguyên liệu nước chưa cán vắt (chén)* và
    *Mủ nguyên liệu đã cán vắt (RSS)*, **đơn giá tính riêng từng loại** (đồng/kg).
  - **Quy khô bắt buộc** khi bán LATEX và 2 loại nguyên liệu mới; **chi phí trên từng dòng bán**;
    **loại tiền mở rộng** VND · USD · **LAK · KHR** (nội tệ đơn vị Lào/Campuchia, buộc có tỷ giá).
  - **Tái cấu trúc menu** theo trục mới: *Số liệu thị trường (tự động/thủ công)* · *Số liệu đơn vị
    thành viên* · *Quản lý hợp đồng* · *Báo cáo & Thống kê* · *Phân tích & Bản tin*.
  - Quyền mới `sales_contract` (2 cấp Xem/Sửa). **Hậu-deploy phải cấp lại quyền này** cho chuyên viên.
- Script chuyển dữ liệu cũ `scripts/migrate-sales-contracts.py` (mặc định chạy thử; `--commit` mới
  ghi). **Không xoá, không sửa dữ liệu cũ**: hợp đồng tồn kho cũ và từng dòng tiêu thụ đã khai được
  sao sang cấu trúc mới, bản gốc giữ nguyên và được đánh dấu để **không bị đếm hai lần**. Ngày nào có
  dòng thiếu chủng loại/số lượng thì **bỏ qua cả ngày** và in ra để rà tay — không suy diễn số liệu.

### Changed
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
