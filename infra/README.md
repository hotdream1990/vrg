# infra/ — Hạ tầng & Triển khai

| Thư mục | Nội dung |
|---|---|
| `docker/` | `docker-compose` cho dev: api · web · DB · redis |
| `db/` | Script khởi tạo DB (TimescaleDB + pgvector), migration |

## Ghi chú
- **DB**: Postgres bật extension **TimescaleDB** (time-series) + **pgvector** (embedding).
- **Production**: Cloud Việt Nam (VNG/Viettel/VNPT) — data residency 100% tại VN.
- Bảo mật: TLS 1.3, AES-256, SSO Active Directory VRG (xem mục 7 trong AGENTS.md).

## Chạy DB (đã validate)
```bash
docker compose -f infra/docker/docker-compose.yml up db   # TimescaleDB + pgvector
docker compose -f infra/docker/docker-compose.yml config -q   # kiểm tra cú pháp
```
> `infra/db/init/01-extensions.sql` tự bật extension `timescaledb` + `vector` khi tạo DB lần đầu.
> Service `api` và `web` đã có Dockerfile; build khi cần triển khai đầy đủ.
