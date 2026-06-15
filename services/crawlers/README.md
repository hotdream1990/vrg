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
| **SHFE** (Sina) | RU 天然橡胶 — last, CNY/tonne | ✅ chạy *(giá last, không phải settlement chính thức)* |
| **TOCOM/JPX** | RSS3 + TSR20 — settlement, JPY/kg | ✅ chạy *(CSV settlement chính thức; headline = front month)* |
| SGX/SICOM | TSR20 (TF), RSS3 (RT) | ⚠️ Akamai chặn bot (Access Denied) cả headless — cần browser thật+proxy hoặc licensed |
| LGM | SMR CV/SMR20/Latex | ⚠️ form chọn ngày — cần Playwright fill form (chưa làm) |

SHFE qua **Sina** (last). TOCOM qua **JPX CSV** settlement (`rb_e{YYYYMMDD}.csv`, cp932) — tự khám phá URL bằng Playwright nếu pattern đổi (self-healing). SGX bị **Akamai** chặn.

## Câu hỏi mở (cần chốt với VRG / kỹ thuật)
- **SGX (SICOM)**: Akamai chặn → cần browser thật + residential proxy, hoặc licensed feed, hoặc dùng ANRPC làm proxy cho TSR20.
- **TOCOM**: chọn kỳ hạn theo max Trading Value cần file volume riêng của JPX (hiện headline = front month).
- **LGM**: implement Playwright fill form chọn ngày → SMR CV/SMR20/Latex.
- **Vĩ mô còn thiếu**: oil (WTI/Brent), USD Index, PMI TQ — chọn nguồn.
