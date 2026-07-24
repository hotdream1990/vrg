# Changelog Dự án

Ghi nhận thay đổi đáng kể. Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/).

## [Unreleased]
### Added
- **Nhật ký hoạt động (audit log)** — ghi vết MỌI thay đổi số liệu: ai · lúc nào · bản ghi nào ·
  giá trị trước → sau. Bảng `audit_log` độc lập (không ghi đè), gắn ở tầng repo nên bao phủ mọi lối
  vào: màn chuyên viên, màn đơn vị thành viên, nhập từ file Excel, link công khai, job tự chạy.
  API `GET /api/audit` (chỉ đọc) + màn **Quản trị → Nhật ký hoạt động**, quyền mới `audit`.
  Không lưu mật khẩu/secret; xoá bản ghi vẫn giữ nguyên giá trị cũ trong nhật ký.
- Khởi tạo cấu trúc repo (scaffold) cho Đề án A — AI Dự báo Giá Cao su.
- `AGENTS.md` (chuẩn chung Claude + Antigravity) + `CLAUDE.md` import.
- Khung `knowledge/` (Markdown + YAML frontmatter) — tri thức dùng chung cho agent & RAG.
- Tài liệu kiến trúc (`docs/architecture/`) + quản trị dự án (`docs/project/`).
- `.env.example`, cập nhật `.gitignore` (bảo vệ dữ liệu mật VRG).
- **Skeleton chạy được** (verified): `apps/api` (FastAPI/uv — pytest 2 passed, ruff clean, HTTP `/health` OK), `apps/web` (React+TS+Vite/pnpm — `pnpm build` OK), `infra/docker` (TimescaleDB+pgvector — `compose config` hợp lệ).
- **Knowledge nghiệp vụ** (`knowledge/business-process/`): quy trình báo cáo tuần/năm, cấu trúc giá Physical, báo cáo ký kết HĐ, bản tin phân tích tuần — trích xuất từ biểu mẫu thật.
- **Plan Sprint 1** (`plans/260615-sprint-01-dashboard-mvp/`): Dashboard MVP + crawler 4 sàn.

### Notes
- Skeleton verified chạy được; chưa cài heavy ML libs (Prophet/XGBoost/LSTM) — bổ sung ở Sprint 2.
- pnpm 11 cần `apps/web/pnpm-workspace.yaml` → `allowBuilds: esbuild: true` để build tự động.
- Dữ liệu mật (`docs/data/`, `docs/bieu-mau/`, `data/raw/`) giữ local, không commit.
