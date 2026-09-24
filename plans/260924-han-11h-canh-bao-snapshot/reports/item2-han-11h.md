# Hạng mục 2 — Cửa sổ nhập liệu theo GIỜ CHỐT 11:00

**Luật mới:** số liệu ngày D nhập/sửa được đến **giờ chốt (mặc định 11:00, giờ VN) của ngày D + N**.
N = `MEMBER_EDIT_WINDOW_DAYS` (đơn vị) / `EDITOR_EDIT_WINDOW_DAYS` (chuyên viên); admin miễn.
Áp CHUNG mọi mục (Thu mua · Tiêu thụ – Tồn kho · giá mủ · nhu cầu thị trường · ngày giao HĐ ·
Giá mủ NL · Physical · Tồn kho tuần · Báo giá). Đã bỏ hẳn `STOCK_EXTRA_WINDOW_DAYS` /
`PURCHASE_EXTRA_WINDOW_DAYS`; thêm `EDIT_CUTOFF_HOUR` (0–23, rỗng/sai → 11).

## Hành vi (N = số ngày cấu hình)

| N | Trước 11:00 hôm nay (T) | Từ 11:00 hôm nay |
|---|---|---|
| 0 | nhập được T | **khoá cả T** (`editable_from` = T+1) |
| 1 | nhập được T-1, T | chỉ T |
| 7 | T-7 … T | T-6 … T |

Ngày tương lai luôn 400. Quá hạn → 403 + header `X-Edit-Blocked: window` (web mời gửi Đề nghị sửa),
câu báo: "…chỉ được nhập/sửa đến 11:00 ngày hôm sau." (0 → "cùng ngày", N≥2 → "đến 11:00, N ngày sau ngày số liệu" — xem mục Sửa sau review).

## File sửa (phần của agent B)

Backend
- `app/core/edit_window.py` — thêm `_vn()`: `ref` có múi giờ khác được đổi về giờ VN (agent C/D gọi
  `editable_from(window, ref)` an toàn); chữ ký `cutoff_hour/deadline/editable_from/is_editable/member_window` giữ nguyên.
- `app/routers/settings.py` — `/api/settings/edit-windows` trả thêm `member_editable_from`,
  `editor_editable_from`, `cutoff_hour`.
- `app/routers/market_demand.py` — trả kèm `editable_from`.
- `app/services/member_checklist.py`, `app/routers/member_self.py` — sửa docstring/comment còn nói "nhập trễ hơn".
- Rà toàn `app/`: mọi hàng rào đều đi qua `edit_window.assert_editable` (security.assert_edit_window /
  assert_editor_window, edit_request_ops_*, sales_contract_lock, market_demand_item_policy) → không còn
  chỗ tự tính `(today - d).days > window`.

Web
- `lib/edit-window.ts` viết lại: `windowPhrase(days, hour)` khớp server, `windowRule()`, `inWindow()`,
  `windowDatesOf()` (có thể rỗng), `useCutoffHour()`; hook dùng `*_editable_from` của server, cache 60 s,
  tải lại khi quay lại tab (trang để mở qua 11:00). Trả thêm `phrase`, `editableFrom`, `cutoffHour`.
- `lib/settings-client.ts`, `member-client.ts` (bỏ `purchase/stock_editable_from`), `unit-daily-client.ts`,
  `market-demand-client.ts` — thêm `editable_from`.
- `UnitDailyEditModal`, `UnitDailyTimeline`, `UnitDailyMoveDateModal`, `MarketDemandTimelinePage`,
  `MemberChecklistBanner` (1 mốc chung + câu "Số liệu mỗi ngày nhập/sửa đến 11:00 ngày hôm sau"),
  `RawMaterialPage`, `PhysicalSheetPage`, `InventoryPage`, `MarketQuotePage` — bỏ `daysBetween`, khoá theo
  `editable_from`, chữ báo "đã quá hạn nhập — … đến 11:00 …". Màn hợp đồng dùng `useEditWindow` tự đúng.

Tests
- Mới `tests/edit_window_clock.py` (`pin_clock`), `tests/test_edit_window_cutoff.py` (test thuần:
  deadline, editable_from trước/sau 11:00 với N=0/1/7, múi giờ, đổi giờ chốt, câu báo, header 403).
