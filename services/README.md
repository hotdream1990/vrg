# services/ — Dịch vụ AI & Dữ liệu (Python)

Các dịch vụ độc lập, được `apps/api` và `pipelines/` gọi tới. Mỗi service là một module Python tách bạch.

| Service | Vai trò | Công nghệ |
|---|---|---|
| `crawlers/` | Thu thập giá 4 sàn (TOCOM/SICOM/SHFE/AFET) + vĩ mô | httpx, parsers |
| `forecasting/` | Dự báo chuỗi thời gian + Scenario Bull/Base/Bear + tự hiệu chỉnh | Prophet, XGBoost, LightGBM, LSTM |
| `rag/` | Ingest/OCR, embedding, retrieve + citation | pgvector, LLM API |
| `notifications/` | Cảnh báo đa kênh + báo cáo 07:30/17:00 | SMTP, Zalo OA, Telegram |

## Quy ước
- Spec crawler bám theo [knowledge/data-sources/lay-gia-cac-san.md](../knowledge/data-sources/lay-gia-cac-san.md).
- **KISS cho PoC**: có thể bắt đầu gộp các service thành module trong `apps/api`, tách riêng khi cần scale.
