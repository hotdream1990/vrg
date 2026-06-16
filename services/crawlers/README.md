# services/crawlers — Crawler chỉ số sàn

Thu thập giá tham chiếu cao su + tỷ giá, chuẩn hóa thành `PriceRecord`. Bám spec
[lay-gia-cac-san.md](../../knowledge/data-sources/lay-gia-cac-san.md).

## Chạy
```bash
cd services/crawlers
uv sync
uv run python -m crawlers.run_crawl --source all
uv run python -m crawlers.run_crawl --source anrpc,fx --out ../../data/raw/crawl.json
uv run pytest          # test offline (selection + parser ANRPC, không gọi mạng)
```

## Kiến trúc (phase-02)
- `base/` — `models` (PriceRecord, ContractQuote, CrawlResult), `fetcher` (retry/backoff/UA từ env), `selection` (chọn kỳ hạn theo **max volume/trading_value**, không hardcode tháng).
- `exchanges/` — anrpc · sgx_sicom · shfe · tocom · lgm.
- `macro/` — fx.
- `run_crawl.py` — CLI, **cô lập lỗi** từng nguồn (1 nguồn hỏng không chặn nguồn khác).

## Trạng thái nguồn
| Nguồn | Grade | Trạng thái |
|---|---|---|
| **ANRPC** | SMR20, STR20, SIR20, RSS3 (physical US$/kg) | ✅ chạy |
| **FX** (open.er-api) | USD/VND, CNY, THB, JPY, MYR | ✅ chạy |
| **SHFE** (daily kx) | RU 天然橡胶 — **settlement**, CNY/tonne | ✅ chạy *(SETTLEMENTPRICE kỳ hạn **max Volume** — đúng spec)* |
| **TOCOM/OSE** | RSS3 + TSR20 — settlement, JPY/kg | ✅ chạy *(OSE Daily Report PDF · chọn kỳ hạn **max Trading Value**)* |
| **LGM** | SMR CV/L/5/GP/10/20 + Latex — **US cents/kg** | ✅ chạy *(API currentprice; Latex tự quy đổi Sen/kg→US cents/kg theo tỷ giá nội tại)* |
| **SGX/SICOM** | TSR20 (TF), RSS3 (RT) | ❌ **CHƯA CÓ DATA** — API trả rỗng / `SGX_4015/4020`; cần request capture từ browser hoặc licensed SICOM feed |

SHFE qua **SHFE daily kx** (`/data/tradedata/future/dailydata/kx{date}.dat`) → SETTLEMENTPRICE của kỳ hạn **max Volume**. Cao su (RSS3/TSR20) qua **OSE Daily Report ZIP** → `cdf_dyr` PDF (pdfplumber), chọn kỳ hạn có **Trading Value lớn nhất**. LGM qua **API currentprice** (httpx + token công khai). **SGX hiện chưa có data** (xem mục dưới).

## Câu hỏi mở (cần chốt với VRG / kỹ thuật)
- **SGX (SICOM) — CHƯA CÓ DATA**: API còn sống nhưng `/history/symbol/TF` trả rỗng; `params`→`SGX_4015`, `prices`→`SGX_4020`. Trang dùng `cc=TF&category=rubber`. Cần capture request thật từ browser (devtools sgx.com) hoặc licensed feed. Tạm thời TSR20/RSS3 có thể tham chiếu ANRPC/TOCOM.
- **TOCOM/OSE**: ✅ đã chọn max Trading Value từ PDF. Còn lại: lịch sử 2 năm (ZIP chỉ ~4 tháng) → dùng Excel của VRG / J-QUANTS.
- **LGM**: ✅ xong — API `webv2api/api/rubberprice/currentprice` + Basic token công khai nhúng trong frontend.
- **Vĩ mô còn thiếu**: oil (WTI/Brent), USD Index, PMI TQ — chọn nguồn.
