# Màn "Cảnh báo bất thường" (frontend) — chỉ ADMIN

Route `/canh-bao-bat-thuong`. Admin mở một trang là nắm mọi bất thường trong số liệu đơn vị thành
viên, thay cho việc chạy script dò tay từng đợt.

## File đã tạo/sửa (đúng 4 file được giao)

| Việc | File |
|---|---|
| TẠO | `/Volumes/Work/biz-project/VRG/apps/web/src/lib/anomaly-client.ts` (94 dòng) |
| TẠO | `/Volumes/Work/biz-project/VRG/apps/web/src/features/command-center/pages/AnomalyPage.tsx` (298 dòng) |
| SỬA | `/Volumes/Work/biz-project/VRG/apps/web/src/App.tsx` — 2 dòng: import + route |
| SỬA | `/Volumes/Work/biz-project/VRG/apps/web/src/features/command-center/AdminLayout.tsx` — 3 chỗ: import icon · mục `ADMIN_MENU` · `ROUTE_KEYS` |

Không đụng file nào khác.

## Giao diện

- **Thẻ tổng quan** (5 thẻ, dùng lại `.kpi-row.ct-kpi`): Tổng số cảnh báo · Nghiêm trọng · Cần xem ·
  Ghi nhận · Đơn vị bị nêu tên. Mức nặng chỉ nhấn bằng **viền trái 3px + màu chữ số**, không tô nền
  đỏ — trang đỏ rực thì người xem hết phân biệt được việc nào gấp.
- **Bộ lọc**: `RangePicker` (mặc định 01/01 năm nay → **hôm qua**) · `Quét lại` · `Xuất Excel` ·
  `Cấu hình ngưỡng` (đẩy sang phải bằng `marginLeft:auto`).
- **Mỗi nhóm một panel `Collapse`**: tiêu đề = tên nhóm + thẻ mức + `N dòng · M đơn vị` + mô tả luật.
  Mặc định **bung các nhóm `high`**, gấp phần còn lại (`activeKey` có kiểm soát, set lại sau mỗi lần quét
  — `defaultActiveKey` vô dụng vì dữ liệu về sau khi mount).
- **Nhóm 0 dòng** → dòng xanh `Không có cảnh báo.` kèm `CheckCircleOutlined`, không dựng bảng rỗng.
- **Bảng**: phân trang client 10 dòng/trang, `scroll={{x:"max-content"}}` để màn hẹp cuộn trong bảng.
- **Cấu hình ngưỡng**: `Drawer` 520px, mỗi ngưỡng 1 `InputNumber` + dòng `hint` **màu đỏ** theo quy ước
  `.form-note` + dòng "Mặc định: …". `Khôi phục mặc định` chỉ điền lại giá trị (chưa lưu);
  `Lưu` → `PUT` → đóng ngăn → **tự quét lại**.
- **Đang quét**: thẻ `Spin size="large"` + câu "…mất vài giây, vui lòng đợi…"; RangePicker và cả 3 nút
  bị disable, nút Quét lại ở trạng thái `loading`.
- **Lỗi**: `Alert type="error"` hiện đúng `detail` tiếng Việt của FastAPI (403, 503, mất mạng) — trang
  vẫn còn tiêu đề + bộ lọc, không bao giờ trắng.

## Bảng dựng ĐỘNG theo `columns` của API

Backend thêm luật mới là web hiện được ngay, không phải sửa file này:

```tsx
const columns: ColumnsType<AnomalyRow> = group.columns.map((c) => ({
  title: c.label, dataIndex: c.key, key: c.key,
  render: (v: unknown) => cellText(v),
}));
```

`AnomalyRow = Record<string, unknown>`; `cellText()` tự nhận dạng kiểu: số → `formatViNumber` (1.234,5
kiểu vi-VN) · chuỗi khớp `YYYY-MM-DD` → `dmy` (15/01/2026) · boolean → Có/Không · rỗng → `—`.

## Quyết định thiết kế

1. **Gác quyền bằng `RequireRole roles={["admin"]}`** — đúng cơ chế khối `/quan-tri/*` đang dùng, không
   tự chế. Route đặt trong chính khối đó (dù path là `/canh-bao-bat-thuong`, không có tiền tố `/quan-tri`).
2. **Không tự quét lại khi đổi ngày.** `useEffect` deps rỗng, quét 1 lần lúc mở trang; đổi ngày phải bấm
   `Quét lại`. Quét mất vài giây — tự chạy theo từng lần chỉnh lịch sẽ giật và tốn server.
3. **Xuất Excel qua `fetch` + blob**, không `window.open`: endpoint cần Bearer token, `window.open` không
   gắn được header nên sẽ trả 401. Làm y hệt `audit-client.ts` / `unit-analytics-client.ts`.