- `tests/test_edit_window.py` thêm 3 test API: N=0 khoá hôm nay lúc 11:00 (đơn vị + chuyên viên, admin
  miễn, `editable_from` > hôm nay), N=1 giữ hôm qua tới 11:00, đổi `EDIT_CUTOFF_HOUR`=15.
- `tests/test_unit_daily.py`: thay `test_daily_forms_get_extra_days_over_the_other_forms` bằng
  `test_every_daily_form_shares_the_cutoff_deadline` (6 đường ghi, 10:59 vs 11:00).
- Ghim giờ sáng cho fixture đặt cửa sổ 0 rồi ghi "hôm nay" (`test_market_demand.md`,
  `test_sales_contract_completion_fences.env`) — không ghim thì xanh buổi sáng, đỏ buổi chiều.

Tài liệu người dùng (README + spec.json, bản Word dựng lại bằng `build_guide.js`)
- `quan-tri-he-thong`: bỏ đoạn 2 ô "nhập trễ hơn"; thêm luật giờ chốt + ô "Giờ chốt nhập liệu".
- `nhap-lieu-don-vi-thanh-vien`, `nhap-lieu-bang-excel`, `de-nghi-sua-so-lieu`: câu "hôm nay và một số
  ngày gần nhất" → "đến 11:00 theo hạn quy định (vd đến 11:00 ngày hôm sau)".
- Ảnh chụp KHÔNG chụp lại: ảnh tab "Cửa sổ nhập liệu" ở sổ tay quản trị có thể còn hiện 2 ô cũ.

## Lưu ý khi deploy
- Prod đang: đơn vị N = 0, 2 ô EXTRA = 1 (⇒ Thu mua/Tồn kho thực tế hết ngày hôm sau). Sau deploy 2 ô
  EXTRA bị bỏ qua ⇒ **đơn vị sẽ chỉ nhập được tới 11:00 cùng ngày** cho tới khi chủ dự án đặt
  `MEMBER_EDIT_WINDOW_DAYS = 1` (→ 11:00 ngày hôm sau). Nên đặt ngay sau deploy.
- Chuyên viên đang 7 (+1 cho 2 biểu) → nay 7 chung, hạn 11:00 ngày thứ 7 (mất ~1,5 ngày ở 2 biểu so với trước).
- Dòng `STOCK_EXTRA_WINDOW_DAYS` / `PURCHASE_EXTRA_WINDOW_DAYS` còn nằm trong bảng `app_config` prod —
  vô hại (không còn trong CONFIG_SPEC); xoá tay nếu muốn gọn.
- `docs/project/project-changelog.md` còn nhắc 2 ô cũ (lịch sử) — main agent thêm entry mới.

## Kết quả kiểm tra (DB riêng `vrg_test_b`)
- Test cửa sổ (edit_window, edit_window_cutoff, unit_daily, member_checklist, edit_request*,
  sales_contract*, market_demand*, data_lock…): 184 + 17 xanh.
- Cả bộ `pytest -q`: 637 xanh · 1 đỏ · 6 bỏ qua. Test đỏ (`test_purchase_auto_sync::test_master_switch_off…`)
  do chính tôi chạy song song test giờ chốt trên cùng DB (đặt tạm N = 0) — chạy lại riêng: 13/13 xanh.
- Cả bộ chạy lại với đồng hồ giả **14:00** (mô phỏng chạy sau giờ chốt, plugin tạm ở scratchpad):
  **644 xanh · 0 đỏ** ⇒ bộ test không còn phụ thuộc giờ chạy.
- `ruff` sạch ở file đã sửa. Web `tsc --noEmit`: sạch toàn bộ (exit 0, lần kiểm cuối).
- Chưa kiểm trên trình duyệt (Browser pane bị từ chối). Đã gọi thử dev API: `/api/settings/edit-windows`
  trả đủ `member_editable_from`/`editor_editable_from`/`cutoff_hour`.

## Sửa sau review (`review-item2.md`)

