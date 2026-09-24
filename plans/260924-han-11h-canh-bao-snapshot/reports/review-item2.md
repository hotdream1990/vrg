# Review Hạng mục 2 — Cửa sổ nhập liệu theo giờ chốt 11:00

**Phạm vi:** thay đổi chưa commit của `core/edit_window.py`, `security.py`, các router `member_self · unit_daily · prices ·
settings · market_demand · inventory · market_quote · sales_contracts · public_purchase`, service `member_checklist ·
member_data_check · edit_request_ops_* · sales_contract_lock · market_demand_item_policy · config_repo`, web
`lib/edit-window.ts` + các màn dùng, test cửa sổ, sổ tay `docs/huong-dan/*/README.md`.

**Đã tự kiểm:** đọc code + grep toàn `app/` · `pytest tests/test_edit_window_cutoff.py` **13 passed** (chạy với
`DATABASE_URL` trỏ cổng chết để conftest KHÔNG chạm DB dev) · `tsc --noEmit` web **sạch** · `ruff` file đã sửa **sạch** ·
chạy thử `edit_window` bằng script thuần (ranh giới giây, múi giờ, N lớn, giờ chốt 0) · đọc `app_config` DB dev bằng 1
câu SELECT (MEMBER trống ⇒ 7, EDITOR 7). KHÔNG chạy test cần DB.

## Phát hiện

| # | Mức | Vị trí | Kịch bản lỗi | Đề xuất |
|---|---|---|---|---|
| 1 | **Trung** | `app/core/edit_window.py:129` · `web/src/lib/edit-window.ts:30` · placeholder `config_repo.py:74` | Câu báo khi N ≥ 2 là "đến 11:00 **ngày thứ 7** sau ngày số liệu". Trong tiếng Việt "ngày thứ 7" = **thứ Bảy**; N = 2…6 đọc thành thứ Hai…thứ Sáu. Mặc định N = 7 (chuyên viên trên prod đang là 7) nên câu này hiện thật: chuyên viên hiểu "tới 11h thứ Bảy tuần sau". | Đổi thành "đến 11:00, **7 ngày sau** ngày số liệu" (hoặc "đến 11:00 ngày D + 7"). Sửa đồng thời server, web, placeholder và test `test_window_phrase_names_the_cutoff`. |
| 2 | **Trung** | `app/routers/public_purchase.py:41-55` | Link công khai `/nhap-gia-mu` ghi giá mủ nước lớp `vrg_unit` cho **hôm nay**, không qua `assert_editable` (và cả `data_lock`). Với N = 0, sau 11:00 tài khoản đơn vị đăng nhập bị 403 "đến 11:00 cùng ngày", nhưng link công khai vẫn ghi được giá hôm nay ⇒ lách luật giờ chốt cho mục "giá mủ". Trước đây hôm nay luôn nằm trong cửa sổ nên chưa lệch; lệch này do luật mới sinh ra. | Trong `submit` gọi `edit_window.assert_editable(today, edit_window.member_window())` (+ `data_lock.assert_not_locked`); trang công khai hiện câu `window_phrase` khi 403. |
| 3 | Thấp | `routers/member_self.py:427-434` · `routers/unit_daily.py:375-378` · sổ tay `nhap-lieu-bang-excel/README.md:139` | Ghi Excel (`/import/commit`) KHÔNG kiểm cửa sổ: đơn vị chỉ qua `data_lock`, chuyên viên không qua gì; `rows` do client gửi nên ghi được ngày quá hạn bất kỳ. Hiện đang tắt (`EXCEL_IMPORT_ENABLED = False` → 503) nên chưa khai thác được, nhưng sổ tay vừa sửa lại khẳng định "ngày đã quá hạn hệ thống sẽ từ chối ghi" — sai ngay khi bật lại. | Trong vòng lặp commit: gọi `assert_editable(as_of, member_window())` cho đơn vị / `assert_editor_window` cho chuyên viên (hoặc đánh lỗi từng dòng ở bước xem trước). |
| 4 | Thấp | `web/src/lib/edit-window.ts:52-75` và payload `editable_from` của Timeline · DemandList · Checklist | Chỉ tải lại khi tab chuyển sang hiện (`visibilitychange`), cache 60 giây. Người nhập để tab mở suốt qua 11:00 (hay gặp) thì lưới Giá mủ NL/Physical vẫn mở ô, Báo giá vẫn tự lưu, chip checklist vẫn màu cam ⇒ gõ xong mới nhận 403. Server vẫn chặn nên không hỏng dữ liệu, chỉ là trải nghiệm. | Server trả thêm `next_cutoff_at`; web đặt `setTimeout` tới mốc đó để tải lại (hook + các màn có payload riêng), hoặc tải lại khi cửa sổ lấy lại focus. |
| 5 | Thấp | `app/core/edit_window.py:51-57,102` | `n.date() - timedelta(days=window)` ném `OverflowError` khi N ≥ ~739.000 (admin gõ "9999999" để hiểu là "không giới hạn") ⇒ **mọi** đường ghi + `/api/settings/edit-windows` + checklist trả 500. Bản cũ `assert_editable` so số nguyên nên không bị. Đã tái hiện bằng script. | Chặn trần trong `_parse`, vd `min(n, 3650)`. |
| 6 | Thấp | `app/core/edit_window.py:79` | `EDIT_CUTOFF_HOUR = 0` hợp lệ (0–23). Khi đó N = 0 ⇒ `editable_from` luôn là ngày mai: không ai ngoài admin nhập được, câu báo "đến 00:00 cùng ngày". Đã tái hiện bằng script. | Cho phép 1–23, hoặc coi 0 là 24:00 (hết ngày); ghi rõ trong placeholder. |
| 7 | Thấp | `tests/test_purchase_price_layers.py:26,58` · `test_zero_purchase_price.py:29,59` · `test_purchase_auto_sync.py:25,60`; `test_edit_window.py:64` · `test_unit_daily.py:299` | Các test ghi "hôm qua" qua `/api/member/prices` mà không đặt `MEMBER_EDIT_WINDOW_DAYS`/ghim giờ. Trước đây có `PURCHASE_EXTRA` (mặc định +1) che. DB dev (N trống ⇒ 7) vẫn xanh, nhưng DB bản sao prod (N = 0 hiện tại) ⇒ đỏ cả ngày; khi prod đặt N = 1 như khuyến nghị ⇒ **xanh sáng, đỏ sau 11:00**. Hai test kia khẳng định `cutoff_hour == 11`, đỏ nếu DB đã cấu hình giờ chốt khác. | Thêm fixture autouse (conftest) đặt cố định `MEMBER/EDITOR_EDIT_WINDOW_DAYS` + `EDIT_CUTOFF_HOUR` về mặc định, trả lại sau phiên; hoặc từng fixture tự đặt và gọi `pin_clock`. |
| 8 | Thấp | `config_repo.py:69,73` | Nhãn vẫn là "Số ngày sửa được…" trong khi N = 0 vẫn sửa được hôm nay tới 11:00 ⇒ admin dễ hiểu 0 = "không được sửa ngày nào". | Đổi nhãn thành "Hạn nhập: số ngày sau ngày số liệu (tính tới giờ chốt)…". |

