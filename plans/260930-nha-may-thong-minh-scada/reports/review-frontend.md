# Review FRONTEND — Nhà máy thông minh (SCADA) · 30/09/2026

Góc: đúng hợp đồng API · UX nghiệp vụ · nhất quán với hệ hiện có. Chỉ đọc, không sửa code.

## Phạm vi
- `apps/web/src/lib/smart-factory-client.ts` (152 dòng)
- `apps/web/src/features/command-center/pages/smart-factory/*` (11 file, ~1.070 dòng)
- `lib/permissions.ts`, `App.tsx`, `sidebar-menu-builders.tsx` (diff)
- Đối chiếu: `routers/smart_factory.py`, `smart_factory_admin.py`, `services/scada_daily_meters.py`,
  `scada_client.py`, `scada_factory_repo.py`, `core/access_meta.py`
- `tsc --noEmit -p apps/web/tsconfig.json`: **PASS** (0 lỗi). Mọi file < 200 dòng.

## Đánh giá chung
Chất lượng tốt: khớp hợp đồng (khoá, null, cờ), race đổi nhà máy/đổi kỳ đã chặn bằng cờ `alive`,
thời điểm cắt chuỗi (không `new Date()`), số vi-VN, `null` luôn "—", chỉ icon `@ant-design/icons`,
chữ hướng dẫn trong form dùng `.form-note`, mật khẩu `autoComplete="new-password"` + trống → `null`,
regex tag/ident khớp đúng server, route/menu/cap đúng cho admin · editor · executive · member/leader.
**Không có lỗi mức High.** Còn 6 điểm Medium chủ yếu về UX nghiệp vụ và nhất quán.

---

## HIGH
Không có.

## MEDIUM

### M1. Đổi nhà máy: số của nhà máy CŨ vẫn hiện dưới lớp Spin
- `FactoryMetersPage.tsx:95-105, 122, 165-177`
- Kịch bản: đang xem NM A → chọn NM B (SCADA B chậm/không tới được: login_timeout 10s + query
  60s×2). Toolbar đã ghi "NM B" nhưng KPI/biểu đồ/bảng + "Số đọc lúc…" vẫn là số NM A (chỉ mờ đi) tới
  1–2 phút; bộ cột có thể sai (A có số bành, B không). Dễ đọc nhầm/chụp màn hình nhầm.
- Race phản hồi cũ đè mới: **không xảy ra** (cờ `alive` đúng).
- Sửa: chỉ giữ `data` khi cùng nhà máy —
  `const shown = badRange || data?.factory.id !== factoryId ? null : data;`
  (đổi kỳ vẫn giữ số cũ dưới Spin, đổi nhà máy thì hiện Skeleton).

### M2. Nhà máy chưa khai tag → thành lỗi đỏ 502; Alert "chưa khai tag" là code chết
- `FactoryMetersPage.tsx:95-105, 169-172` · backend `scada_client.py:138-142` → `smart_factory.py:63-65`
- Backend ném `ScadaError` khi không có tag → **502**, nên nhánh `shown.metrics.length === 0` không
  bao giờ chạy. Người xem (editor/executive) thấy "Không đọc được số liệu SCADA" + "vào Cấu hình để
  khai" (họ không vào được) + nút "Thử lại" vô ích; mỗi lần còn mở kết nối SCADA.
- `FactoryBrief.metrics` đã có sẵn trong `/factories` nhưng web không dùng.
- Sửa: trước khi gọi API, `if (!factory.metrics.length)` → hiện Alert info (admin kèm link cấu hình),
  không gọi `/meters/daily`; bỏ Alert chết ở dòng 169-172.

### M3. Thứ tự 4 tag điện (R0→R3) có thể đảo mà không bị bắt
- `ScadaFactoryFormModal.tsx:90-101`, `scada-form-rules.ts:64-74`
- `Select mode="tags"` giữ thứ tự THEO LẦN CHỌN. Admin gỡ `PM_EnergyReal1` rồi chọn lại → thành
  `R0,R2,R3,R1`, vẫn đủ 4 tag nên qua kiểm tra, server tính kWh sai hàng tỷ lần mà không báo.
- Sửa (KISS): 4 ô `Input` cố định nhãn "R0 (cao nhất)… R3 (thấp nhất)" + 1 công tắc "SCADA đã có
  kWh (1 tag)"; hoặc tối thiểu `tagRender` hiện số thứ tự R0..R3 trên từng tag.

### M4. "TB/ngày" tính cả hôm nay chưa trọn ngày
- Backend `scada_daily_meters.py:170-177` (`days_with_data` gồm ô `in_progress`);
  hiển thị `FactoryMeterKpis.tsx:22-25`, `FactoryMeterTable.tsx:122`.
