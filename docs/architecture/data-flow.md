# Luồng Dữ liệu Tổng thể

> Từ thu thập → xử lý → dự báo → hiển thị/cảnh báo → truy vấn.

## Sơ đồ
```mermaid
flowchart LR
    subgraph SRC[Nguồn dữ liệu]
      EX[4 sàn quốc tế<br/>TOCOM·SICOM·SHFE·AFET]
      MAC[Vĩ mô<br/>dầu·tỷ giá·PMI]
      INT[Nội bộ VRG<br/>BCTM·Physical·PDF·email]
    end

    EX & MAC --> CR[services/crawlers]
    INT --> ING[services/rag · ingest/OCR]

    CR --> ETL[pipelines · ETL<br/>làm sạch·chuẩn hóa]
    ETL --> TS[(TimescaleDB)]
    ING --> VEC[(pgvector)]

    TS --> FC[services/forecasting<br/>Prophet·XGBoost·LSTM<br/>Bull/Base/Bear]
    VEC --> RAG[services/rag · retrieve+citation]

    FC --> API[apps/api · FastAPI]
    RAG --> API
    TS --> API

    API --> WEB[apps/web<br/>Dashboard·Forecast·Command Center]
    API --> NOTI[services/notifications<br/>Email·Zalo·Telegram]
    WEB --> USER[Lãnh đạo & Chuyên viên VRG]
    NOTI --> USER
```

## Diễn giải
1. **Thu thập**: crawler 4 sàn + vĩ mô; tri thức nội bộ qua OCR/ingest.
2. **Chuẩn hóa**: ETL pipeline → TimescaleDB (số) và pgvector (embedding).
3. **Suy luận**: forecasting sinh dự báo + kịch bản; RAG truy xuất kèm citation.
4. **Phục vụ**: FastAPI gộp dữ liệu → Web (dashboard/chat) + Notifications (cảnh báo).
5. **Báo cáo tự động**: 07:30 (dự báo mở cửa) và 17:00 (thực tế vs dự báo).
