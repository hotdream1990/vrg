# Báo cáo tuần v2 — cập nhật theo "Logic viết Bản tin tuần 16.7" + mẫu thực tế tuần 35–36

Tài liệu nguồn (gitignored, mật): `docs/bieu-mau-bo-sung/huong-dan-bao-cao-tuan/`
- `Logic viết Bản tin tuần 16.7.docx` (logic MỚI) · bản markdown: scratchpad `logic-new.md`
- `BÁO CÁO PHÂN TÍCH THỊ TRƯỜNG CAO SU TUẦN 35 & 36-2026 ....docx` (mẫu thực tế MỚI NHẤT)
- `ANRPC Biweekly Report- August issue 1 2026.pdf` (tài liệu đính kèm mẫu)
Snapshot v1: `snapshot-v1/` + tag `snapshot/weekly-report-v1-20260913`.

## Mục tiêu v2
1. **Kỳ gộp 1–3 tuần** (mẫu 35–36): bảng nhiều cột tuần + +/- từng cặp; nhãn/tiêu đề theo kỳ.
2. **Ghi chú tự động dưới bảng** "sàn X không có giá ngày …" (từ dữ liệu, giá 0 = No Trading).
3. **Cao/thấp theo kỳ kèm giá nội tệ** (JPY/kg, CNY/tấn, US cent/kg) + tuần xảy ra.
4. **Danh mục nguồn tham khảo cấu hình được** (bảng `weekly_source`, seed theo mục I.SOURCE của logic).
5. **Tài liệu đính kèm** mỗi báo cáo (PDF/DOCX, vd ANRPC) → trích chữ → AI tóm tắt số liệu chính → AI dùng khi viết.
6. **Chỉ số tài chính tự lấy**: DXY, WTI, Brent (CNBC chart API, dự phòng Yahoo — Investing.com chặn bot 403; Yahoo trả 429 cho IP prod; giữ link Investing để đối chiếu) + tỷ giá hệ thống USD/JPY·CNY·MYR·THB.
7. **Tin vietnambiz ĐÚNG KỲ** (mọi bài 'Giá cao su hôm nay' trong kỳ, không chỉ 1 bài mới nhất).
8. **AI theo logic mới**: khung IV mới, logic tương quan từng sàn, V theo kịch bản, tránh từ tuyệt đối, kiểm tra số AI viết có trong dữ liệu.
9. PDF + web: bảng III MỌI kỳ (kể cả 1 tuần) bám mẫu 35–36 — cột tuần + "+/- (T37/T36)" có dấu, không cột % (chốt 13/09).

## Hợp đồng dùng chung (KHÔNG tự đổi — cần đổi thì báo agent chính)
Module nền đã có: `apps/api/app/services/weekly_period.py` → `period(week_key, span)` (xem docstring + chạy thử).