- Kịch bản: 8h sáng xem 30 ngày → hôm nay mới ~1/3 ngày nhưng vẫn đếm là 1 ngày → TB/ngày bị kéo thấp
  ~2% (7 ngày: ~10%). Người đọc so định mức sẽ hiểu sai.
- Sửa: backend loại ô `in_progress` khỏi `avg_per_day`/`days_with_data` (tổng vẫn cộng), cập nhật
  api-contract; hoặc tối thiểu web ghi chú "TB/ngày tính cả hôm nay (chưa trọn ngày)".

### M5. Lịch sử truy cập sẽ hiện đường dẫn thô cho 2 trang mới
- `apps/api/app/core/access_meta.py:13` (`PAGES`) — docstring dòng 7 ghi rõ "Trang mới thêm vào
  App.tsx nhớ khai một dòng ở đây".
- Sửa: thêm `"/nha-may-thong-minh/chi-so": "Chỉ số điện · nước · số bành"`,
  `"/nha-may-thong-minh/cau-hinh-scada": "Cấu hình kết nối SCADA"`.

### M6. Nhà máy bị tắt/xoá khi đang xem → 404 lặp mãi, danh sách không làm mới
- `FactoryMetersPage.tsx:102, 159-164`
- Kịch bản: admin tắt NM đang xem → "Tải lại"/"Thử lại" luôn 404; Select vẫn liệt kê NM đó tới khi
  F5. (localStorage trỏ NM đã xoá lúc mở trang thì đã xử lý đúng — rơi về NM đầu tiên.)
- Sửa: trong `.catch`, `if (e instanceof ApiError && e.status === 404) setListTick(t => t + 1)`.

## LOW

| # | File:dòng | Vấn đề | Đề xuất |
|---|---|---|---|
| L1 | `smart-factory-format.ts:13-14` · BE `scada_daily_meters.py:166` | Tiêu thụ hiện 2 số lẻ nhưng server làm tròn 3 số rồi mới cộng → cộng tay cột trên web có thể lệch dòng "Tổng" vài phần trăm đơn vị (92 dòng tới ±0,46) | Để `USED_DIGITS` điện/nước = 3 cho khớp (hoặc chấp nhận, ghi chú) |
| L2 | `smart-factory-format.ts:14` | TB/ngày số bành hiện số nguyên (212,5 → "213") | TB/ngày dùng 1 số lẻ riêng cho bành |
| L3 | `FactoryMeterTable.tsx:79-80` | Dòng hôm nay chỉ tô nền khi cờ `in_progress`; hôm nay bị `no_data`/`reset` thì mất nền | So `r.date === data.fetched_at.slice(0,10)` |
| L4 | `ScadaTestResultModal.tsx:21-23` | `ok=true` nhưng "10 phút gần nhất không có số"/"chưa khai tag" vẫn hiện icon xanh thành công; còn so khớp nguyên văn chuỗi `"Kết nối thành công"` của server | `status = result.latest_at ? "success" : "warning"`; luôn hiện `detail` |
| L5 | `smart-factory-format.ts:80-83` · `FactoryMetersPage.tsx:67` | Kỳ mặc định tính 1 lần lúc mở trang theo đồng hồ trình duyệt: để trang qua đêm, "Tải lại" không có ngày mới | Chấp nhận (VN/LA/KH cùng UTC+7) hoặc tính lại khi bấm Tải lại nếu kỳ đang là preset |
| L6 | `FactoryMeterToolbar.tsx:39-44` | Cho chọn >92 ngày rồi mới cảnh báo | `disabledDate={(d, { from }) => isFutureDay(d) \|\| (!!from && Math.abs(d.diff(from,"day")) >= MAX_DAYS)}` |
| L7 | `ScadaFactoryFormModal.tsx:66-75` | Host/tài khoản: server cấm khoảng trắng bên trong, tài khoản ≤128 ký tự — web không chặn trước (vẫn hiện 400 đúng) | Thêm `pattern: /^\S+$/` + `max: 128` |
| L8 | `ScadaFactoryFormModal.tsx:36-38, 54` | 409 trùng tên chỉ hiện Alert đầu modal (form dài thì phải cuộn lên mới thấy) | 409 → `form.setFields([{ name: "name", errors: [msg] }])` |
| L9 | `scada-form-rules.ts:26-30` | Form thêm mới điền SẴN `Water_TotalVolume` + 4 tag điện mặc định; tag không tồn tại trong WideHistory làm OPENQUERY lỗi → 502 cả trang (mất cả điện) | Đưa mặc định vào placeholder/gợi ý, không điền sẵn; hoặc nhắc bấm "Kiểm tra kết nối" sau khi lưu |
| L10 | `ScadaConfigPage.tsx:50-60` | `load()` không chặn phản hồi cũ: tải lần đầu chậm + vừa lưu xong → danh sách cũ có thể đè danh sách mới | Dùng bộ đếm yêu cầu (`reqId`) như cờ `alive` |
| L11 | `sidebar-menu-builders.tsx:96` vs `:114` | Cùng `ThunderboltOutlined` với "Quét Đa sàn" trong cùng menu | Đổi icon mục chỉ số (vd `DashboardOutlined`/`FundProjectionScreenOutlined`) |
| L12 | `smart-factory-client.ts:82-136`, `:150-152` | DRY: tự viết lại `downloadAuthed` (`weekly-report-client.ts:122`) + `errorMessage` của `http.ts`; `slug` dùng ký tự tổ hợp NGUYÊN VĂN `[̀-ͯ]` (khó đọc, dễ vỡ khi format) trong khi `DashboardFilterBar.tsx:42` viết `̀-ͯ` | Tách 1 helper `downloadAuthed(path, fallbackName)` vào `http.ts` (đọc Content-Disposition); regex dùng escape `\u` |
| L13 | `smart-factory-format.ts:43` · `FactoryMeterCharts.tsx:13` · `FactoryMeterTable.tsx:27` · 2 trang | `ddmm` trùng `dm` ở `lib/date.ts`; `upperFirst` lặp 2 file; `errText` lặp 2 trang | Dùng `dm`; đưa `upperFirst` vào `smart-factory-format.ts` |
| L14 | `FactoryMetersPage.tsx:95-105` | Không huỷ fetch (AbortController) khi đổi nhà máy/kỳ — server vẫn giữ luồng đọc SCADA tới 70s; không có gợi ý "SCADA có thể mất tới ~1 phút" | Thêm `AbortController` + dòng mô tả trong Spin |

