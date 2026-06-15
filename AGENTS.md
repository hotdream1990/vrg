# AGENTS.md — AI Agent Dự báo Giá Cao su (VRG)

Hướng dẫn chuẩn cho **cả AI agent (Claude Code, Google Antigravity, …) lẫn người đóng góp**.
File theo từng tool (vd `CLAUDE.md`) import file này — **chỉnh ở đây, không chỉnh nơi khác.**

## 1. Dự án là gì
AI Agent hỗ trợ **phân tích & dự báo giá cao su** cho **Tập đoàn Công nghiệp Cao su Việt Nam (VRG)**.
Đơn vị triển khai: **Bizino AI + Thái Hưng Infotech**. Giai đoạn: **PoC — Đề án A**.

| Hạng mục | Giá trị |
|---|---|
| Khách hàng | VRG (Vietnam Rubber Group) — "DRG" = bí danh nội bộ trong deck |
| Mặt hàng PoC | SVR 10 (kiến trúc sẵn sàng mở rộng: SVR CV/L/3L/20, RSS3, Latex) |
| Mục tiêu độ chính xác | MAPE ≤ 6% (7 ngày), ≤ 10% (30 ngày) |
| 3 đầu ra | Dashboard đa sàn · Dự báo Bull/Base/Bear · Executive RAG Command Center + cảnh báo |
| Nguồn sự thật phạm vi | `docs/proposal/` (Kế hoạch Triển khai) |

> ⚠️ Đề án B (Sàn TMĐT B2B) **ngoài phạm vi** repo này — đừng trộn vào.

## 2. Kiến trúc & Stack (Hybrid AI, API-first)
- **Quantitative**: Prophet · XGBoost · LightGBM · LSTM — chuỗi thời gian, kịch bản.
- **Qualitative (LLM)**: Claude API (Anthropic) / GPT — phân tích ngữ cảnh, hỏi đáp tiếng Việt.
- **RAG**: pgvector — tri thức nội bộ + trích dẫn (citation).
- **Backend**: FastAPI (Python). **Frontend**: React + TypeScript (Vite).
- **Data**: TimescaleDB (time-series) + pgvector (vector). **Pipeline**: Airflow/Prefect.
- **Hạ tầng**: Cloud Việt Nam (VNG/Viettel/VNPT) — data residency.

Chi tiết: [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md).

## 3. Bản đồ repo
```
apps/api        FastAPI gateway (routers, orchestration)
apps/web        React + TS — Dashboard · Forecast · Command Center
services/       crawlers · forecasting · rag · notifications
packages/       shared-py · shared-ts (dùng chung)
pipelines/      Airflow/Prefect DAGs (ETL)
knowledge/      ★ tri thức dùng chung (Markdown + YAML) — xem knowledge/README.md
data/           raw/ (gitignored) · templates/ · samples/
docs/           architecture · project · proposal · (data, bieu-mau = nguồn mật, gitignored)
infra/          docker-compose, init DB
plans/          kế hoạch triển khai
```

## 4. Tri thức tương thích 2 nền tảng (QUAN TRỌNG)
- Tri thức = **Markdown + YAML frontmatter**, kebab-case, **1 chủ đề / 1 file**, đặt trong `knowledge/`.
- Cả Claude + Antigravity + RAG đều đọc được. **Không dùng cú pháp riêng của bất kỳ tool nào** trong file knowledge.
- Format chi tiết: [knowledge/README.md](knowledge/README.md).
- Dữ liệu mật (Excel/PDF) **không commit** — chỉ commit fact đã trích xuất sang Markdown.

## 5. Quy ước
- **Đặt tên file**: kebab-case, mô tả rõ mục đích (đọc tên là hiểu ngay).
- **Kích thước**: file code < 200 dòng; tách module khi vượt.
- **Nguyên tắc**: YAGNI · KISS · DRY.
- **Commit**: Conventional Commits (`feat:`, `fix:`, `docs:`…), tiếng Anh, không tham chiếu AI.
- **Ngôn ngữ**: tài liệu & giao tiếp tiếng Việt; code & định danh tiếng Anh.
- **Bảo mật**: không hardcode secret; dùng `.env` (xem `.env.example`).

## 6. Chạy dự án (cổng riêng VRG: API 8390 · Web 5390 · DB 5433)
```bash
# Nhanh nhất — 1 lệnh chạy CẢ API + Web (hoặc gõ /dev trong Claude Code):
./scripts/dev.sh                                     # Ctrl+C để dừng cả hai

# Hoặc chạy riêng:
# API (FastAPI) — http://localhost:8390/health
cd apps/api && uv sync && uv run python -m app      # chạy theo API_PORT (mặc định 8390)
cd apps/api && uv run pytest                         # test

# Web (React+TS+Vite) — http://localhost:5390 · có nút "Quét giá ngay"
cd apps/web && pnpm install && pnpm dev
cd apps/web && pnpm build                            # build production

# DB (TimescaleDB + pgvector) — host 5433
docker compose -f infra/docker/docker-compose.yml up db
```
> Cổng đổi qua `.env` (`API_PORT`/`WEB_PORT`/`DB_PORT`) — xem `.env.example`. Web gọi API qua `VITE_API_URL`.
> `apps/web/pnpm-workspace.yaml` đã bật `allowBuilds: esbuild` (pnpm 10+ chặn build script mặc định).

## 7. Bảo mật & tuân thủ
- Data residency 100% tại Việt Nam; Zero Data Retention với LLM API (hợp đồng Business/Enterprise).
- Mã hóa AES-256 (lưu trữ) / TLS 1.3 (truyền tải). Tuân thủ **Nghị định 13/2023/NĐ-CP**.

## 8. Trạng thái
PoC — đang dựng cấu trúc. Roadmap: [docs/project/development-roadmap.md](docs/project/development-roadmap.md).
