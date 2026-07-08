import type { DataSourceNote } from "./types";

/** Các trang SỐ LIỆU TỰ ĐỘNG — máy tự quét theo lịch (mặc định 18:00 giờ VN), có thể sửa tay ô bất kỳ. */
export const AUTO_NOTES: Record<string, DataSourceNote> = {
  "price-sheet": {
    kind: "auto",
    tagline: "Máy tự quét mỗi ngày từ 4 sàn (SHFE · OSE · SGX · MRB) — mỗi sàn chọn hợp đồng đại diện theo quy ước; có thể sửa tay.",
    intro:
      "Giá đóng cửa (settlement) của các sàn kỳ hạn + giá physical MRB, do crawler tự lấy rồi ghi vào kho giá. " +
      "Quy ước chọn hợp đồng theo từng sàn: SHFE/OSE lấy hợp đồng có khối lượng/giá trị giao dịch lớn nhất; SGX lấy hợp đồng giao tháng sau (theo giờ Singapore).",
    sources: [
      {
        name: "SHFE — Sàn kỳ hạn Thượng Hải (cao su RU)",
        where: "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{YYYYMMDD}.dat",
        method: "GET JSON (header Referer: shfe.com.cn)",
        steps: [
          "Gọi file .dat theo ngày giao dịch YYYYMMDD, vd kx20260703.dat.",
          "Đọc mảng o_curinstrument[], lọc dòng có PRODUCTID bắt đầu bằng 'ru_f' (hợp đồng cao su).",
          "Chọn hợp đồng có VOLUME lớn nhất trong ngày.",
        ],
        field: "SETTLEMENTPRICE của hợp đồng khối lượng lớn nhất (kèm DELIVERYMONTH, VOLUME, OPENINTEREST).",
        unit: "CNY/tấn",
        note: "Nếu ngày đó chưa có dữ liệu, tự lùi tối đa 7 ngày giao dịch gần nhất (bỏ cuối tuần).",
      },
      {
        name: "TOCOM / OSE — Sàn Osaka, Nhật (RSS3 & TSR20)",
        where: "https://www.jpx.co.jp/.../files/{YYYYMM}/Daily_Report_OSE_{YYYYMMDD}.zip",
        method: "Tải ZIP → đọc PDF (pdfplumber)",
        steps: [
          "Tải file ZIP báo cáo ngày của OSE theo YYYYMMDD.",
          "Giải nén, lấy PDF 'cdf_dyr_{YYYYMMDD}.pdf'; đọc text từng trang.",
          "Tìm trang có chữ 'ゴム' (cao su); tách 2 nhóm: 'RSS' → RSS3, 'TSR' → TSR20.",
          "Mỗi nhóm chọn hợp đồng có giá trị giao dịch (trading value) lớn nhất; nếu không có KL thì lấy hợp đồng đầu.",
        ],
        field: "Giá settlement (số thập phân cuối dòng hợp đồng), kèm mã hợp đồng 6 số (vd 202609).",
        unit: "JPY/kg",
      },
      {
        name: "SGX / SICOM — Singapore (TSR20 mã TF · RSS3 mã RT)",
        where: "https://api.sgx.com/derivatives/v1.0/contract-code/{TF|RT}?category=futures",
        method: "GET JSON (header Origin/Referer: sgx.com)",
        steps: [
          "Gọi API theo mã hợp đồng TF (→ TSR20) và RT (→ RSS3).",
          "Lấy hợp đồng giao THÁNG SAU so với ngày hiện tại (giờ Singapore UTC+8), có preliminary-settlement-price-abs > 0. VD ngày 08/07/2026 → lấy kỳ hạn giao 2026-08.",
        ],
        field: "preliminary-settlement-price-abs của kỳ hạn tháng sau (kèm delivery-month, base-date).",
        unit: "US cents/kg",
        note: "⚠️ Sáng sớm sàn chưa ra settlement (kỳ tháng sau = 0/rỗng) → để trống, chờ phiên sau; hoặc nhập tay.",
      },
      {
        name: "MRB / LGM — Cục Cao su Malaysia (SMR CV/L/5/GP/10/20 + Latex)",
        where: "https://www.lgm.gov.my/webv2api/api/rubberprice/currentprice",
        method: "GET JSON (header Authorization: Basic …)",
        steps: [
          "Gọi API giá hiện hành → mảng JSON, mỗi dòng 1 grade.",
          "Chuẩn hoá tên grade (SMR 20 → SMR20…); bỏ grade ngoài danh mục.",
        ],
        field: "sellersUs (US cents/kg) cho các SMR. Latex quy đổi: sellers (Sen/kg) ÷ tỷ giá MYR/USD nội bộ của chính phiên đó.",
        unit: "US cents/kg",
      },
    ],
    caveats: [
      "Lịch quét mặc định 18:00 hằng ngày (giờ VN) — xem/đổi ở trang Lịch quét.",
      "Bấm 'Quét các sàn' để chạy ngay; có thể bấm vào ô để sửa/ghi đè giá thủ công khi cần.",
    ],
  },

  fx: {
    kind: "auto",
    tagline: "Máy tự quét tỷ giá USD (JPY · CNY · MYR · THB · VND) mỗi ngày; có thể sửa tay.",
    intro: "Tỷ giá USD dùng để quy đổi giá các sàn về USD/tấn.",
    sources: [
      {
        name: "exchangerates.org.uk (CNY · JPY · THB · MYR)",
        where: "https://www.exchangerates.org.uk/Dollars-to-{Yuan|YEN|Baht|Malaysian-Ringgit}-currency-conversion-page.html",
        method: "Playwright (Firefox headless — trang có Cloudflare)",
        steps: [
          "Mỗi đồng tiền mở 1 phiên trình duyệt riêng (Cloudflare chỉ cho 1 context/phiên).",
          "Chờ Cloudflare qua ('Just a moment' biến mất) rồi đọc bảng lịch sử tỷ giá.",
          "Lấy dòng mới nhất khớp mẫu '1 USD = <số> <MÃ>'.",
        ],
        field: "Số sau '1 USD = ' của dòng ngày gần nhất (vd 6.7908 CNY).",
        unit: "Ngoại tệ / 1 USD",
      },
      {
        name: "Vietcombank — USD/VND (Mua & Bán)",
        where: "https://www.vietcombank.com.vn/api/exchangerates?date=YYYY-MM-DD",
        method: "GET JSON",
        steps: [
          "Gọi API tỷ giá VCB theo ngày; lọc dòng currencyCode = 'USD'.",
          "Lấy 2 giá: transfer (mua chuyển khoản) và sell (bán).",
        ],
        field: "transfer → 'USD/VND (Mua)'; sell → 'USD/VND (Bán)'.",
        unit: "VND / 1 USD",
        note: "Cùng nguồn VCB với phiếu Báo giá mủ. API có date param nên backfill được từng ngày.",
      },
    ],
    caveats: [
      "Nếu Playwright lỗi (Cloudflare), VND (VCB) vẫn được lấy độc lập.",
      "Có nút 'Quét tỷ giá' để chạy ngay; sửa tay ô bất kỳ nếu cần.",
    ],
  },
};
