# Hạng mục 5 — Snapshot số liệu tuần toàn hệ thống

Trạng thái: **xong** (backend + job + API + web + test). Chưa commit (agent chính commit).

## 1. Thiết kế bảng `unit_week_snapshot` (tạo idempotent trong `ensure_schema`)

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `week_start` | date **PK** | Thứ Hai (ISO) của tuần — mỗi tuần đúng 1 dòng |
| `week_end` | date | Chủ nhật |
| `purchase` | jsonb | NGUYÊN kết quả `period_report("purchase", T2, CN)` — đủ mọi cột, xuất lại Excel được |
| `consumption` | jsonb | NGUYÊN kết quả `period_report("consumption", T2, CN)` (tiêu thụ theo hợp đồng + tồn kho) |
| `totals` | jsonb | Dòng Tổng cộng của từng biểu (`{purchase:{…}, consumption:{…}}`), kèm `unit_count`, `reporting_units`, tồn theo chủng loại |
| `deadline_at` | timestamptz | Hạn nhập của ngày Chủ nhật tại lúc chụp |
| `taken_at` | timestamptz | Giờ chụp THẬT (DB `now()`) — so với `deadline_at` để biết chụp trễ |
| `taken_by` | text | `job` = tự động · username = admin bấm "Chụp ngay" |

Ghi bằng `INSERT … ON CONFLICT (week_start) DO NOTHING` ⇒ không bao giờ ghi đè; job và admin bấm cùng lúc thì chỉ một lượt được ghi. Không có đường sửa/xoá trong code.

Số liệu **không tính lại công thức nào**: gọi đúng `unit_period_report.period_report` (mặc định GỘP đơn vị sáp nhập, như màn Báo cáo tổng hợp) ⇒ bản lưu khớp tuyệt đối Báo cáo tổng hợp cùng kỳ tại thời điểm chụp.

## 2. Luật chọn tuần / giờ chụp

- Tuần = thứ Hai → Chủ nhật. Hạn chụp của tuần = `edit_window.deadline(Chủ nhật, member_window())` (giờ chốt `cutoff_hour()`, mặc định 11:00).
  - N = 1 ⇒ 11:00 thứ Hai tuần sau. N = 0 ⇒ 11:00 chính Chủ nhật. N = 7 ⇒ 11:00 Chủ nhật tuần sau.
- `due_week(now)` = tuần GẦN NHẤT đã qua hạn đó. Job chụp tuần này nếu **chưa có** bản lưu; có rồi thì thôi (ghi `meta_crawl_run` trạng thái `empty`).
- **Không chụp bù tuần cũ hơn, kể cả lần chạy đầu** (lý do ghi trong docstring `unit_week_snapshot.py` + mô tả job): số tuần cũ có thể đã được sửa sau hạn (đề nghị sửa được duyệt, admin sửa hộ) — chụp muộn hàng loạt không còn là "số chốt đúng hạn".
- Job `unit-week-snapshot` trong `JOB_REGISTRY`: **hằng ngày 11:10**, `catch_up=True`, seed bật. Admin xem/đổi giờ/tắt/"Chạy ngay" ở trang Lịch chạy.
- Màn hình tô nhãn **"chụp sau hạn"** khi `taken_at − deadline_at > 24 giờ` (đổi từ 1 giờ sau review), kèm câu "số có thể gồm cả phần sửa sau hạn".

## 3. Quyền

| Thao tác | Ai |
|---|---|
| Xem danh sách / chi tiết / Excel | quyền `unit_daily` (admin · chuyên viên được cấp · **lãnh đạo Tập đoàn** — `unit_daily` có trong `EXECUTIVE_CAPS`, mức xem) — cùng hàng rào Báo cáo tổng hợp |
| "Chụp ngay" | chỉ **admin** (`require_admin`; executive còn bị hàng rào chỉ-xem chặn thêm) |
| Tài khoản đơn vị (member/leader) | **403** (không có cap `unit_daily`); menu đơn vị không có mục này |

## 4. API — `/api/unit-week-snapshots` (router gắn `require_cap("unit_daily")` ở `main.py`)

