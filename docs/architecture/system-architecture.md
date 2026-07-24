# Kiến trúc Hệ thống — AI Dự báo Giá Cao su (PoC)

> Nguồn: Kế hoạch Triển khai (Đề án A). Kiến trúc **Hybrid AI, API-first**.

## 1. Tổng quan
Hệ thống kết hợp **AI Định lượng** (xử lý chuỗi thời gian) và **AI Định tính** (LLM/RAG xử lý
ngữ cảnh, tin tức, báo cáo) để tạo ra dự báo giá + khuyến nghị cho lãnh đạo VRG.

## 2. Các khối thành phần
| Khối | Công nghệ (PoC) | Vai trò |
|---|---|---|
| Quantitative Block | Prophet, XGBoost, LightGBM, LSTM | Dự báo chuỗi thời gian, sai số, kịch bản Bull/Base/Bear |
| Qualitative Block (LLM) | Claude API / GPT | Phân tích ngữ cảnh, tóm tắt báo cáo, hỏi đáp tiếng Việt |
| RAG Engine | pgvector | Lưu & truy xuất tri thức nội bộ + citation |
| Agent Orchestration | Bizino AI Agent Framework | Điều phối luồng giữa các khối AI |
| Data Pipeline | Airflow / Prefect | Thu thập, làm sạch, chuẩn hóa dữ liệu |
| Backend API | FastAPI (Python) | API cho Dashboard & Chatbot |
| Frontend | React + TypeScript | Dashboard giám sát & giao diện chat |
| Time-series DB | TimescaleDB | Lưu giá, khối lượng, chỉ số theo thời gian |
| Vector DB | pgvector | Embedding tài liệu cho RAG |
| Hạ tầng | Cloud VN (VNG/Viettel/VNPT) | Data residency 100% tại Việt Nam |

## 3. Bốn module nghiệp vụ (SOW)
1. **Dashboard Giám sát Thị trường Đa sàn** — crawler 4 sàn (TOCOM/SICOM/SHFE/AFET) < 60s,
   so sánh Premium/Discount với giá sàn VRG, tích hợp vĩ mô (WTI/Brent, USD/VNĐ, USD Index, PMI TQ).
2. **Hệ thống AI Dự báo Giá** — dự báo "đầu ngày" (Expected + CI 80%) ↔ đối chiếu "cuối ngày"
   (Anomaly Detection tự hiệu chỉnh); ma trận **Bull / Base / Bear**.
3. **Executive AI Command Center** — OCR + vector hóa tri thức nội bộ; hỏi đáp tiếng Việt cho
   3–5 lãnh đạo; mọi câu trả lời kèm **citation**.
4. **Hệ thống Cảnh báo Đa kênh** — ngưỡng linh hoạt; gửi Email/Zalo OA/Telegram; báo cáo tự động 07:30 & 17:00.

## 4. Ánh xạ sang code (`services/`)
| Module nghiệp vụ | Thư mục |
|---|---|
| Dashboard data ingestion | `services/crawlers/` + `pipelines/` |
| Dự báo & kịch bản | `services/forecasting/` |
| RAG & Command Center | `services/rag/` + `apps/api` + `apps/web` |
| Cảnh báo & báo cáo | `services/notifications/` |

## 5. Bảo mật
Data residency VN · Zero Data Retention (LLM API) · AES-256 / TLS 1.3 · SSO Active Directory VRG ·
Audit log · tuân thủ Nghị định 13/2023/NĐ-CP. Xem thêm mục 7 trong [AGENTS.md](../../AGENTS.md).

### 5.1 Nhật ký hoạt động (audit log)
Bảng `audit_log` ghi 1 dòng cho mỗi lần ghi/xoá số liệu — không ghi đè, nên truy được **ai · lúc nào ·
bản ghi nào · giá trị trước → sau**, kể cả bản ghi đã bị xoá.

| Thành phần | Vai trò |
|---|---|
| `app/core/request_ctx.py` | Ngữ cảnh request (người thao tác · IP · admin đăng nhập hộ), đặt ở middleware |
| `app/services/audit_repo.py` | `log()` khi có thay đổi + `search()` tra cứu |
| Điểm gắn | Các hàm GHI ở tầng repo (`price_repo`, `floor_repo`, `unit_daily_repo`, …) → mọi lối vào đều được ghi |
| `app/routers/audit.py` | `GET /api/audit` (chỉ đọc, gác quyền `audit`) |

Quy ước: mật khẩu/secret chỉ ghi nhận "đã đổi", không lưu giá trị; dữ liệu phái sinh (mirror) tạm tắt
nhật ký để khỏi trùng; các màn tự động lưu được gộp lần lưu liên tiếp trong 10 phút của cùng người.
