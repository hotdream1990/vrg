# Báo cáo Công tác — Quét Giá Đa sàn (brainstorm slide)

> **Mục đích:** slide báo cáo công tác đã làm cho hạng mục *Quét giá đa sàn* (PoC VRG).
> **Style nguồn:** bám `docs/data/Phien lam viec DRG - AI Du bao Gia Cao su-print.html`
> (deck 1920×1080, theme xanh glassmorphism nền sáng + divider tối, eyebrow/s-title/panel/feat/table/chip).
> **Ngôn ngữ:** tiếng Việt. **Trạng thái:** brainstorm ý chính — *chưa* dựng HTML.

---

## A. Đề xuất luồng slide (13–14 trang)

| # | Slide | Loại | Nội dung lõi |
|---|---|---|---|
| 00 | **Bìa** | cover | "Báo cáo Công tác — Quét Giá Đa sàn" · logo Thái Hưng + Bizino × VRG · tháng 06/2026 |
| 01 | **Nội dung báo cáo** | agenda (chip 1–5) | 5 nhóm ý: Bối cảnh → Khung base → Quét đa sàn → Giao diện → Next steps |
| — | **PHẦN 01 · Bối cảnh & Đầu vào** | divider | |
| 02 | Tình hình khi nhận project | content (feat) | Quy trình **thủ công**, phụ thuộc kinh nghiệm chuyên viên, lấy giá từng web mỗi ngày (T‑1) |
| 03 | Biểu mẫu đầu vào được cung cấp | table | 4 chuyên viên: Tâm · Hạnh · Phụng · Triều — ai đưa gì |
| — | **PHẦN 02 · Khung base hệ thống** | divider | |
| 04 | Kiến trúc & stack | panel ×4 / feat | Monorepo, FastAPI + React/TS + TimescaleDB/pgvector, cổng riêng 8390/5390/5433 |
| 05 | Hạ tầng dữ liệu + API gateway | panel | TimescaleDB (`fact_price` hypertable + `meta_crawl_run`), API health/scan/latest/history |
| — | **PHẦN 03 · Quét đa sàn (trọng tâm)** | divider | |
| 06 | Từ quy trình chuyên viên → code | flow 3 bước | Tâm (.docx) → spec `lay-gia-cac-san.md` → `services/crawlers` |
| 07 | Kiến trúc crawler | feat | base (chuẩn hóa `PriceRecord`, selection theo volume) · cô lập lỗi từng nguồn |
| 08 | **Lấy gì — của sàn nào — như thế nào** | table lớn | ANRPC · SHFE · TOCOM/OSE · LGM · FX · SGX (✅/❌) |
| 09 | Tích hợp API + ghi DB + kiểm thử | feat | `POST /scan` → crawler → upsert `fact_price` → `/latest`,`/history`; pytest offline |
| — | **PHẦN 04 · Giao diện quét đa sàn** | divider | *(đang làm ở luồng khác — bổ sung sau)* |
| 10 | Màn hình "Quét đa sàn" | shot + feat | **[PLACEHOLDER ảnh + nội dung — chèn sau]** |
| — | **PHẦN 05 · Next steps** | divider | |
| 11 | Nghiên cứu & triển khai tiếp | table/feat | Nguồn dang dở + số hóa biểu mẫu còn lại + ETL/RAG |
| 12 | Tổng kết | closing | Đã có: 5/6 nguồn chạy + persistence + UI; kế tiếp: hoàn thiện dữ liệu nghiệp vụ |

---

## B. Nội dung chi tiết từng nhóm (nguyên liệu cho slide)

### 1️⃣ Tình hình khi nhận project + biểu mẫu đầu vào (`docs/bieu-mau`)

**Hiện trạng nghiệp vụ (slide 02):**
- Công tác dự báo/báo cáo giá đang **làm thủ công**, phụ thuộc kinh nghiệm cá nhân.
- Mỗi ngày chuyên viên **vào từng website** sàn, đọc bảng/PDF, **chọn kỳ hạn đúng** (theo kinh nghiệm), copy giá ra Excel → ra bản tin ngày.
- Quy ước: lấy giá của **ngày trước hiện tại 1 ngày (T‑1)**.
- Nhiều định dạng rời rạc: `.docx`, `.xlsx`, `.pdf`, `.pptx` → khó tổng hợp, khó tự động hóa.

**Biểu mẫu 4 chuyên viên cung cấp (slide 03):**

