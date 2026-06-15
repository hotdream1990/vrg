# packages/ — Mã dùng chung

Thư viện nội bộ dùng chung giữa các app/service, tránh lặp (DRY).

| Package | Dùng cho |
|---|---|
| `shared-py/` | models, kết nối DB, util Python dùng chung (`apps/api`, `services/`) |
| `shared-ts/` | type & API contract dùng chung (`apps/web` ↔ `apps/api`) |

> Giữ tối giản — chỉ đưa lên đây những gì thực sự dùng ở ≥ 2 nơi (YAGNI).