### A. `WeeklyReport` (GET /api/weekly-reports/{week_key}, PUT trả lại cùng shape)
Giữ các field v1 (week_key, week_no, year, date_range, prev_week_no, prev_year, next_week_no, next_year,
prev_col_label, curr_col_label, exchange_rows, physical_rows, latex_prev, latex_curr, latex_change, narrative) và THÊM:
```
span_weeks: int                      # 1..3
weeks: list[WeekCol]                 # period()["weeks"]: {week_no, year, mon, fri, label, short, range}; [0]=tuần mốc
last_week_no, last_year: int
title_label, span_label, prev_label, movement_label, next_label, list_label: str
exchange_rows/physical_rows[i] thêm: values: list[float|None] (len = len(weeks)),
                                     changes: list[float|None] (len-1, r1), changes_pct: list[float|None] (len-1, r2)
                                     (prev/curr/change_abs/change_pct = cặp CUỐI, giữ tương thích)
exchange_gaps: list[str]             # auto, vd "Tuần 24/8 - 28/8: sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 25/8."
physical_gaps: list[str]             # auto, vd "Tuần 31/8 - 4/9: giá giao ngay STR20 không có giá ngày 2/9."
range_stats: list[RangeStat]         # sàn quốc tế, cao/thấp CẢ KỲ (các tuần trong kỳ, không gồm tuần mốc)
physical_range_stats: list[RangeStat]
  RangeStat = {exchange: str|None, grade, high, high_date 'dd/mm', high_week_no, high_native: float|None,
               low, low_date, low_week_no, low_native, native_unit: 'JPY/kg'|'CNY/tấn'|'US cent/kg'|None}
fx_rows: list[{pair, values: list[float|None], changes: list[float|None], changes_pct}]   # USD/JPY, USD/CNY, USD/MYR, USD/THB — TB tuần
latex_bands: list[str|None]          # len(weeks) — override nếu có, else auto
latex_changes: list[str|None]        # len(weeks)-1
```
### Narrative (payload jsonb) — thêm, tất cả optional
```
span_weeks: int = 1
report_note: list[str]               # "Ghi chú:" dưới masthead (vd lý do gộp tuần)
exchange_table_notes: list[str]      # ghi chú tay thêm dưới bảng III.1 (ngoài gaps auto)
physical_table_notes: list[str]      # vd "Giá physical tuần này tham khảo theo ANRPC."
latex_override: list[str|None]|None  # len(weeks); None/"" = dùng auto (KHÔNG lưu seed)
latex_change_override: list[str|None]|None
macro[].title                        # SỬA ĐƯỢC; mặc định v2 = 4 nhóm bên dưới
(giữ latex_prev/latex_curr/latex_change cũ để đọc báo cáo đã lưu: span=1 → map sang override)
```
Tiêu đề IV mặc định (chốt 13/09 — thứ tự + tiêu đề theo báo cáo thật 35–36; báo cáo đã lưu giữ tiêu đề riêng):
1. `1. Thị trường Năng lượng, Địa chính trị & Giá Cao su tổng hợp (Butadiene):` · 2. `2. Cung – Cầu:`
3. `3. Tỷ giá và Tài chính Nhật Bản:` · 4. `4. Dữ liệu Kinh tế Trung Quốc & Các yếu tố khác:`
Hướng dẫn AI + mã nguồn IV.n nhận chủ đề theo từ khoá tiêu đề trước (năng lượng/dầu/butadien → cung/cầu/anrpc
→ tỷ giá/yên/dxy/tài chính → trung quốc/khác), không khớp mới theo vị trí.

### Bullet/định dạng chữ trong narrative (PDF + web hiểu giống nhau)
Dòng mở đầu `>` = gạch cấp 2, `>>` = cấp 3, `-` ở Phần V = gạch đầu dòng. Trong dòng: `**đậm**`, `*nghiêng*`. PDF PHẢI escape HTML trước khi áp định dạng.

### AI result
`AiAssistResult` thêm `warnings: list[str]` (số không đối chiếu được) + `absolute_words: list[str]`.
`AiAssistAllResult` thêm `warnings: dict[str, list[str]]` (key = field narrative hoặc `macro:<i>`) + `absolute_words: dict[str, list[str]]`.

### B. Nguồn tham khảo — `/api/weekly-sources`
Bảng `weekly_source(id serial, category, name, role, url, sections jsonb, guide, mode, feed_symbol, enabled, sort_order, updated_by, updated_at)`.
- category ∈ futures|physical|financial|news|macro · mode ∈ internal|market_feed|vietnambiz|attachment|manual
- sections ⊂ I, II, III.1, III.2, III.3, IV.1, IV.2, IV.3, IV.4, V, VI
- `GET ""` · `GET /meta` ({categories,modes,sections} có label VN) · `POST ""` · `PUT /{id}` · `DELETE /{id}` · `POST /reset-defaults`
- WeeklySource JSON = đủ cột (sections = list[str], updated_at iso).
Service Python: `weekly_source_repo.list_sources(enabled_only=False)`, `sources_for_section(key)`.

### B. Đính kèm — `/api/weekly-reports/{week_key}/attachments`
Bảng `weekly_report_attachment(id serial, week_key, file, filename, size, kind 'anrpc'|'other', pages, text_content, summary, uploaded_by, created_at, updated_at)`; file ở `data_dir()/weekly-reports/attachments/` (nằm trong volume `weekly-out` sẵn có).
- `GET ""` → list[{id, week_key, filename, size, kind, pages, text_chars, summary, uploaded_by, created_at}]
- `POST ""` multipart `file` (+ form `kind`) · `PATCH /{id}` {kind?, summary?} · `DELETE /{id}`
- `GET /{id}/file` (tải) · `GET /{id}/text` → {text} · `POST /{id}/summarize` → {summary} (gọi `weekly_ai.summarize_attachment(week_key, id)` import lười)
Service: `weekly_attachment_service.context_documents(week_key, max_chars=24000) -> list[{id, filename, kind, used:'summary'|'text', content}]`, `delete_all(week_key) -> int`.