| Chuyên viên | Biểu mẫu / dữ liệu | Phục vụ |
|---|---|---|
| **Tâm** ⭐ | "Các Web và hướng dẫn lấy giá…" (.docx) · "Mẫu file lấy giá các sàn, giá mủ nước" (.xlsx) · Bản tin ngày 09‑06 (.pdf/.pptx/.docx) · Giá Physical 2025/2026 | **Nguồn lõi cho quét đa sàn** + bản tin giá |
| **Hạnh** | Báo cáo Tuần — DATA ĐẦU VÀO / ĐẦU RA (các Cty gửi về, tuần 20) | Sản lượng/giá tuần theo công ty |
| **Phụng** | Báo cáo ký kết hợp đồng theo Quý (Input/Output) · Báo cáo phân tích thị trường cao su hàng tuần (.docx/.pdf) · BM07a | Giá bán thực tế VRG · tri thức phân tích (RAG) |
| **Triều** | Mẫu Báo cáo Tiêu thụ năm 2025 (.xls/.xlsx) · CV 3476/CSVN‑TTKD | Sản lượng tiêu thụ toàn Tập đoàn |

> Điểm nhấn: **Tâm** là người cung cấp quy trình lấy giá các sàn → đây là đầu vào trực tiếp cho hạng mục quét đa sàn.

---

### 2️⃣ Khung base của hệ thống

**Kiến trúc (slide 04):**
- **Monorepo** chuẩn: `apps/{api,web}` · `services/{crawlers,forecasting,rag,notifications}` · `packages/{shared-py,shared-ts}` · `pipelines/` · `knowledge/` · `infra/` · `data/`.
- **Stack:** FastAPI (Python) · React + TypeScript (Vite) · **TimescaleDB + pgvector**.
- **Cổng riêng VRG** (tránh đụng dự án khác): API `8390` · Web `5390` · DB `5433`.
- **1 lệnh chạy cả API + Web:** `./scripts/dev.sh` (hoặc `/dev`).
- **Nguyên tắc:** KISS · YAGNI · DRY · file < 200 dòng · **cô lập lỗi** từng nguồn.

**Hạ tầng dữ liệu + API (slide 05):**
- Docker compose: TimescaleDB+pgvector; init `infra/db/init/01-extensions.sql` + `02-schema.sql`.
- 2 bảng (KISS, chưa cần star-schema):
  - `fact_price` — **hypertable** theo `as_of`; PK `(as_of, source, grade, contract, price_type)`; index `(source, grade, as_of DESC)` để lấy giá mới nhất.
  - `meta_crawl_run` — mỗi lần "Quét giá" = 1 run (start/finish, rows, status, error).
- Schema **idempotent**: app tự `ensure_schema` qua `app/core/db.py` (DRY với SQL init).
- **API gateway** (`apps/api`): `GET /health` · `GET /health/db` · `POST /api/prices/scan` · `GET /api/prices/latest` · `GET /api/prices/history`.
- **Knowledge base dual‑compat** (Markdown + YAML) — Claude + Antigravity + RAG cùng đọc.

---

### 3️⃣ Quét đa sàn — TRỌNG TÂM (triển khai từ nội dung của ai → lấy gì, sàn nào, thế nào)

**Nguồn gốc nội dung (slide 06) — "từ ai":**
> Số hóa **quy trình thủ công của chuyên viên Tâm** (file `Các Web và hướng dẫn lấy giá… .docx`)
> → trích thành **spec** `knowledge/data-sources/lay-gia-cac-san.md`
> → hiện thực thành code `services/crawlers/` (bám đúng spec).

3 bước: **Tri thức chuyên viên → Spec chuẩn hóa (Markdown) → Crawler tự động.**

**Kiến trúc crawler (slide 07):**
- `base/` — `models` (`PriceRecord` chuẩn hóa: source/grade/price/currency/unit/price_type/as_of/contract/extra) · `fetcher` (retry/backoff/UA, header riêng) · `selection` (**tham số hóa kinh nghiệm chuyên viên**: chọn kỳ hạn theo *max volume* / *max trading value* — **không hardcode tháng**).
- `exchanges/` (anrpc·shfe·tocom·lgm·sgx_sicom) + `macro/` (fx).
- `run_crawl.py` — CLI gom mọi nguồn, **1 nguồn hỏng không chặn nguồn khác**, xuất JSON.

**Bảng lõi (slide 08) — lấy gì / của sàn nào / như thế nào:**

| Sàn | Mặt hàng | Lấy gì | Cách lấy (kỹ thuật) | Đơn vị | TT |
|---|---|---|---|---|---|
| **ANRPC** | SMR20, STR20, SIR20, RSS3 | Giá **physical** | Parse bảng HTML `anrpc.org/anrpc-daily-price`, tự chọn **cột ngày mới nhất** | US$/kg | ✅ |
| **SHFE** (Thượng Hải) | Natural Rubber (RU 天然橡胶) | **Settlement** | JSON chính thức `kx{date}.dat`, chọn kỳ hạn **MAX Volume** → SETTLEMENTPRICE, tự lùi ngày | CNY/tấn | ✅ |
| **TOCOM/OSE** (Nhật) | RSS3, TSR20 | **Settlement** | JPX OSE Daily Report **ZIP → giải nén `cdf_dyr` PDF** (pdfplumber), chọn kỳ hạn **MAX Trading Value** | JPY/kg | ✅ |
| **LGM** (Malaysia) | SMR CV/L/5/GP/10/20, Latex | Giá **physical FOB** | API `currentprice` (token Basic công khai); **Latex tự quy đổi** Sen/kg → US cents/kg theo tỷ giá MYR/USD nội tại cùng phiên | US cents/kg | ✅ |
| **FX** (vĩ mô) | USD/VND·CNY·THB·JPY·MYR | Tỷ giá | `open.er-api.com` (latest) — theo dõi USD/VNĐ + quy đổi giá physical | per USD | ✅ |
| **SGX/SICOM** | TSR20 (TF), RSS3 (RT) | Settlement | API còn sống nhưng đổi format → trả rỗng / `SGX_4015/4020`; **logic parse đã sẵn sàng** | US cents/kg | ❌ open |

