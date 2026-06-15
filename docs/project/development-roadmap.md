# Lộ trình Phát triển — PoC (Đề án A)

> Living document. Cập nhật trạng thái sau mỗi mốc. Phương pháp Agile, có demo với VRG mỗi Sprint.

## Trạng thái tổng
| Giai đoạn | Trạng thái | Ghi chú |
|---|---|---|
| Giai đoạn 0 — Cấu trúc & Tài liệu | 🟡 Đang làm | Dựng scaffold + docs (tài liệu này) |
| Giai đoạn 1 — PoC | ⚪ Chưa bắt đầu | 3 Sprint, demo & nghiệm thu với VRG |
| Giai đoạn 2 — On-premise | ⚪ Tương lai | Đánh giá sau khi PoC chứng minh hiệu quả |

> ⚠️ Cần VRG xác nhận: bản kế hoạch ghi "12 tuần / 3 Sprint × 4 tuần" nhưng bảng chi tiết là
> "Tuần 1–6". **Chốt lại tổng thời lượng** trước khi khởi động Sprint 1.

## Sprint (theo Kế hoạch Triển khai)
### Sprint 1 — Nền tảng dữ liệu & Dashboard MVP
- Khảo sát nghiệp vụ, ký NDA, thiết lập Cloud VN.
- Crawler 4 sàn (TOCOM/SICOM/SHFE/AFET) + API vĩ mô, kết nối BCTM nội bộ.
- Dashboard MVP (React) hiển thị giá real-time + lịch sử ~2 năm.
- **Bàn giao**: Dashboard 4 sàn + dữ liệu lịch sử + kết nối BCTM.

### Sprint 2 — AI Engine & Chatbot
- ETL tự động, vector hóa tài liệu nội bộ.
- Huấn luyện Quantitative (Prophet/XGBoost/LSTM) + tích hợp LLM (Qualitative).
- Scenario Engine Bull/Base/Bear; cấu hình cảnh báo đa kênh.
- Chatbot RAG (tiếng Việt + citation) tích hợp vào Dashboard.
- **Bàn giao**: Dự báo SVR 10 đầu/cuối ngày + Chatbot + cảnh báo Email/Zalo/Telegram.

### Sprint 3 — Kiểm thử & Nghiệm thu
- Shadow testing: AI vs chuyên gia VRG; tính MAPE; tinh chỉnh mô hình.
- Kiểm tra bảo mật, đào tạo người dùng, nghiệm thu, bàn giao tài liệu vận hành.
- **Bàn giao**: Báo cáo độ chính xác + hệ thống production-ready + đề xuất Giai đoạn 2.

## Tiêu chí thành công PoC
- Mặt hàng SVR 10: **MAPE ≤ 6% (7 ngày), ≤ 10% (30 ngày)**.
- Executive Command Center phục vụ 3–5 lãnh đạo, hỏi đáp tiếng Việt + citation.
- Cảnh báo đa kênh hoạt động; báo cáo tự động 07:30 & 17:00.
