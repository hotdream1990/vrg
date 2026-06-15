# Phase 02 — Crawler 4 sàn + Vĩ mô

## Context Links
- [plan.md](plan.md) · **Spec gốc**: [lay-gia-cac-san.md](../../knowledge/data-sources/lay-gia-cac-san.md)
- [san-pham-cao-su.md](../../knowledge/domain/san-pham-cao-su.md) · [data-flow.md](../../docs/architecture/data-flow.md) · [data-checklist.md](../../docs/project/data-checklist.md)

## Overview
- **Priority**: P1
- **Status**: ⚪ pending
- **Mô tả**: Viết crawler thu thập giá tham chiếu 4 sàn (TOCOM/SICOM-SGX/SHFE/AFET) + chỉ số vĩ mô (WTI/Brent, USD/VNĐ, USD Index, PMI TQ), **bám đúng quy trình thủ công** trong spec. Ghi raw + chuẩn cấu trúc để Phase 03 ETL load.

## Key Insights (BẮT BUỘC tuân thủ spec)
- Quy ước chung: lấy giá của **ngày trước hiện tại 01 ngày (T-1)**.
- **Chọn kỳ hạn = kinh nghiệm chuyên viên** → lấy kỳ hạn có **Trading Value / Volume LỚN NHẤT**, KHÔNG hardcode số tháng. Khoảng cách kỳ hạn đổi theo thời điểm (TOCOM ~5 tháng, SHFE ~3 tháng — chỉ là tham khảo).
- Mỗi sàn lấy field giá khác nhau: TOCOM=**Settlement**, SHFE=**Settle**, SGX=**SETTLE** (cột `RT`=RSS3, `TF`=TSR20), LGM=physical FOB (US Cents/Kg; Latex: `giá/tỷ giá×10`).
- Crawler chỉ **fetch + parse + emit bản ghi chuẩn**; KHÔNG tính Premium/Discount (đó là ETL/serving).
- Tách **fetcher** (HTTP/file) ↔ **parser** (đọc bảng) ↔ **selector kỳ hạn** (logic max volume) → mỗi sàn 1 module < 200 dòng, tái dùng base.

## Requirements
**Chức năng**
- 4 crawler sàn + nhóm vĩ mô, mỗi cái trả `list[PriceRecord]`/`MacroRecord` (Pydantic).
- Logic chọn kỳ hạn theo max(volume|trading_value) **tham số hóa** (`SelectionStrategy`), cấu hình hóa cột/endpoint per sàn.
- Ghi `meta_crawl_run` (start/finish/status/rows/error) mỗi lần chạy.
- Hỗ trợ tải **một ngày bất kỳ** (param `as_of_date`) → phục vụ Phase 03 nạp lịch sử (backfill).
- Nguồn tỷ giá phụ trợ (USD/CNY, USD/THB, BNM) cho quy đổi physical.

**Phi chức năng**
- Retry + backoff; timeout; `User-Agent` từ `.env` (`CRAWLER_USER_AGENT`).
- Idempotent: chạy lại cùng `as_of_date` không tạo bản ghi trùng (upsert key).
- Lỗi 1 sàn không làm gãy các sàn khác (cô lập).

## Architecture
```
services/crawlers/
  base/
    fetcher.py          HTTP/file fetch + retry/backoff/timeout
    models.py           PriceRecord, MacroRecord, ContractQuote (Pydantic)
    selection.py        SelectionStrategy: max_trading_value | max_volume (tham số hóa)
    registry.py         map source_code → crawler
  exchanges/
    tocom.py            JPX cdf_dyr → RSS3 (max Trading Value) → Settlement
    shfe.py             DailyData → Natural Rubber (max Volume) → Settle
    sgx_sicom.py        Historical Settlement → RT(RSS3)/TF(TSR20) → SETTLE
    afet.py             nguồn Thái/TFEX (xác nhận endpoint) → settle
    lgm.py              physical FOB: SMR CV/SMR20/Latex (quy đổi tỷ giá)
  macro/
    oil.py              WTI/Brent (API vĩ mô)
    fx.py               USD/VNĐ, USD/CNY, USD/THB, USD Index
    pmi_cn.py           PMI Trung Quốc
  fx_rates.py           helper tỷ giá (BNM, exchangerates.org.uk) cho quy đổi
  run_crawl.py          CLI: --source --as-of-date (gọi từ pipelines)
```
- `SelectionStrategy.pick(quotes)` → chọn `ContractQuote` có `trading_value`/`volume` max; trả kèm `expiry_month/year` thực tế (động).
- Output chuẩn hóa **trước** khi vào DB: đơn vị, tiền tệ, `source_ts`, `as_of_date`.