## Đã kiểm, không có lỗi
- Grep toàn `app/`: không còn chỗ tự tính `(today - d).days > window`, không còn lời gọi `member_window(kind)`/`editor_window(kind)`
  hay khoá `*_EXTRA_*`. Mọi đường ghi của đơn vị/chuyên viên (member_self, unit_daily, prices, inventory, market_quote,
  market_demand policy, sales_contract_lock, edit_request_ops_daily/demand/contract) đều qua `assert_editable`. Các chỗ
  miễn (`inventory /auto/*`, `delivery-type`, `stock-contracts` cũ, kế hoạch năm) đều cố ý, có từ trước.
- Ranh giới: 10:59:59.999999 còn mở, 11:00:00 khoá; `ref` có múi giờ khác được đổi về giờ VN; `ref` không múi giờ coi là
  giờ VN; ngày tương lai → 400 (không kèm header, nên luồng Đề nghị sửa không nuốt nhầm).
- `windowDates` rỗng (N = 0 sau 11:00): Giá mủ NL/Physical ghép với ngày có dữ liệu nên lưới không vỡ; không màn nào đọc
  `windowDates[0]`.
- Mốc hiển thị thống nhất: chip checklist, `editable` của ô kiểm tra/thiếu tỷ giá, Timeline/Modal/Đổi ngày, Nhu cầu thị
  trường, hợp đồng (`useEditWindow` ↔ `security.assert_edit_window` theo vai trò) cùng lấy `editable_from` do server tính.
- `pin_clock` ghim `edit_window.now` (kéo theo `today()`); các test giờ chốt đã ghim giờ nên không phụ thuộc giờ chạy.

## Ngoài phạm vi (ghi để agent khác xử lý)
- `services/unit_week_snapshot.py:55-58` (hạng mục 5): `due_week(ref)` so `deadline()` (có múi giờ) với `ref` mà không
  qua `_vn` ⇒ truyền `ref` không múi giờ sẽ `TypeError`. Hiện chưa có chỗ gọi như vậy.

## Câu hỏi còn mở
- Prod đang để đơn vị N = 0 (theo báo cáo item2, tôi chưa tự kiểm): deploy xong mà chưa đặt N = 1 ngay thì đơn vị chỉ
  nhập được tới 11:00 cùng ngày, kể cả tồn cuối ngày. Có muốn migration tự nâng N = 0 → 1 lúc khởi động không?
- Link công khai `/nhap-gia-mu` trên prod còn dùng không? Nếu đã bỏ thì phát hiện #2 hạ xuống Thấp.
