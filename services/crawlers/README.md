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
| SGX/SICOM | TSR20 (TF), RSS3 (RT) | ⚠️ API trả rỗng — cần mã contract/auth |
| SHFE | RU natural rubber | ⚠️ `.dat` 404 từ môi trường — cần ngày giao dịch thật/proxy |
| TOCOM/JPX | RSS3 | ⚠️ nguồn PDF (cdf_dyr) — cần parser PDF |
| LGM | SMR CV/SMR20/Latex | ⚠️ form chọn ngày — cần phiên/tham số |

Logic parse + chọn kỳ hạn của SGX/SHFE **đã viết sẵn**, sẽ chạy khi endpoint/ngày hợp lệ.

## Câu hỏi mở (cần chốt với VRG / kỹ thuật)
- **SGX**: mã contract/kỳ hạn đúng cho TF/RT (hoặc nguồn thay thế Investing/Barchart).
- **AFET**: đã sáp nhập TFEX — endpoint chính thức?
- **TOCOM**: chấp nhận parser PDF hay dùng nguồn JSON thay thế?
- **Vĩ mô còn thiếu**: oil (WTI/Brent), USD Index, PMI TQ — chọn nguồn (EIA/Stooq/API có key).