- `GET ""` → `{items: [tóm tắt + totals], status: {due: {tuần, deadline_at, taken}, next: {tuần, deadline_at}}}`
- `GET /{week_start}` → bản lưu đầy đủ (400 nếu không phải thứ Hai, 404 nếu chưa chụp)
- `GET /{week_start}/excel` → 1 file 2 sheet (Thu mua · Tiêu thụ - Tồn kho) dựng bằng CHÍNH `unit_period_excel.build_period_xlsx` từ số đã lưu, thêm dòng 4 "BẢN LƯU … chụp lúc … (hạn nhập …)"
- `POST /take` (admin) → chụp tuần gần nhất đủ điều kiện; đã có ⇒ **409** "đã có bản lưu lúc … — không chụp đè"

## 5. Web — route `/snapshot-so-lieu-tuan`, menu "Snapshot số liệu tuần" (nhóm Báo cáo & Thống kê, ngay dưới Báo cáo tổng hợp; có cả ở menu Lãnh đạo Tập đoàn)

- Dải trạng thái: "Tuần 38 (14/9 – 20/9/2026): tự chụp sau hạn nhập 11:00 ngày 27/09/2026"; nếu tuần đủ điều kiện chưa có bản lưu → câu cảnh báo + nút **Chụp ngay** (chỉ admin, có Popconfirm).
- Trái: danh sách tuần (Tuần N/năm · khoảng ngày · giờ chụp · nhãn "chụp tay"/"chụp sau hạn").
- Phải: tiêu đề tuần + **Xuất Excel** + Alert "Số liệu chốt tự động lúc {giờ} ngày {…} — sửa số liệu sau thời điểm này không làm đổi bản lưu." + bảng từng đơn vị, 3 nhóm cột **Thu mua** (mủ nước · chén · dây · tổng · thành phẩm · % KH) · **Tiêu thụ** (tổng · XK · trong nước · nội bộ · doanh thu · giá BQ) · **Tồn kho** (ngày lấy số tồn — tô vàng nếu cũ hơn ngày nhập cuối · thành phẩm · chưa/đã nhập kho · đã ký HĐ chưa giao · nguyên liệu) + dòng **Tổng cộng lấy từ bản lưu**.
- Đã kiểm trên trình duyệt với bản API+Vite RIÊNG (cổng 8394/5394, DB `vrg_test_d`, đã tắt sau khi kiểm): danh sách, bảng, cuộn ngang, Chụp ngay → bản lưu mới hiện ngay, nút biến mất.

## 6. File

Tạo mới:
- `apps/api/app/services/unit_week_snapshot.py` — luật tuần/hạn, `build` (không ghi), `totals`, `take_due`, `status`, `run_job`
- `apps/api/app/services/unit_week_snapshot_repo.py` — insert-only, get, get_summary, list
- `apps/api/app/services/unit_week_snapshot_excel.py` — Excel 2 sheet
- `apps/api/app/routers/unit_week_snapshots.py`
- `apps/api/tests/test_unit_week_snapshot.py`
- `apps/web/src/lib/unit-week-snapshot-client.ts`
- `apps/web/src/features/command-center/pages/UnitWeekSnapshotPage.tsx`, `UnitWeekSnapshotTable.tsx`

Sửa (Edit tool, đúng vùng của mình):
- `apps/api/app/core/db.py` — khối `CREATE TABLE unit_week_snapshot` ngay sau `edit_request`
- `apps/api/app/services/scheduler.py` — khối đăng ký job sau `inventory-weekly` (import riêng trong khối)
- `apps/api/app/main.py` — import router + `include_router`
- `apps/web/src/App.tsx` — import + route trong nhóm `RequireCap unit_daily`
- `apps/web/src/features/command-center/sidebar-menu-builders.tsx` — icon `CameraOutlined`, `ITEM.weekSnapshot`, 2 menu

KHÔNG đụng `edit_window.py`, `unit_period_report.py`, `unit_period_excel.py`.

## 7. Kiểm thử