## Đối chiếu yêu cầu soi kỹ
1. **Hợp đồng**: khớp đủ khoá/kiểu (`MeterCell`, `flag` 5 giá trị, `summary`, `intensity` null/obj,
   `kwh_per_bale`/`m3_per_bale`, test `values` chỉ có khoá của chỉ số đã khai → web dùng `"x" in v` đúng).
   Lệch duy nhất: metric rỗng ra 502 (M2).
2. **Trạng thái**: loading (Skeleton/Spin) OK; 502 hiện `detail` OK; không có nhà máy OK (admin có
   nút cấu hình); race OK; localStorage NM đã xoá OK; số cũ khi đổi NM (M1); 404 lặp (M6).
3. **RangePicker**: mặc định 30 ngày, chặn tương lai, preset, hôm nay đều đúng; >92 chỉ cảnh báo sau (L6).
4. **Bảng/biểu đồ**: cờ có icon + Tooltip giải thích tiếng Việt, cột hôm nay tô nhạt, null = trống
   (không vẽ 0); dòng Tổng đọc thẳng `summary` (lệch làm tròn L1); 92 dòng không vấn đề hiệu năng.
5. **Form**: trống mật khẩu → `null` OK; điện 0/1/4 + regex khớp server OK; 400/409/422 hiện `detail` OK;
   thứ tự tag (M3).
6. **Quyền**: admin thấy 2 mục; editor có cap chỉ thấy mục chỉ số, gõ URL cấu hình → 403 (RequireRole);
   executive thấy mục chỉ số (GET qua guard); member/leader không có menu, `effectiveCaps` rỗng →
   RequireCap 403, server `require_cap` cũng chặn. Thiếu nhãn Lịch sử truy cập (M5).
7. **DRY**: L12, L13.

## Việc nên làm (theo thứ tự)
1. M1 + M2 + M6 (cùng `FactoryMetersPage.tsx`, ~10 dòng).
2. M3 (form tag điện) — rủi ro sai số liệu thật.
3. M4 (chốt với chủ dự án: TB/ngày có tính hôm nay không) → sửa backend + contract.
4. M5 (2 dòng `access_meta.py`).
5. Low tuỳ thời gian; L4, L9, L12 đáng làm trước.

## Câu hỏi treo
- TB/ngày (và "ngày có số") có loại ngày hôm nay chưa trọn ngày không? (M4)
- Có muốn tag không tồn tại chỉ làm trống chỉ số đó thay vì 502 cả trang không? (L9 — cần backend
  thử từng nhóm tag hoặc kiểm tag lúc lưu.)
