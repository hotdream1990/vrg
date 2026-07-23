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
        name: "TOCOM / OSE — Sàn Osaka, Nhật (RSS3 & TSR20 · bảng này dùng RSS3)",
        where:
          "https://www.jpx.co.jp/automation/markets/statistics-derivatives/daily/files/{YYYYMM}/Daily_Report_OSE_{YYYYMMDD}.zip" +
          "  (vd phiên 22/07/2026 → .../daily/files/202607/Daily_Report_OSE_20260722.zip)",
        method: "Tải ZIP → đọc PDF (pdfplumber)",
        steps: [
          "Tải ZIP báo cáo ngày của OSE theo đúng phiên YYYYMMDD (ngày Nhật nghỉ/lễ không có file → 404).",
          "Giải nén, lấy PDF 'cdf_dyr_{YYYYMMDD}.pdf' (Commodity Derivatives Futures — phái sinh hàng hoá); đọc text từng trang.",
          "Chỉ nhận trang của THỊ TRƯỜNG ĐẤU GIÁ (競争売買 / AuctionMarket); bỏ các trang J-NET (thoả thuận ngoài sàn).",
          "Trong nhóm trang đó: trang 'RSS3 Rubber Futures' (ゴム（RSS3）先物) → RSS3, trang 'TSR20 Rubber Futures' → TSR20 (báo cáo hiện nay là trang 12 và 13).",
          "Mỗi dòng của bảng = 1 kỳ hạn (mã 6 số yyyymm): đọc Trading Value (取引金額 — giá trị giao dịch cả phiên, ¥) và Settlement Price (清算数値).",
          "Chọn kỳ hạn có Trading Value LỚN NHẤT rồi lấy Settlement Price của đúng kỳ hạn đó; nếu cả bảng không có giao dịch thì lấy kỳ hạn gần nhất (dòng đầu).",
        ],
        field:
          "Settlement Price (清算数値) của kỳ hạn có Trading Value lớn nhất, kèm mã kỳ hạn 6 số. " +
          "VD phiên 22/07/2026: kỳ hạn 202612, trading value 732.392.000 ¥ → settlement 420,7 JPY/kg.",
        unit: "JPY/kg (USD/tấn = giá ÷ tỷ giá USD/JPY × 1.000, lấy tỷ giá đúng ngày đó)",
        note:
          "JPX chỉ đăng báo cáo vào cuối ngày (tối giờ Nhật) nên dòng của chính hôm nay còn trống tới lúc đó — hệ thống KHÔNG lấy giá phiên khác đắp vào. " +
          "Ngày Nhật nghỉ lễ cũng trống (vd 20/07/2026 — Ngày của Biển). " +
          "TSR20 trên OSE gần như không có giao dịch nên settlement là số sàn công bố, không phải giá khớp lệnh (bảng này không dùng). " +
          "Gói ZIP của JPX chỉ lưu ~4 tháng gần nhất; lịch sử xa hơn phải nạp từ file của VRG.",
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
          "Lấy dòng CÓ NGÀY mới nhất khớp mẫu '1 USD = <số> <MÃ>' — đây là giá đóng cửa (close) của ngày đó; số 'live/spot' trên trang bị bỏ qua.",
        ],
        field: "Số sau '1 USD = ' của dòng ngày gần nhất (vd 6.7908 CNY).",
        unit: "Ngoại tệ / 1 USD",
        note:
          "USD/JPY lưu 2 số lẻ (163,12) theo đúng file gốc Ban TTKD; các đồng khác giữ số lẻ của nguồn. " +
          "Close của ngày D chỉ có trên web từ khoảng 06:00 sáng D+1 (nửa đêm giờ Anh) — nên tỷ giá và USD/tấn của ngày hôm nay được điền vào sáng hôm sau, không lấy tỷ giá ngày khác đắp vào.",
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
