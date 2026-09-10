# Báo cáo: gói kỹ năng "Đơn vị thành viên" cho Trợ lý AI

**File duy nhất tạo mới:** `apps/api/app/services/assistant_tools/unit_tools.py` (292 dòng — vượt
mốc 200 dòng khuyến nghị vì 5 tool × schema đầy đủ tiếng Việt + 1 lớp bảo vệ dữ liệu phát hiện được
khi test thật; ưu tiên đúng nghiệp vụ theo đúng chỉ dẫn).

**Không sửa file nào khác.** `__init__.py` của package đã sẵn `from ... import floor_tools,
internal_tools, market_tools, unit_tools` (do các agent song song khác phụ trách) — 3 module kia
CHƯA tồn tại tại thời điểm test nên không thể `import app.services.assistant_tools` bình thường;
đã test bằng cách nạp trực tiếp `_common.py` + `unit_tools.py` qua `importlib` (giả `sys.modules`
cho package cha) — xem script test ở cuối báo cáo.

## 5 tool đã viết

| Tool | Tham số | Reuse service |
|---|---|---|
| `get_unit_purchase` | `date_from,date_to` (mặc định 30 ngày), `material` (latex/cup/lace), `group_by` (total/region/company) | `unit_series_purchase.purchase_volume_series` (sản lượng) + `.purchase_series` (dải giá) |
| `get_unit_consumption` | `date_from,date_to`, `group_by` (total/region/company/grade) | `unit_series_consumption.consumption_series` |
| `get_unit_stock` | `as_of` (mặc định hôm nay), `group_by` (warehouse/structure/region/grade) | `unit_series_stock.stock_series` (date_from=date_to=as_of) |
| `get_unit_plan_progress` | `year`, `group_by` (region/company) | `unit_report_query.year_plan_by_group` (kế hoạch) + `unit_series_purchase`/`unit_series_consumption` (thực hiện) + `unit_daily_repo.year_plan` (đếm độ phủ) |
| `get_submission_status` | `kind` (purchase/consumption), `date_from,date_to` (mặc định 7 ngày) | `unit_report_status.status_report` |

## Output THẬT trên DB local (docker `vrg-caosu-db-1`, dữ liệu tới ~29/08/2026)

```
get_unit_purchase {} (mủ nước, 30 ngày 12/08→10/09, group_by=region)
→ tong_san_luong_tan_quy_kho: 2158.693, don_gia: min 493.6 / max 563.0 / avg 526.5 đồng/độ TSC
  (11 ngày có giá), 6 nhóm khu vực, top: Đông Nam Bộ 1458.389 tấn

get_unit_purchase {group_by: company, material: cup}
→ tong_san_luong_tan_quy_kho: 1089.038, đồng/độ DRC, 9 nhóm (đơn vị)

get_unit_purchase {group_by: total} → artifact rỗng đúng như thiết kế (chỉ số tổng), 2158.693 tấn

get_unit_consumption {} → tong_san_luong_tan: 14403.382, tong_doanh_thu_vnd: 838,274,497,300,
  canh_bao_doanh_thu: null (không có dòng thiếu tỷ giá / bất thường trong 30 ngày gần nhất)

get_unit_stock {} (as_of=hôm nay 10/09) và {as_of: 2026-08-29}
→ CẢ HAI trả lỗi "Chưa có đơn vị nào khai tồn kho ngày ... — KHÔNG lấy ảnh chụp ngày khác thay thế."
  Đã xác minh đây là ĐÚNG hiện trạng dữ liệu (không phải bug): gọi thẳng
  `unit_series_stock.stock_series` cho 18/08→05/09 thì units_counted rơi về 0 kể từ 23/08/2026
  (dữ liệu tồn kho thật của DB local dừng khai quanh 20-22/08). Test với as_of=2026-08-15 (ngày
  CÓ dữ liệu) → tong_ton_kho_tan: 63923.888, so_don_vi_co_so_lieu: 53, co_cau: {signed: 33109.16,
  free: 30814.728} — khớp 100% với gọi thẳng `stock_series('2026-08-15','2026-08-15','structure')`.

get_unit_plan_progress {} (năm 2026, group_by=region)
→ san_luong_thu_mua: kế hoạch 104330 tấn, thực hiện (YTD 01/01→10/09) 38128.72 tấn, 36.5%
→ doanh_thu: kế hoạch 1850 tỷ, thực hiện TOÀN TẬP ĐOÀN 16021.23 tỷ, 866.0% — kèm 3 dòng cảnh báo
  gộp trong `ghi_chu` (xem mục "Bẫy nghiệp vụ" bên dưới)
→ group_by=company: 15 dòng, đúng cắt top theo tên A→Z trong 15 khoá đầu (union kế hoạch ∪ thực hiện)

get_submission_status {} (purchase, 04→10/09)
→ tong_don_vi_phai_nop: 34, tong_o_thieu: 238, ty_le_da_nop_pct: 0.0 (chưa ai nộp tuần này trong
  DB local — hợp lý vì clone dừng ở cuối 08, xem mục đối chiếu)
get_submission_status {kind: consumption} → tong_don_vi_phai_nop: 65, tong_o_thieu: 455
```