- `tests/test_unit_week_snapshot.py` (DB `vrg_test_d`): **4 passed** — hạn theo Chủ nhật + N (N=1 và N=7); trước hạn không chụp tuần đó / đúng 11:00 chụp, `rows` và `totals` == `period_report` cùng kỳ, tồn kho = ngày cuối có nhập tồn; chạy lại không sinh bản 2; sửa số sau khi chụp → báo cáo sống đổi (15 → 55 t) mà bản lưu y nguyên; member 403, executive xem 200 nhưng `POST /take` 403, admin chụp 200 rồi 409, Excel trả file xlsx. Dùng tuần 06–12/01/2025 để dọn không bao giờ đụng bản thật.
- Hồi quy liên quan: `test_scheduler_catchup` · `test_executive_readonly` · `test_leader_readonly` · `test_unit_consolidated_excel` → cùng lượt **31 passed**. `ruff` sạch. Web `tsc --noEmit` sạch.

## 8. Đối chiếu số thật (DB dev `vrg_caosu`, CHỈ ĐỌC)

⚠ DB dev là bản clone cũ: biểu Tồn kho/tiêu thụ dừng ở **22/08/2026**, tháng 9 chỉ có 2 bản ghi thu mua (Bà Rịa 19–20/09). `MEMBER_EDIT_WINDOW_DAYS` trên dev đang **trống ⇒ mặc định 7** ⇒ hạn chụp tuần = 11:00 Chủ nhật tuần sau.

**a) Bản lưu job dev tự chụp** (xem mục 9): Tuần 37 (07–13/09), `taken_at` 09:18:37 24/09, `deadline_at` 11:00 20/09, `taken_by=job`. So với `period_report` sống cùng kỳ: rows **khớp 100%** cả 2 biểu, totals khớp. (Tuần này dev không có số: 64 đơn vị, 0 đơn vị có số; khối 3 "đã ký HĐ chưa giao" = 47.872,002 t.)

**b) Dựng KHÔNG ghi tuần 14–20/09/2026** (0,12 s): rows + totals **khớp 100%** `period_report`.
- Thu mua: 1/64 đơn vị có số — mủ nước 81,101 t · mủ chén 0,050 t · tổng 81,151 t.
- Tiêu thụ 0 t; tồn kho: 64/64 đơn vị không có số tồn trong tuần (dev không có dữ liệu); đã ký HĐ chưa giao 47.872,002 t.

**c) Bổ sung tuần có đủ số — 17–23/08/2026** (dựng không ghi, 0,20 s), rows + totals **khớp 100%**:

| Chỉ tiêu | Σ period_report | Snapshot |
|---|---|---|
| Thu mua mủ nước / chén | 745,163 / 462,334 t | 745,163 / 462,334 t |
| Tổng thu mua (quy khô) | 1.207,498 t | 1.207,498 t |
| Thu mua thành phẩm | 203,700 t | 203,700 t |
| Tổng tiêu thụ (XK / trong nước) | 7.918,819 t (2.557,329 / 5.361,490) | như bên trái |
| Doanh thu | 461,117 tỷ đồng | 461,117 tỷ đồng |
| Tồn kho thành phẩm (chưa / đã nhập kho) | 53.680,561 t (1.270,032 / 52.410,529) | như bên trái |
| Đã ký HĐ chưa giao | 47.872,002 t | 47.872,002 t |
| Tồn nguyên liệu | 32.651,168 t | 32.651,168 t |

Ngày lấy số tồn tuần này: 18/08 (1 đv) · 20/08 (7) · 21/08 (32) · 22/08 (19) · không có (5) — minh hoạ đúng luật "ngày cuối có nhập tồn".

## 9. Lưu ý cho agent chính / chủ dự án