> Mỗi bản ghi đều **chuẩn hóa về `PriceRecord`** → đồng nhất cho ETL/serving (không phụ thuộc format gốc của từng sàn).

**Tích hợp API + Persistence + kiểm thử (slide 09):**
- `POST /api/prices/scan` → chạy crawler (subprocess, timeout 180s) → gom records → **upsert `fact_price`** (`ON CONFLICT`) + ghi `meta_crawl_run`.
- **Degrade gracefully**: DB down vẫn trả dữ liệu quét (best‑effort persist).
- Đọc cho dashboard: `/latest` (kèm `ingested_at`), `/history` (chuỗi cho biểu đồ).
- **Kiểm thử offline** (`pytest`, không gọi mạng): selection + parser ANRPC/SHFE/TOCOM/LGM.

---

### 4️⃣ Giao diện quét đa sàn — *(đang triển khai ở luồng khác)*

> **[PLACEHOLDER — bổ sung sau khi anh hoàn thiện UI]**
- Route `/quet-da-san` (Command Center, dark theme).
- Mở trang **tự nạp giá đã lưu** từ DB (`GET /latest`) — không cần bấm mỗi lần; hiển thị "cập nhật lúc" theo `ingested_at`.
- Nút **"Quét giá ngay"** → `POST /scan` → refresh.
- Bảng theo sàn + **trạng thái nguồn** (✓ ok · · empty · ⚠ blocked · ✗ error); **cờ nguồn chưa có data**.
- *(Chèn screenshot khi sẵn sàng — dùng khung `.shot` như deck mẫu)*

---

### 5️⃣ Next steps — nghiên cứu & triển khai tiếp từ biểu mẫu

**A. Hoàn tất các nguồn giá còn dang dở:**
- **SGX/SICOM**: capture request thật từ browser (devtools) hoặc licensed SICOM feed.
- **TOCOM lịch sử 2 năm**: ZIP chỉ ~4 tháng → bổ sung từ Excel VRG / J‑QUANTS.
- **Vĩ mô còn thiếu**: dầu (WTI/Brent), USD Index, PMI Trung Quốc.

**B. Số hóa biểu mẫu nghiệp vụ còn lại (mỗi cái mở 1 luồng dữ liệu):**
- **Tâm** → "Mẫu file lấy giá các sàn, giá mủ nước" (.xlsx): **giá mủ nước nội địa**; "Giá Physical" 2025/2026 → nạp **lịch sử**.
- **Phụng** → Hợp đồng theo Quý: **giá bán thực tế VRG** → tính **Premium/Discount** vs thị trường; Báo cáo phân tích tuần → nạp **RAG**.
- **Hạnh** → Báo cáo Tuần các Cty → chuẩn hóa data đầu vào/đầu ra.
- **Triều** → Báo cáo Tiêu thụ năm → **sản lượng/tiêu thụ** toàn Tập đoàn.

**C. Hoàn thiện khung & pipeline:**
- Phase 01 còn lại: dimension tables + Alembic + shared `db_models`.
- Phase 03: **ETL nạp lịch sử** + Premium/Discount.
- Scheduler (Airflow/Prefect) chạy **T‑1 tự động hằng ngày**.
- Bơm bản tin ngày (Tâm) + phân tích tuần (Phụng) vào **pgvector** cho Command Center hỏi đáp tiếng Việt có trích dẫn.

---

## C. Cần anh chốt trước khi dựng HTML
1. **Đối tượng & giọng:** báo cáo nội bộ trình Lãnh đạo VRG, hay báo cáo nội bộ đội Bizino? (ảnh hưởng độ sâu kỹ thuật ở Phần 03).
2. **Độ dài:** giữ ~13–14 slide như trên, hay gọn còn ~8–9 (gộp 04+05, 08+09)?
3. **Phần 04 (giao diện):** để 1 slide placeholder, hay tạm ẩn cho tới khi có screenshot?
4. **Số liệu thật:** có muốn nhúng 1 ảnh chụp output `run_crawl` / bảng `/latest` thật để minh chứng "chạy được" không?