Không tool nào ném exception trên dữ liệu thật (12 tổ hợp tham số đã chạy, bao gồm mọi `group_by`).

## Đối chiếu số với service gốc (bắt buộc theo tiêu chí #3)

1. **Thu mua**: gọi trực tiếp `purchase_volume_series('2026-08-12','2026-09-10','latex','region')`
   và `...,'company')` — tổng cộng dồn từ `values` của cả hai cách nhóm đều ra **2158.693 tấn**,
   khớp con số `get_unit_purchase` trả về.
2. **Tồn kho**: gọi trực tiếp `stock_series('2026-08-15','2026-08-15','structure')` →
   `{'total': 63923.888, 'units_counted': 53, 'values': {'signed': 33109.16, 'free': 30814.728}}`
   — khớp TUYỆT ĐỐI với `get_unit_stock` (từng số).
3. **Tình trạng nộp**: gọi trực tiếp `status_report('purchase','2026-09-04','2026-09-10')` →
   `totals = {'expected': 238, 'filled': 0, 'no_purchase': 0, 'missing': 238}`, `len(rows)=34` —
   khớp `tong_don_vi_phai_nop=34`, `tong_o_thieu=238`, `ty_le_da_nop_pct=0.0`.

## Bẫy nghiệp vụ đã xử lý

1. **`total`/`region`/`company`/`grade` không có trong `GROUPS` gốc của `purchase_volume_series`/
   `consumption_series`** (chúng chỉ nhận region/company hoặc region/company/grade/contract/channel)
   → khi tool nhận `group_by=total`, gọi service với `region` làm proxy rồi CHỈ lấy tổng, bỏ qua
   breakdown (artifact=None, top_nhom=None) — không tự chế thêm nhánh code trong service gốc.
2. **Giá thu mua không chia theo nhóm được** (`purchase_series` chỉ có dải giá mức Tập đoàn) →
   tách riêng lời gọi giá (luôn ở mức Tập đoàn) khỏi lời gọi sản lượng (chia theo `group_by`), nói
   rõ trong response thay vì áp giá Tập đoàn cho từng khu vực.
3. **`revenue_missing_lines`** (dòng bán USD thiếu tỷ giá) — không bỏ qua lặng lẽ, gộp vào
   `canh_bao_doanh_thu`/`ghi_chu` của từng tool đúng yêu cầu đề bài.
4. **`units_counted` của tồn kho luôn xuất hiện trong summary** (không chỉ khi thấp) — tránh người
   đọc tưởng cột thấp là bán được nhiều trong khi thực ra là thiếu đơn vị nhập.
5. **Không carry-forward**: `get_unit_stock` trả lỗi rõ ràng khi `units_counted=0` ở đúng ngày hỏi,
   không tự động lùi ngày lấy ảnh chụp gần nhất (khác hẳn cách UI `stock_report` vẫn cho lùi —
   nhưng đây là tool cho LLM tư vấn nên bám sát luật cứng "thiếu thì báo thiếu").