1. **Tồn kho trong snapshot đi theo đúng luật của Báo cáo tổng hợp**: số THỜI ĐIỂM của **ngày cuối cùng CÓ nhập tồn trong tuần** (`stock_as_of`, có thể sớm hơn Chủ nhật; đơn vị sáp nhập cộng theo pháp nhân). Chủ dự án đang được hỏi xác nhận luật này (hạng mục 4). Nếu luật đổi trong `period_report`, bản lưu MỚI tự theo luật mới; bản lưu CŨ giữ nguyên số đã chụp (đúng tinh thần bản lưu cố định).
2. **DB dev đã có 1 bản lưu do dev server tự chạy**: API 8390 `reload=True` nạp code → seed job → chạy bù lúc **09:18:37 24/09** ⇒ `vrg_caosu.unit_week_snapshot` có **1 dòng** (week_start 2026-09-07, taken_by `job`) + `meta_crawl_run` id **919** (`ok`, 1). Các lần nạp lại sau đó KHÔNG chụp thêm (đã kiểm: vẫn 1 dòng, 1 lượt chạy) — chống chụp trùng đúng. Không xoá theo chỉ đạo.
3. **Khi deploy prod lần đầu**: job chạy bù ngay sau khởi động → chụp tuần gần nhất đã qua hạn, `taken_at` trễ vài ngày so với `deadline_at` ⇒ màn hình gắn nhãn "chụp sau hạn". Đúng yêu cầu "lần đầu chỉ tuần gần nhất".
4. **Hạn phụ thuộc `MEMBER_EDIT_WINDOW_DAYS`**: prod để trống/7 thì tuần chỉ được chụp 11:00 Chủ nhật tuần sau (trễ 1 tuần so với ví dụ N=1). Muốn chụp 11:00 thứ Hai thì đặt N=1.
5. **Đổi giờ chốt** (`EDIT_CUTOFF_HOUR`) sang sau 11:10 mà không đổi giờ job ⇒ job hôm đó chưa tới hạn, lần chạy hôm sau mới chụp (trễ 1 ngày, vẫn đúng tuần). Nên chỉnh giờ job ở trang Lịch chạy theo.
6. **Giới hạn đã biết**: máy chủ tắt liên tục qua 2 mốc hạn (> 1 tuần) thì tuần ở giữa không được chụp (không chụp bù — theo yêu cầu). Admin "Chụp ngay" cũng chỉ chụp tuần gần nhất.
7. DB test `vrg_test_d` để lại (đã dọn số liệu mẫu dựng cho kiểm UI).

## Câu hỏi còn mở
- Có cần cho admin chụp bù một tuần cụ thể bị lỡ (máy chủ tắt > 1 tuần) không? Hiện theo yêu cầu: không.
- Prod đang để `MEMBER_EDIT_WINDOW_DAYS` bao nhiêu? Quyết định tuần được chụp 11:00 thứ Hai (N=1) hay 11:00 Chủ nhật tuần sau (N=7).

## Sửa sau review (24/09/2026, theo `review-item1-item5.md`)
1. **NaN/±inf không còn làm hỏng job** (Trung): `unit_week_snapshot_repo` quy mọi số không hữu hạn
   (duyệt sâu dict/list) về `null` rồi `json.dumps(allow_nan=False)` — phòng thủ độc lập với việc chặn
   NaN ở đầu vào. Một ô bẩn chỉ thành ô trống, không mất bản lưu cả tuần.
2. **Nhãn "chụp sau hạn"** chỉ gắn khi trễ QUÁ 24 giờ (`LATE_AFTER_MS`, `unit-week-snapshot-client.ts`).
   Job chạy 11:10 cố định: đổi `EDIT_CUTOFF_HOUR` lệch vài giờ không còn làm mọi tuần bị gắn nhãn.
   **Đổi giờ chốt thì chỉnh giờ 2 job `unit-week-snapshot` + `anomaly-notify` ở trang Lịch chạy**
   (ghi ở `JOB_NAME` trong `unit_week_snapshot.py`).
3. **Đơn vị chỉ có giao hàng theo hợp đồng** (không phiếu ngày) không còn bị tô mờ: `hasData` xét
   thêm mọi ô số (tiêu thụ · tồn kho …) khác 0.
4. **`due_week(ref)` không kèm múi giờ**: quy về giờ VN qua `edit_window._vn` (+ gắn múi giờ VN khi
   thiếu) — hết TypeError. Không sửa `edit_window.py`.
- Không đổi: hạn chụp vẫn dựa `member_window()` (chờ chủ dự án quyết).
- Test: thêm 2 test (NaN/inf lưu null · `ref` không múi giờ). `vrg_test_d`: 6 passed. `ruff`, `tsc` sạch.
