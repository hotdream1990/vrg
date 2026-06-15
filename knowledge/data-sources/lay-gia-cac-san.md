---
title: Cách lấy giá tham chiếu các sàn & giá physical
type: data-source
tags: [sgx, sicom, shfe, tocom, jpx, lgm, anrpc, rss3, tsr20, latex]
source: docs/bieu-mau/Tâm/Các Web và hướng dẫn lấy giá báo cáo bản tin thị trường ngày.docx
updated: 2026-06-15
---

# Cách lấy giá các sàn (số hóa từ quy trình chuyên viên Tâm)

> Đây là tri thức nghiệp vụ thủ công hiện tại — dùng làm spec cho `services/crawlers/`.
> Quy ước chung: lấy giá của **ngày trước ngày hiện tại 01 ngày**.

## JPX / TOCOM (Nhật) — RSS3
- Web: `https://www.jpx.co.jp/english/markets/statistics-derivatives/daily/index.html`
- File `cdf_dyr` trang 12 → lấy **RSS3** tại vị trí có **Trading Value lớn nhất**
  (thường cách ~5 tháng so với hiện tại) → lấy giá **Settlement Price**.

## SHFE (Thượng Hải) — Natural Rubber
- Web: `https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/`
- Statistical → ngày (trước 01 ngày) → Future → Daily express → All: Natural rubber →
  chọn **Volume lớn nhất** (thường cách ~3 tháng) → lấy giá tại **Settle**.

## SGX / SICOM (Singapore) — RSS3 & TSR20
- Web: `https://www.sgx.com/research-education/derivatives` → Historical Settlement Data → Type: Future.
- **RSS3**: cột COM = `RT`, COM_MM = tháng trước hiện tại 01 tháng, COM_YY = năm hiện tại → giá **SETTLE** (cùng 1 dòng).
- **TSR 20**: cột COM = `TF`, COM_MM = tháng trước 01 tháng, COM_YY = năm hiện tại → giá **SETTLE**.

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