6. **Sáp nhập đơn vị**: mọi số đều đi qua `unit_series_*`/`unit_report_status`/`unit_report_query`
   — các hàm này đã tự xử lý gộp/tách sáp nhập (`member_unit_merge`), tool không tự cộng theo tên
   công ty nên không có rủi ro đếm trùng.
7. **`year_plan_by_group` không có tuỳ chọn `group_by=total`** → khi cần tổng Tập đoàn dùng thẳng
   giá trị `total` thứ hai của tuple trả về, không tính lại bằng `sum(dict.values())` (khác nhau khi
   có group không rơi vào `PLAN_DIMS`).

## Phát hiện được khi test thật (đã tự xử lý trong file, KHÔNG sửa được ở file khác)

### Bug dữ liệu: 3 dòng doanh thu sai ĐƠN VỊ TÍNH giá bán (~10⁶ lần)

Khi test `get_unit_plan_progress` với khoảng ngày cả năm (01/01→10/09/2026), tổng doanh thu ban đầu
ra **24.801.275,97 TỶ đồng** (vô lý — lớn hơn GDP Việt Nam nhiều lần) → `pct_thuc_hien` = 1.340.609%.
Truy ngược bằng `unit_report_rows.consumption_rows` phát hiện 3 dòng giao hàng của
**Công ty TNHH MTV Cao su Hà Tĩnh** có `price` lưu theo **đồng/tấn thay vì triệu đồng/tấn**
(quy ước hệ thống ở `line_revenue_vnd`: VNĐ thì nhân thêm `TRIEU`=1.000.000):

| Ngày (`as_of`) | Mã HĐ | qty (tấn) | price lưu (sai, đang là đ/tấn) | Doanh thu tính sai |
|---|---|---|---|---|
| 2026-01-27 | 34 | 56.0 | 46.300.000 | 2.592.800.000.000.000 |
| 2026-01-30 (invoice 23/03) | 1812-02 | 199.99 | 47.550.000 | 9.509.524.500.000.000 |
| 2026-03-24 (invoice 07/05) | 01 | 249.9 | 50.750.000 | 12.682.425.000.000.000 |

Giá đúng nhiều khả năng là `price/1.000.000` (≈ 46,3 / 47,55 / 50,75 triệu đ/tấn — đúng dải giá
SVR10 nội địa hợp lý). **Đây là lỗi DỮ LIỆU trong bảng lưu chi tiết hợp đồng bán (nguồn của
`unit_report_rows.consumption_rows`), không phải lỗi code** — ngoài phạm vi file tôi được giao, và
CHƯA rõ prod có dính lỗi tương tự hay không (local DB clone tới ~29/08 nên 3 dòng này tồn tại sẵn
trên prod tại thời điểm clone).

**Cách tôi xử lý trong `unit_tools.py`** (không sửa DB, không đoán số đúng thay người nhập):
- Thêm hằng `REVENUE_SANITY_VND_PER_DAY = 5.000 tỷ/ngày` (gấp ~30 lần ngày cao điểm thật đo được
  ~170 tỷ) và hàm `_safe_revenue()` — LOẠI các ngày vượt trần khỏi tổng doanh thu, đồng thời liệt kê
  đúng ngày bị loại vào `canh_bao_doanh_thu`/`ghi_chu` để người dùng biết mà kiểm tra, không im lặng
  bỏ qua. Áp dụng ở cả `get_unit_consumption` và `get_unit_plan_progress`.
- Sau khi lọc, doanh thu thực hiện 01/01→10/09/2026 còn **16.021,23 tỷ đồng** (hợp lý hơn nhiều,
  dù vẫn cần đối chiếu thêm — xem mục dưới).

→ **Đã dùng `spawn_task` để báo việc sửa dữ liệu này cho một phiên riêng** (không tự sửa vì ngoài
phạm vi file được giao và vì sửa DB cần xác nhận giá đúng với đơn vị Hà Tĩnh trước).

