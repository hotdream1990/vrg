# Sửa backend sau review — Nhà máy thông minh (SCADA) · 30/09/2026

Phạm vi: 13 mục trong phiếu giao việc (review-security / review-correctness / review-frontend).
Chưa commit git. Chỉ chạy truy vấn SELECT trên SQL Server **giả lập** `localhost:14330`, không kết nối máy thật.

## File đã sửa / tạo (số dòng)
| File | Dòng | Việc |
|---|---|---|
| `apps/api/app/services/scada_client.py` | 179 (từ 200) | Bỏ phần "Chi tiết" khi thông điệp lặp mật khẩu (không phân biệt hoa thường), không che bằng `***` nữa · `timeout=30` · `probe` đọc thêm `server_time` (1 câu `PROBE_SQL`) · chuyển `check_connection` sang module mới |
| `apps/api/app/services/scada_connection_check.py` | 90 (mới) | Nút Kiểm tra kết nối: `server_time`, `warnings` (múi ≠ +07:00 · đồng hồ lệch > 5 phút · 10 phút không có số · từng chỉ số không có số), `values` = số mới nhất của TỪNG chỉ số (`dm.latest_of`), `latest_at` = mốc mới nhất trong các số đó |
| `apps/api/app/services/scada_read_guard.py` | 80 (mới) | Khoá theo nhà máy `acquire(timeout=15)` → `ScadaBusyError` (429) · cache 60s theo khoá (id, updated_at, start, end) · lỗi không cache |
| `apps/api/app/services/scada_daily_meters.py` | 198 (từ 197) | Gộp mẫu phút vào chuỗi giờ (`merge_samples`) · `reset` khi có lần giảm giữa hai mẫu kề nhau (so sau làm tròn) · hôm nay có mẫu đúng D+1 00:00 thì đóng như ngày thường · `days_complete`, `avg_per_day` chỉ ngày đủ số · suất tiêu hao chỉ ngày cả hai ô đủ số · bỏ tham số `latest` khỏi phần tính dòng |
| `apps/api/app/services/scada_factory_repo.py` | 198 (từ 184) | PUT đổi host/cổng/tài khoản mà trống mật khẩu → 400 · tag trùng (không phân biệt hoa thường) → 400 |
| `apps/api/app/services/scada_meters_excel.py` | 169 (từ 151) | "N ngày có số" (Tổng) / "N ngày đủ số" (BQ) · ô hôm nay tô xanh, thiếu số/đặt lại tô vàng + chú giải đúng · ẩn cột kWh/bành, m³/bành khi thiếu chỉ số |
| `apps/api/app/routers/smart_factory.py` | 120 (từ 88) | 400 chưa khai tag · 400 "Từ ngày không được sau hôm nay." · `query_bounds` (kỳ đã qua: D+1 00:00 + 1 giờ) · 429 · 502 admin đủ chi tiết / người khác câu ngắn + `logger.warning` (tên nhà máy + chi tiết) |
| `apps/api/app/routers/smart_factory_admin.py` | 76 | Gọi `scada_connection_check.check_connection` |
| `apps/api/app/core/access_meta.py` | 109 | Nhãn 2 trang `/nha-may-thong-minh/chi-so`, `/nha-may-thong-minh/cau-hinh-scada` |

Test:
| File | Dòng | Nội dung |
|---|---|---|
| `tests/test_scada_daily_meters.py` | 199 | Cập nhật `days_complete` |
| `tests/test_scada_daily_meters_edge_cases.py` | 144 (mới) | Đặt lại về 0 lúc 00:00 · đặt lại lúc 06:00 (cuối > đầu vẫn reset) · thanh ghi lệch nhịp · nhiễu dấu phẩy động · mẫu sau D+1 00:00 không tính · hôm nay chỉ có mẫu phút · đồng hồ SCADA nhanh/chậm quanh nửa đêm · BQ + suất tiêu hao khi có partial/in_progress |
| `tests/test_scada_read_guard.py` | 131 (mới) | Cache TTL/khoá cache/lỗi không cache · bận → ScadaBusyError · lượt chờ dùng lại kết quả · `resolve_period` biên 92/93 + từ ngày tương lai · `query_bounds` end + 1h |
| `tests/test_scada_connection_check.py` | 94 (mới) | Đọc `server_time`, cảnh báo múi/đồng hồ, số mới nhất từng chỉ số, không có số, lỗi |
| `tests/test_scada_meters_excel.py` | 60 (mới) | Nhãn ngày, màu hôm nay ≠ thiếu số, ẩn cột suất tiêu hao |
| `tests/test_smart_factory_api.py` | 340 (từ 299) | PUT đổi host/cổng/tài khoản không mật khẩu → 400 (khác hoa thường/khoảng trắng = không đổi) · tag trùng → 400 · mật khẩu yếu "able" · probe 3 phần tử · end + 1h · .xlsx dùng cache · date_from tương lai · tách `setup_users()` |
| `tests/test_smart_factory_api_hardening.py` | 114 (mới) | 502 theo vai trò (JSON + .xlsx) + log không có mật khẩu · 429 (nhà máy khác không bị chặn) · cache hết hạn khi sửa cấu hình · 400 chưa khai tag (không chạm SCADA) · nhãn Lịch sử truy cập |

