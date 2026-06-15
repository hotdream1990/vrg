# AI Agent Dự báo Giá Cao su — VRG

Hệ thống AI hỗ trợ **phân tích & dự báo giá cao su** cho **Tập đoàn Công nghiệp Cao su Việt Nam (VRG)**.
Triển khai bởi **Bizino AI + Thái Hưng Infotech**. Giai đoạn hiện tại: **PoC (Đề án A)**.

## Ba đầu ra chính
1. **Dashboard giám sát đa sàn** — TOCOM · SICOM · SHFE · AFET + vĩ mô (dầu, tỷ giá, PMI).
2. **Dự báo giá** — Hybrid AI (định lượng + LLM), ma trận kịch bản **Bull / Base / Bear**.
3. **Executive AI Command Center** — RAG chatbot hỏi đáp tiếng Việt + cảnh báo đa kênh.

## Bắt đầu từ đâu
| Bạn là | Đọc |
|---|---|
| AI agent / dev mới | [AGENTS.md](./AGENTS.md) |
| Muốn hiểu kiến trúc | [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) |
| Muốn xem lộ trình | [docs/project/development-roadmap.md](docs/project/development-roadmap.md) |
| Cần biết data phải có | [docs/project/data-checklist.md](docs/project/data-checklist.md) |
| Đóng góp tri thức | [knowledge/README.md](knowledge/README.md) |

## Cấu trúc thư mục
Xem mục **Bản đồ repo** trong [AGENTS.md](./AGENTS.md#3-bản-đồ-repo).

## Lưu ý
- Tương thích **cả Claude Code và Google Antigravity** — tri thức là Markdown + YAML thuần.
- Dữ liệu mật của VRG **không commit** (đã cấu hình trong `.gitignore`).