### Nghi vấn thứ hai: mẫu số kế hoạch doanh thu quá hẹp

`plan_revenue_ty` (kế hoạch doanh thu năm, đơn vị TỶ ĐỒNG) hiện **chỉ 1/65 đơn vị đã khai** (1.850
tỷ đồng, kiểm bằng `unit_daily_repo.year_plan(2026)` trực tiếp) trong khi doanh thu thực hiện lấy
TOÀN TẬP ĐOÀN (mọi đơn vị, mọi hợp đồng) — nên `% thực hiện doanh thu` (866% sau khi đã lọc bug ở
trên) **không phản ánh đúng ý nghĩa "kế hoạch vs thực hiện"**, chỉ là do hầu hết đơn vị chưa nhập
kế hoạch. Đã thêm cảnh báo tự động trong `ghi_chu` khi `n_rev_plan < n_units_total`: *"Chỉ x/y đơn vị
đã khai kế hoạch doanh thu năm — % thực hiện doanh thu vì vậy CHƯA đại diện, đừng dùng để kết luận."*
Đây là vấn đề nghiệp vụ (đơn vị chưa nhập số) chứ không phải lỗi code — không có gì để sửa ở file
khác ngoài việc đôn đốc đơn vị nhập liệu (có thể dùng skill `bao-cao-nhap-lieu` sẵn có).

## Nghi ngờ còn lại / việc cần người khác xác nhận

1. **Xác nhận trên PROD** xem 3 dòng Hà Tĩnh ở trên có tồn tại y hệt không (local chỉ là clone tới
   29/08/2026) — nếu có, cần sửa `price` trực tiếp trong DB (chia lại 1.000.000) sau khi xác nhận số
   đúng với đơn vị, hoặc bổ sung validate ở tầng nhập liệu (form Tiêu thụ) để chặn giá bán VNĐ ghi
   theo đồng/tấn thay vì triệu đ/tấn — đây là việc sửa Ở FILE KHÁC (`unit_daily` frontend/schema
   hoặc DB), ngoài phạm vi file tôi được giao.
2. **`get_unit_stock`/`get_submission_status`** trả "chưa có số liệu"/"0% đã nộp" cho các ngày cuối
   (từ ~21-23/08/2026 trở đi) — vì DB LOCAL dừng khai ở đó, KHÔNG phải bug; khi test trên môi trường
   có dữ liệu mới hơn (staging/prod) các tool này sẽ tự trả số thật của ngày đó.
3. Tôi không đụng `assistant_tools/__init__.py` dù nó đã sẵn dòng import `unit_tools` — khi
   `floor_tools.py`/`internal_tools.py`/`market_tools.py` của các agent song song xong, việc
   `import app.services.assistant_tools` (package thật) sẽ tự chạy được, không cần thao tác gì
   thêm từ phía `unit_tools.py`.

## Cách tôi test (để người khác tái tạo)

Không thể `import app.services.assistant_tools` bình thường lúc viết báo cáo này (thiếu 3 module
song song). Đã tạo package giả trong `sys.modules` rồi nạp `_common.py` + `unit_tools.py` bằng
`importlib.util.spec_from_file_location` — script mẫu:

```python
import importlib.util, sys, types
ROOT, PKG = "/Volumes/Work/biz-project/VRG/apps/api", "app.services.assistant_tools"
pkg = types.ModuleType(PKG); pkg.__path__ = [f"{ROOT}/app/services/assistant_tools"]
sys.modules[PKG] = pkg
def load(name, path):
    spec = importlib.util.spec_from_file_location(f"{PKG}.{name}", path)
    mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod
    spec.loader.exec_module(mod); return mod
load("_common", f"{ROOT}/app/services/assistant_tools/_common.py")
t = load("unit_tools", f"{ROOT}/app/services/assistant_tools/unit_tools.py")
# t.TOOLS["get_unit_purchase"]["run"]({...})
```

Chạy bằng: `cd apps/api && PYTHONPATH=$(pwd) uv run python <script trên>`.