## Related Code Files
**Tạo**
- `services/crawlers/base/{fetcher,models,selection,registry}.py`
- `services/crawlers/exchanges/{tocom,shfe,sgx_sicom,afet,lgm}.py`
- `services/crawlers/macro/{oil,fx,pmi_cn}.py`
- `services/crawlers/{fx_rates,run_crawl}.py`
- `services/crawlers/pyproject.toml` (uv project: httpx, pydantic, selectolax/lxml, pandas, openpyxl)
- `services/crawlers/tests/` (fixture HTML/Excel mẫu cho parser — KHÔNG gọi mạng thật trong unit test)

**Sửa / Tái dùng**
- `packages/shared-py/db_models/` (Phase 01) — dùng cho upsert staging
- `.env.example` → đã có `CRAWLER_USER_AGENT`, `EXCHANGE_RATE_API_KEY` (chỉ điền `.env` thật)

## Implementation Steps
1. `base/models.py`: định nghĩa `ContractQuote(expiry_month, expiry_year, settle, volume, trading_value, currency)`, `PriceRecord`, `MacroRecord`.
2. `base/fetcher.py`: hàm `fetch_html/fetch_file/fetch_json` với retry/backoff/timeout + UA từ env.
3. `base/selection.py`: `SelectionStrategy` (enum + `pick()`), **tham số hóa** tiêu chí (trading_value vs volume) — không cố định số tháng.
4. `exchanges/tocom.py`: tải `cdf_dyr`, parse trang RSS3, áp `pick(max_trading_value)`, lấy **Settlement** → `PriceRecord`.
5. `exchanges/shfe.py`: tải DailyData theo ngày, lọc Natural Rubber, `pick(max_volume)`, lấy **Settle**.
6. `exchanges/sgx_sicom.py`: Historical Settlement, lọc `COM=RT` (RSS3) & `COM=TF` (TSR20), `COM_MM=tháng-1`, lấy **SETTLE** cùng dòng.
7. `exchanges/afet.py`: xác nhận nguồn (AFET đã sáp nhập TFEX) → implement endpoint chốt; nếu chưa có, để adapter rỗng + ghi câu hỏi mở.
8. `exchanges/lgm.py`: reference FOB SMR CV/SMR20 (US Cents/Kg); Latex `giá/tỷ giá×10` (dùng `fx_rates`).
9. `macro/*`: oil (WTI/Brent), fx (USD/VNĐ, USD Index, USD/CNY, USD/THB), pmi_cn.
10. `run_crawl.py`: CLI `--source all|<code> --as-of-date YYYY-MM-DD`; ghi `meta_crawl_run`; upsert staging.
11. Viết unit test parser từ fixture tĩnh (mỗi sàn 1 mẫu); test `SelectionStrategy.pick()` chọn đúng max.
12. Compile/lint: `uv run ruff check`, chạy `pytest` parser offline.

## Todo List
- [ ] `base/` (fetcher, models, selection tham số hóa, registry)
- [ ] 5 crawler sàn (tocom, shfe, sgx_sicom, afet, lgm) bám spec từng field giá
- [ ] 3 nhóm vĩ mô (oil, fx, pmi_cn) + helper tỷ giá
- [ ] `run_crawl.py` CLI hỗ trợ `--as-of-date` (backfill) + ghi meta
- [ ] Idempotent upsert (không trùng theo `(contract, as_of_date)`)
- [ ] Unit test parser bằng fixture tĩnh (offline) + test selection
- [ ] Compile/lint pass

## Success Criteria
- Chạy `run_crawl --source all --as-of-date <T-1>` → mỗi sàn trả ≥1 bản ghi đúng field giá spec.
- Kỳ hạn chọn ra khớp dòng có **volume/trading_value lớn nhất** (verify trên fixture).
- Chạy lại cùng ngày: không nhân bản bản ghi.
- `meta_crawl_run` ghi đủ status/rows; lỗi 1 sàn không chặn sàn khác.

## Risk Assessment
- **Trang sàn đổi layout / chặn bot / cần đăng nhập** → parser tách rời + selector cấu hình hóa; alert khi parse rỗng. Cân nhắc nguồn dự phòng (Investing/Barchart) cho vĩ mô.
- **AFET nguồn không rõ** (đã sáp nhập TFEX) → ghi câu hỏi mở; adapter pluggable để thay nguồn không sửa core.
- **PMI TQ phát hành theo tháng** (không daily) → lịch crawl riêng, không coi là chuỗi ngày.
- **Quy đổi tỷ giá sai đơn vị** (LGM Sen/Kg, Latex `/tỷ giá×10`) → test quy đổi với case trong spec.

## Security Considerations
- Tôn trọng ToS/robots từng site; rate-limit; UA định danh `bizino-vrg-bot`.
- Không log nội dung nhạy cảm; API key vĩ mô qua `.env` (`EXCHANGE_RATE_API_KEY`).
- Validate/parse phòng thủ (dữ liệu ngoài) trước khi ghi DB.

## Next Steps
- Bàn giao bản ghi chuẩn + staging cho **Phase 03** (ETL chuẩn hóa & load fact + backfill 2 năm).
- Chốt câu hỏi mở AFET + nguồn "giá sàn VRG" với VRG.