| # review | Sửa |
|---|---|
| 1 | Câu N ≥ 2 → "đến 11:00, **7 ngày sau** ngày số liệu" (bỏ "ngày thứ 7" = thứ Bảy) ở `edit_window.window_phrase` + web `windowPhrase`; câu 403 gom về `edit_window.blocked_message()`. Sổ tay/spec không có câu cũ → không dựng lại .docx. |
| 2 | `public_purchase.submit`: thêm `assert_editable(hôm nay, member_window())` + `data_lock.assert_not_locked` (cùng hàng rào `PUT /api/member/prices`); `/auth` trả `closed` (câu chặn khi đã qua giờ chốt). Trang `/nhap-gia-mu` hiện Alert cố định + khoá ô/nút khi `closed` hoặc khi gửi bị 403 (client ném `PublicHttpError` kèm mã). |
| 3 | Ghi Excel không qua cửa sổ — file của F1 (`member_self.py`, `unit_daily.py`), không sửa ở đây. |
| 4 | `/api/settings/edit-windows` trả thêm `next_change_at` (giờ chốt kế tiếp, ISO +07:00) + `now`; hook `useEditWindows` hẹn `setTimeout` tới mốc đó (+2 s, tính bằng hiệu 2 mốc giờ server nên không lệch theo đồng hồ máy), bỏ cache cũ hơn mốc, dọn timer khi unmount. Màn có `editable_from` riêng trong payload (Timeline · Nhu cầu TT · Checklist) CHƯA tự tải lại — ngoài phạm vi. |
| 5 | `_parse` chặn trần `MAX_DAYS = 3650` (N, số ngày rà cảnh báo) → hết `OverflowError`/500. `_vn` nay luôn trả mốc kèm múi giờ (mốc không múi giờ gắn giờ VN). |
| 6 | Không chặn giờ chốt = 0 (theo chỉ đạo). |
| 7 | `tests/conftest.py` thêm fixture phiên `_explicit_edit_window` (N = 7 · 7, giờ chốt 11, trả lại cấu hình DB cuối phiên) — phủ cả 3 file `test_purchase_*`/`test_zero_purchase_price` lẫn các test khác trong `test_unit_daily.py` cũng ghi "hôm nay/hôm qua". Helper `window_config()` / `restored_window_config()` trong `tests/edit_window_clock.py`; `test_edit_window.py` + đoạn `test_every_daily_form_shares_the_cutoff_deadline` đặt giờ chốt tường minh và trả lại cấu hình cũ. Test mới `tests/test_public_purchase_window.py`, `test_edit_window_cutoff.py` (+câu, trần N, mốc kế tiếp). |
| 8 | Nhãn `MEMBER_/EDITOR_EDIT_WINDOW_DAYS` → "Số ngày được nhập trễ (N) — …", placeholder giải thích N = 0 / 1 theo giờ chốt. |

Kiểm (DB `vrg_test_b`, cấu hình DB đặt lần lượt N = 0 · 1 · 7 và giờ chốt 15, đồng hồ giả 09:00 và 14:00 qua
plugin tạm ở scratchpad): bộ test cửa sổ/giá mủ/link công khai/unit_daily **65 xanh ở cả 8 tổ hợp**, cấu hình
DB sau mỗi lượt y nguyên. Trước khi thêm fixture phiên: N = 0 lúc 14:00 đỏ 7 test `test_unit_daily`.
Cả bộ `pytest tests` với DB N = 0 + đồng hồ 14:00: **668 xanh · 0 đỏ · 6 bỏ qua**; plugin theo dõi cấu hình
xác nhận không test nào để lại N/giờ chốt khác (chỉ fixture phiên đặt đầu phiên, trả lại cuối phiên).
⚠ Hai phiên pytest chạy SONG SONG trên cùng một DB sẽ giẫm cấu hình của nhau — mỗi agent một DB.
`test_unit_daily::test_year_plan_put_keeps_unsent_keys_and_rejects_nan` (test mới của F1) đỏ lúc F1 đang làm
dở nên loại khỏi lượt ma trận; lượt cả bộ sau đó đã xanh. `ruff` + `tsc --noEmit` sạch.