## Kết quả kiểm tra
- `pytest` 8 file SCADA/smart-factory + `test_access_log.py`: **122 passed**.
- `ruff check` các file đã sửa/tạo: sạch.
- Toàn bộ `uv run pytest -q`: **898 passed, 5 skipped, 3 failed**. Cả 3 test hỏng là 3 test đã hỏng sẵn trong `test_sales_contract.py` (tìm khách hàng, do DB dev là bản sao prod). Không phát sinh test hỏng mới.
- Sau khi chạy: DB dev còn 0 nhà máy `_zz_sf…` và 0 tài khoản `sf_…`.
- E2E với Historian giả lập (chỉ SELECT): kiểm tra kết nối trả `server_time` +07:00, `warnings: []`; kỳ 10–21/09 đúng 2 bẫy dữ liệu (12/09 nước → 11/09 và 12/09 `partial`; 20/09 bành `no_data`, 19/09 `partial`), không có `reset` giả; kỳ gồm hôm nay: hôm nay `in_progress` đóng bằng mẫu phút mới nhất; lần đọc thứ 2 lấy từ cache (0,01 ms); mật khẩu "Unable" → bỏ phần chi tiết.
- Dữ liệu test (`_zz_sf…`, `sf_…`) + cache dọn trong fixture.

## Lệch khỏi / bổ sung so với api-contract
1. **Kiểm tra kết nối, trường hợp 10 phút không có số**: trước đây câu này nằm trong `detail`. Nay `detail` = "Kết nối thành công", câu "10 phút gần nhất Historian không có số của các tag đã khai." chuyển vào `warnings` (đúng mục "Sửa đổi sau review"). FE nên xét `latest_at == null` hoặc `warnings.length` để hiện trạng thái vàng.
2. **Khi đã khai tag**, `values` / `raw` / `latest_at` LUÔN có mặt: chỉ số không có số → `null`; `latest_at` null nếu không có số nào. `raw` = số mới nhất có giá trị của từng tag. Nhà máy chưa khai tag: như cũ (không có 3 khoá này), `warnings: []`.
3. `server_time` = `null` nếu không đọc được giờ máy SQL Server; khi đó thêm cảnh báo "Không đọc được giờ của máy SCADA…". Chênh đồng hồ so theo thời điểm tuyệt đối (UTC); múi giờ kiểm riêng. Hai cảnh báo độc lập.
4. Ô `reset` vẫn giữ `open/close` (chỉ `used = null`) như trước. Chú giải `reset` trên Excel đổi thành "Số bị giảm trong ngày…".
5. Hôm nay có mẫu đúng mốc D+1 00:00 (đồng hồ SCADA nhanh hơn app) → ô KHÔNG mang cờ `in_progress` (đóng như ngày thường, được tính vào `days_complete`).
6. `summary.latest` vẫn chỉ lấy từ truy vấn mẫu phút (null nếu truy vấn đó không có số), đúng contract.
7. Chỉ có khoá theo từng nhà máy. Semaphore chung toàn app (review-security M2 gợi ý) KHÔNG làm vì phiếu giao việc không yêu cầu (YAGNI).
8. `check_connection` chuyển từ `scada_client` sang module `scada_connection_check` vì `scada_client.py` đã đủ 200 dòng.

## Còn treo / cần lưu ý
- Tên tài khoản `scada_ro` vẫn nằm trong detail 502 của admin. Đây là chủ ý, vì admin cần tài khoản đó để tự khoanh vùng lỗi.
- `encryption="require"` (review-security H2) chưa làm vì không có trong danh sách.
- `tests/test_smart_factory_api.py` dài 340 dòng (trước đây đã 299). Test mới đã tách sang file riêng, file cũ chưa tách thêm.
