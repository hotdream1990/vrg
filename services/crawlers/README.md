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
| **TOCOM/OSE** | RSS3 + TSR20 — settlement, JPY/kg | ✅ chạy *(OSE Daily Report PDF · chọn kỳ hạn **max Trading Value**)* |
| **LGM** | SMR CV/L/5/GP/10/20 (US cents/kg) + Latex (Sen/kg) | ✅ chạy *(API currentprice + Basic token công khai)* |
| SGX/SICOM | TSR20 (TF), RSS3 (RT) | ⚠️ Akamai chặn bot (Access Denied) cả headless — cần browser thật+proxy hoặc licensed |

SHFE qua **Sina** (last). Cao su (RSS3/TSR20) qua **OSE Daily Report ZIP** → `cdf_dyr` PDF (pdfplumber), chọn kỳ hạn có **Trading Value lớn nhất** (đúng hướng dẫn). LGM qua **API currentprice** (httpx + token công khai). SGX bị **Akamai** chặn.

## Câu hỏi mở (cần chốt với VRG / kỹ thuật)
- **SGX (SICOM)**: Akamai chặn → cần browser thật + residential proxy, hoặc licensed feed, hoặc dùng ANRPC làm proxy cho TSR20.
- **TOCOM/OSE**: ✅ đã chọn max Trading Value từ PDF. Còn lại: lịch sử 2 năm (ZIP chỉ ~4 tháng) → dùng Excel của VRG / J-QUANTS.
- **LGM**: ✅ xong — API `webv2api/api/rubberprice/currentprice` + Basic token công khai nhúng trong frontend.
- **Vĩ mô còn thiếu**: oil (WTI/Brent), USD Index, PMI TQ — chọn nguồn.