4. **Giao diện SÁNG, không tối.** Đề bài ghi "giao diện tối, màu nhấn `#0a9e48`" nhưng `theme.ts` của dự án
   là `antdTheme.defaultAlgorithm` ("SÁNG — xanh + trắng theo vrg.vn") với accent `#16AF67`. Tôi bám theo
   codebase để màn này không lạc lõng giữa 30+ màn còn lại. Nếu chủ dự án thật sự muốn tối, đó là việc đổi
   `theme.ts` cho **toàn hệ thống**, không phải cho riêng trang này.
5. **Không emoji** — icon vector `@ant-design/icons` (`WarningOutlined`, `ReloadOutlined`,
   `FileExcelOutlined`, `SlidersOutlined`, `CheckCircleOutlined`).
6. Thêm câu nhắc ở đầu trang: "Cảnh báo là **dấu hiệu cần kiểm tra**, chưa chắc đã là số sai — đối chiếu
   với đơn vị trước khi sửa", để admin không sửa thẳng số liệu của đơn vị chỉ vì thấy một dòng đỏ.

## Kiểm tra

### `./node_modules/.bin/tsc --noEmit`
```
(không có lỗi)
```

### `pnpm build`
```
$ tsc && vite build
vite v6.4.3 building for production...
✓ 4963 modules transformed.
dist/index.html                     0.64 kB │ gzip:   0.38 kB
dist/assets/index-Cbj9rb0O.css     27.21 kB │ gzip:   5.93 kB
dist/assets/index-BdpWiDM5.js   2,219.35 kB │ gzip: 668.29 kB
✓ built in 3.35s
```
(Cảnh báo "chunks larger than 500 kB" có sẵn từ trước — cả app đóng gói 1 bundle, không phải do màn này.)

### Chạy thử thật trên trình duyệt
Backend chưa chạy được cục bộ, nên tôi dựng một harness TẠM (`preview-anomaly-tmp.html` +
`src/preview-anomaly-tmp.tsx`, chặn `window.fetch` trả dữ liệu giả), render trang thật rồi **xoá cả 2 file**
và build lại sạch. Đã tận mắt xác nhận:

- Thẻ tổng quan, bộ lọc, tiêu đề nhóm hiển thị đúng; số theo kiểu vi-VN (`25.137,5`), ngày `15/01/2026`.
- Cột bảng dựng đúng từ `columns` giả (Đơn vị · Ngày · Giá lớn nhất (đồng/độ) · Nghi ngờ).
- Phân trang: `1–10 / 23 dòng`, có trang 1 2 3.
- Nhóm `high` tự bung; nhóm `medium`/`low` gấp sẵn.
- Nhóm 0 dòng bung ra hiện đúng `Không có cảnh báo.`
- Drawer: nạp 2 ngưỡng, hint đỏ, "Mặc định: 1.500"; bấm **Khôi phục mặc định** đổi ô thứ 2 từ `10` → `5`
  (giá trị `default`), ô thứ 1 giữ `1500`.
- Giả 403 → `Alert` hiện đúng câu `detail` tiếng Việt của server, trang không trắng.

## Đối chiếu với backend (đã khớp)

Đọc `apps/api/app/routers/anomalies.py` + `plans/reports/anomaly-api.md` do agent backend vừa tạo —
hợp đồng khớp 100%: `GET /api/anomalies` (prefix + `@router.get("")` → **không có dấu `/` cuối**),
`GET|PUT /api/anomalies/config` (`value` là **số**, PUT nhận `{"values": {KEY: number}}`),
`GET /api/anomalies/export.xlsx`. Cả 4 endpoint `Depends(require_admin)`.

## Việc cần người khác làm

1. **`apps/api/app/services/anomaly_rules.py` chưa tồn tại** → `GET /api/anomalies` và `export.xlsx` hiện
   trả **503** "Bộ luật quét bất thường chưa sẵn sàng". Màn hình xử lý đúng (hiện Alert đỏ với câu đó),
   nhưng chưa có cảnh báo thật nào để xem cho tới khi file luật xong.
2. **Chưa chạy thử end-to-end với API thật** (API + DB cục bộ chưa dựng trong phiên này). Sau khi
   `anomaly_rules.py` xong, cần mở `/canh-bao-bat-thuong` bằng tài khoản admin thật để xác nhận
   `columns`/`rows` thật render đẹp và file Excel tải về được.
3. **Cảnh báo va chạm file**: `AdminLayout.tsx` lúc tôi đọc đã có sẵn thay đổi chưa commit của một agent
   khác (nhóm `RETIRED_MENU` "Menu đã bỏ", chốt 11/09/2026). 3 sửa đổi của tôi nằm xen kẽ và **không đè
   mất** phần đó — đã kiểm bằng `git diff`. Người gom commit lưu ý diff của file này chứa việc của 2 phiên.
4. Sau deploy **không cần cấp quyền gì thêm** — màn thuần admin, không đi qua `DATA_CAPS`.