### B. Đầu vào thị trường — `/api/weekly-reports/{week_key}/indicators` và `/news`
- `weekly_market_feed.weekly_indicators(weeks) -> list[{source_id, name, role, url, symbol, values, changes, changes_pct, last_closes, high:{value,date}|None, low:{...}|None, error}]` (TB tuần giá đóng cửa ngày, r2; cache 30')
- `weekly_news.fetch_period_articles(index_url, date_from: date, date_to: date, max_articles=12, max_chars_each=1800) -> list[{url, title, published 'YYYY-MM-DD', body}]` (cache theo URL)
- GET `/indicators?span=` → {indicators: [...]} · GET `/news` → {articles: [{url,title,published}]} (span đọc từ payload đã lưu nếu không truyền)

### Quyền
Đọc: gác chung `require_cap("bulletin_weekly")` ở main. Ghi: `Depends(require_cap_edit("bulletin_weekly"))`. Ghi log `audit_repo.log("bulletin_weekly", ...)`.

### D. Models PDF (`services/weekly_report/weekly/models.py`) — A map sang, D render
```python
@dataclass class WeekCol: week_no: int; year: int; label: str            # 'Tuần 35 (24/8 - 28/8)'
@dataclass class TableRow: exchange: str|None; grade: str; values: list[float|None]
    # property changes -> list[float|None] (r1), changes_pct -> list[float|None] (r2)
@dataclass class MacroSection: title: str; bullets: list[str]
@dataclass class WeeklyReportData:
    title_label: str; date_range: str; span_label: str
    prev_label: str; movement_label: str; next_label: str
    weeks: list[WeekCol]                          # [tuần mốc, tuần 1..n]
    report_note: list[str]
    summary_prev: list[str]; movement: list[str]
    exchange_rows: list[TableRow]; exchange_gaps: list[str]; exchange_table_notes: list[str]; exchange_notes: list[str]
    physical_rows: list[TableRow]; physical_gaps: list[str]; physical_table_notes: list[str]; physical_notes: list[str]
    latex_bands: list[str|None]; latex_changes: list[str|None]; latex_notes: list[str]
    macro: list[MacroSection]; forecast: list[str]; conclusion: list[str]
```
Tên file PDF: `Bao-cao-tuan-{span_label thay '/' bằng '-'}.pdf` (vd `Bao-cao-tuan-35-36-2026.pdf`).

## Phân nhánh (file ownership — KHÔNG sửa file của nhánh khác)
| Nhánh | File |
|---|---|
| A core | `services/weekly_report_service.py` (tách thêm `weekly_report_tables.py`), `schemas/weekly_report.py`, `routers/weekly_reports.py`, test `tests/test_weekly_report_tables.py` |
| B inputs | `core/db.py` (chỉ thêm 2 bảng), `services/weekly_source_repo.py`, `services/weekly_source_defaults.py`, `services/weekly_attachment_service.py`, `services/weekly_market_feed.py`, `services/weekly_news.py`, `schemas/weekly_source.py`, `routers/weekly_sources.py`, `routers/weekly_report_inputs.py`, `main.py` (đăng ký router), tests `tests/test_weekly_sources.py`, `tests/test_weekly_inputs.py` |
| C AI | `services/weekly_ai.py`, `services/weekly_ai_prompts.py`, `services/weekly_ai_context.py`, `services/weekly_number_check.py`, test `tests/test_weekly_number_check.py` |
| D PDF | `services/weekly_report/weekly/*.py` |
| E Web | `apps/web/src/features/command-center/pages/WeeklyReportPage.tsx`, `pages/components/Weekly*.tsx` (mới/sửa), `lib/weekly-report-client.ts`, `lib/weekly-sources-client.ts` (mới), cuối `features/bulletin/bulletin.css` (chỉ khối `.wk-*`) |
