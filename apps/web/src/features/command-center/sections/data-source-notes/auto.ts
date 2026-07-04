import type { DataSourceNote } from "./types";

/** Các trang SỐ LIỆU TỰ ĐỘNG — máy tự quét theo lịch (mặc định 18:00 giờ VN), có thể sửa tay ô bất kỳ. */
export const AUTO_NOTES: Record<string, DataSourceNote> = {
  "price-sheet": {
    kind: "auto",
    tagline: "Máy tự quét mỗi ngày từ 4 sàn (SHFE · OSE · SGX · MRB) — chọn hợp đồng có khối lượng lớn nhất; có thể sửa tay.",
    intro:
      "Giá đóng cửa (settlement) của các sàn kỳ hạn + giá physical MRB, do crawler tự lấy rồi ghi vào kho giá. " +
      "Mỗi sàn tự chọn hợp đồng có khối lượng/giá trị giao dịch lớn nhất trong ngày (không cố định tháng đáo hạn).",
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
          "Lọc dòng có preliminary-settlement-price-abs; ưu tiên total-volume lớn nhất; nếu KL = 0 thì lấy open-interest lớn nhất.",
        ],
        field: "preliminary-settlement-price-abs (kèm delivery-month, base-date).",
        unit: "US cents/kg",
        note: "⚠️ Từ 6/2026 API SGX hay trả rỗng — khi thiếu cần nhập tay hoặc dùng nguồn thay thế.",
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
        name: "open.er-api.com (VND)",
        where: "https://open.er-api.com/v6/latest/USD",
        method: "GET JSON",
        steps: [
          "exchangerates.org.uk không có VND → gọi open.er-api riêng.",
          "Đọc rates.VND; ngày lấy từ time_last_update_unix.",
        ],
        field: "rates.VND.",
        unit: "VND / 1 USD",
      },
    ],
    caveats: [
      "Nếu Playwright lỗi (Cloudflare), VND vẫn được lấy độc lập.",
      "Có nút 'Quét tỷ giá' để chạy ngay; sửa tay ô bất kỳ nếu cần.",
    ],
  },
};
