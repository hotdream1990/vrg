# Nhà máy thông minh — Chỉ số điện · nước · số bành (SCADA / AVEVA Historian)

Ngày: 30/09/2026 · Nhánh: `feature/master-contract` (làm tiếp trên nhánh hiện tại)

## Mục tiêu
Nhóm menu mới **Nhà máy thông minh**. Mục con đầu tiên: **Chỉ số điện · nước · số bành** theo NGÀY
(mặc định 30 ngày gần nhất), đọc thẳng từ SQL Server của SCADA (Wonderware/AVEVA Historian,
linked server `INSQL`, bảng `WideHistory`). Cấu hình kết nối do admin khai trên UI, NHIỀU nhà máy
(mỗi nhà máy một SCADA, tag có thể đặt tên khác nhau).

## Quyết định thiết kế
| Hạng mục | Chốt |
|---|---|
| Driver | `pymssql` (wheel pip có sẵn FreeTDS — không cần cài ODBC hệ thống vào image) |
| Cấu hình | Bảng `scada_factory` (1 dòng / nhà máy). Mật khẩu KHÔNG bao giờ trả ra API |
| Truy vấn | `OPENQUERY(<linked>, '...FROM WideHistory ... wwRetrievalMode=''Cyclic'' ...')`, chuỗi dựng bằng code, định danh (tag, linked server) kiểm regex nghiêm → chống injection |
| Chỉ số ngày | Lấy mẫu Cyclic **theo giờ** (`wwResolution = 3600000`) từ 00:00 ngày đầu → 00:00 ngày sau ngày cuối (hoặc `GetDate()` nếu gồm hôm nay). Chỉ số đầu ngày D = giá trị lúc D 00:00; chỉ số cuối = giá trị lúc D+1 00:00 (hôm nay = số mới nhất). Tiêu thụ = cuối − đầu → tổng các ngày = tổng cả kỳ, không rơi phần tiêu thụ giữa 2 lần ghi như hệ cũ |
| Số mới nhất | Truy vấn phụ `DateTime >= DateAdd(mi,-10,GetDate())`, `wwResolution = 60000`, lấy dòng cuối có số |
| Điện | 4 thanh ghi 16-bit: `kWh = ((R0&0xFFFF)<<48 \| (R1&0xFFFF)<<32 \| (R2&0xFFFF)<<16 \| (R3&0xFFFF)) / 1000` — tính ở Python (int không tràn; `&0xFFFF` sửa thanh ghi bị đọc thành số âm). Khai 1 tag thì coi là kWh sẵn |
| Thiếu số | Mốc 00:00 trống → lấy mẫu có số đầu tiên TRONG ngày, gắn cờ `partial`. Cuối < đầu → tiêu thụ = null, cờ `reset`. Không mượn số ngày khác |
| Quyền | Cap mới `smart_factory` (1 cấp). Admin + Lãnh đạo Tập đoàn có sẵn. Cấu hình kết nối: chỉ admin |
| Giờ | Giờ Việt Nam (UTC+7 — VN/Lào/Campuchia cùng múi) |
| Kỳ tối đa | 92 ngày |

## Hợp đồng API (BE ↔ FE)
Xem [api-contract.md](./api-contract.md).

## Các nhánh (song song, file không giao nhau)
| Nhánh | Phạm vi | Trạng thái |
|---|---|---|
| A. Backend | services `scada_*`, router `smart_factory*`, bảng, cap, test, dep `pymssql` | ✅ |
| B. Frontend | client, 2 trang (chỉ số · cấu hình), menu, route, cap | ✅ |
| C. Historian giả lập | SQL Server Docker + linked server `INSQL` loopback + view `WideHistory` giả để chạy thử e2e | ✅ |
| D. Tích hợp + review | 3 review (đúng/sai · bảo mật · FE) → sửa; đối chiếu SCADA thật Phú Riềng khớp RELCO | ✅ |
| E. Deploy | `pymssql` vào image · Tailscale cho VPS (sidecar `scada-gw`) · cấp quyền `smart_factory` | ✅ 0.4.101 (30/09) |
| F. Sơ đồ vận hành | mimic 4 khu kiểu RELCO, `/plant/layout` + `/plant/live`, bố cục `plant_layouts/phu_rieng.json` — hợp đồng [so-do-van-hanh-contract.md](./so-do-van-hanh-contract.md) | ✅ local · ⏸ CHƯA deploy (chủ dự án dặn) |

## Kết quả đối chiếu SCADA thật (30/09/2026)
- Máy `desktop-ufvfvjk` (Tailscale 100.123.202.42), SQL Server 2016, múi +07:00, đồng hồ khớp.
- Tag: điện `PM_EnergyReal0..3`, nước `Water_TotalVolume`, số bành `RobotTotalCount` (tìm bằng bảng `Tag`).
- Tháng 09: điện/nước/bành khớp bảng RELCO từng ngày. Nhiễu thật: nước lùi 0,003 m³ lúc 05:00 08/09
  → luật reset dùng ngưỡng 1%.
- Tag có dấu cách (`PM - VoltAB`, `Z01 - Champer Temperature`…) chưa hợp regex tag hiện tại — mở
  rộng khi làm màn điện áp/dòng · nhiệt độ hầm sấy.

## Rủi ro
- **Mạng**: server VRG (cloud) phải tới được SQL Server trong LAN nhà máy (IP public/NAT 1433 hoặc VPN). Không tới được → cần agent tại nhà máy đẩy số lên (ngoài phạm vi bản này).
- Tag số bành chưa biết tên → để admin khai.
- Deploy image vá: thêm `pymssql` phải `uv sync` lại (không chỉ thay app/web).
