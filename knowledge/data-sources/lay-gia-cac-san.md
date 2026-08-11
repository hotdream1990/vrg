---
title: Cách lấy giá tham chiếu các sàn & giá physical
type: data-source
tags: [sgx, sicom, shfe, tocom, jpx, lgm, anrpc, rss3, tsr20, latex]
source: docs/bieu-mau/Tâm/Các Web và hướng dẫn lấy giá báo cáo bản tin thị trường ngày.docx
updated: 2026-08-11
---

# Cách lấy giá các sàn (số hóa từ quy trình chuyên viên Tâm)

> Đây là tri thức nghiệp vụ thủ công hiện tại — dùng làm spec cho `services/crawlers/`.
> Quy ước chung: lấy giá của **ngày trước ngày hiện tại 01 ngày**.

## Nguyên tắc chung: ĐÚNG NGÀY, không đắp giá phiên cũ
Mỗi giá phải là giá của **đúng phiên ngày đó**. Ngày sàn nghỉ / không ra settlement thì
ghi **giá 0 = No Trading** (báo cáo in chữ "No Trading"), tuyệt đối không lấy giá phiên
trước đóng dấu sang ngày mới. Vì vậy mọi nguồn đều phải là **báo cáo theo phiên** (mỗi
phiên 1 file, ngày nghỉ không có file) chứ không phải bảng giá "live" — bảng giá live
thường đổi ngày trước khi có settlement mới.

## JPX / TOCOM (Nhật) — RSS3
- Web: `https://www.jpx.co.jp/english/markets/statistics-derivatives/daily/index.html`
- File `cdf_dyr` trang 12 → lấy **RSS3** tại vị trí có **Trading Value lớn nhất**
  (thường cách ~5 tháng so với hiện tại) → lấy giá **Settlement Price**.
- **Không kỳ hạn nào có Trading Value** → giá 0 (No Trading). Không lấy settlement lý thuyết
  của kỳ hạn đầu: JPX giữ nguyên số đó nhiều phiên liền (vd OSE TSR20 đứng im 350 JPY/kg).

## SHFE (Thượng Hải) — Natural Rubber
- Web: `https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/`
- Statistical → ngày (trước 01 ngày) → Future → Daily express → All: Natural rubber →
  chọn **Volume lớn nhất** (thường cách ~3 tháng) → lấy giá tại **Settle**.

## SGX / SICOM (Singapore) — RSS3 & TSR20
- Nguồn (từ 11/08/2026): **báo cáo Daily Futures theo phiên** —
  `https://links.sgx.com/1.0.0/derivatives-daily/{id}/FUTURE.zip` → `MMDDFUT.csv`
  (`DATE,COM,COM_MM,COM_YY,OPEN,HIGH,LOW,CLOSE,SETTLE,VOLUME,OINT,SERIES`).
  `id` tăng 1 sau mỗi phiên (ngày nghỉ không có id) → dò id rồi **đối chiếu cột DATE**.
- **Mã hợp đồng**: RSS3 = `RT`, TSR20 = `TF`.
- **Chọn kỳ hạn = giao THÁNG SAU** (next month) so với **ngày của phiên** — vd phiên 07/08/2026
  → hợp đồng giao **2026-09**.
- **Giá lấy**: cột `SETTLE` (US cents/kg). `SETTLE = 0` = sàn không ra settlement cho cao su
  phiên đó → **lưu 0 = No Trading** (vd phiên 10/08/2026).
- ⚠ **Không dùng API live** `api.sgx.com/derivatives/v1.0/contract-code/{TF|RT}`: field
  `base-date` của API nhảy sang phiên mới **trước khi** có settlement mới, và nhảy cả vào ngày
  sàn không ra settlement → settlement phiên cũ bị đóng dấu sang ngày sau. Thực tế 10–11/08/2026
  giá 273,9 của phiên 07/08 bị ghi cho cả hai ngày.

## LGM (Malaysia) — Physical FOB
- Web: `https://www.lgm.gov.my/webv2/sidenav/(mreDetails:mreprice)` → reference prices (FOB) → chọn ngày (trước 01 ngày).
- **SMR CV**, **SMR20**: lấy theo **US Cents/Kg**.
- **Latex in Bulk** (Centrifuged Latex, ISO 2004, 60% DRC, Sen/Kg): `giá / tỷ giá × 10`.

## Tỷ giá & nguồn bổ trợ
- USD/CNY: `https://www.exchangerates.org.uk/Dollars-to-Yuan-currency-conversion-page.html`
- USD/THB: `https://www.exchangerates.org.uk/Dollars-to-Baht-currency-conversion-page.html`
- BNM (Malaysia): `https://www.bnm.gov.my/exchange-rates`
- ANRPC Daily Price: `https://www.anrpc.org/anrpc-daily-price`
- Asian physical rubber: `https://www.marketscreener.com/search/?q=Asian+physical+rubber+prices`

## Lưu ý số hóa
Logic "chọn kỳ hạn có Volume/Trading Value lớn nhất" là **kinh nghiệm chuyên viên** — cần
tham số hóa trong crawler (đừng hardcode số tháng), vì khoảng cách kỳ hạn thay đổi theo thời điểm.
