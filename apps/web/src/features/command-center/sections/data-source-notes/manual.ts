import type { DataSourceNote } from "./types";

/** Các trang SỐ LIỆU THỦ CÔNG — người nhập tay từ văn bản/báo cáo nguồn (không có crawler). */
export const MANUAL_NOTES: Record<string, DataSourceNote> = {
  "market-quote": {
    kind: "manual",
    tagline: "Nhập tay phiếu báo giá mủ thị trường theo ngày; Mục 6 (giá mủ nước + mủ chén) đồng bộ kho Giá mủ nguyên liệu.",
    intro:
      "1 phiếu/ngày: tỷ giá VCB + giá SVR (nội địa tư nhân · xuất khẩu hàng tư nhân · VRG xuất khẩu · VRG nội địa, kèm bao bì + đơn vị vận chuyển) + đề xuất mua từ khách hàng - hàng VRG + giá mủ khu vực (nước + chén) + ghi chú.",
    sources: [
      {
        name: "Phiếu báo giá mủ thị trường (nội bộ)",
        where: "Nguồn gốc: bản báo giá mủ hằng ngày của bộ phận kinh doanh (mẫu Excel 'Báo giá mủ ngày …').",
        method: "Nhập tay tại trang này",
        steps: [
          "Bấm '＋ Tạo phiếu mới', chọn ngày báo giá.",
          "Điền tỷ giá VCB, giá SVR cho 4 mục (NĐ tư nhân / XK hàng tư nhân / VRG XK / VRG nội địa) + bao bì (hàng rời/pallet) + đơn vị vận chuyển; Mục 4 thêm tình trạng.",
          "Điền Mục 5 (đề xuất mua từ khách hàng - hàng VRG: số lượng + đơn giá) — chỉ lưu trong phiếu.",
          "Điền Mục 6 (giá mủ nước + mủ chén theo đơn vị) — tự ghi vào kho 'Giá mủ nguyên liệu'.",
          "Phiếu tự lưu khi nhập.",
        ],
        field: "tỷ giá (mua_tm/mua_ck/bán); giá SVR theo chủng loại + bao bì + vận chuyển; đề xuất KH (số lượng/đơn giá); mủ nước (đồng/độ TSC) + mủ chén (đồng/độ DRC) theo đơn vị; ghi chú.",
        note: "Giá SVR còn được lưu chuỗi (source='market') làm đầu vào Bản tin/dự báo. Mục 6 (mủ nước=purchase, mủ chén=purchase_cup) dùng chung danh mục đơn vị thành viên.",
      },
    ],
  },

  "vrg-floor": {
    kind: "manual",
    tagline: "Nhập tay theo từng 'lần' Tập đoàn ban hành — không có nguồn tự động.",
    intro:
      "Biểu giá sàn do Tập đoàn ban hành: Giá XK FOB/FCA (USD/tấn) + Giá nội địa (VNĐ/tấn). Số 'lần' tự tăng.",
    sources: [
      {
        name: "Biểu giá sàn VRG ban hành (Ban TTKD)",
        where: "Nguồn gốc: quyết định / biểu giá sàn nội bộ của Ban TTKD VRG (không có API).",
        method: "Nhập tay tại trang này",
        steps: [
          "Bấm '＋ Tạo biểu giá mới (lần N)' — số lần tự nhảy.",
          "Chọn 'Ngày áp dụng'.",
          "Điền cho từng chủng loại: Giá XK FOB/FCA (USD/T) và Giá nội địa (VNĐ/T); ô trống = chưa có.",
          "Bấm 'Lưu biểu giá'.",
        ],
        field: "lan (số lần), as_of (ngày áp dụng); theo grade: fob_usd, domestic_vnd.",
        note: "Bản tin ngày tự lấy 2 lần mới nhất để so sánh. Lịch sử 2024–2026 đã nạp sẵn ~79 lần.",
      },
    ],
  },

  "raw-material": {
    kind: "manual",
    tagline: "Nhập tay giá thu mua mủ nước theo từng đơn vị thành viên (đồng/độ TSC).",
    intro: "Lưới: hàng = ngày, cột = đơn vị thành viên VRG (danh sách lấy từ trang 'Đơn vị thành viên').",
    sources: [
      {
        name: "Báo giá thu mua của các đơn vị thành viên",
        where: "Nguồn gốc: bảng giá thu mua mủ nước nội bộ của từng công ty/đơn vị VRG.",
        method: "Nhập tay tại trang này",
        steps: [
          "Chọn ngày rồi bấm '＋ Thêm ngày' để tạo dòng.",
          "Bấm vào ô giao (đơn vị × ngày) để nhập giá.",
          "Thêm/đổi tên cột đơn vị ở trang 'Đơn vị thành viên'.",
        ],
        field: "price (giá thu mua). Lưu với source='vrg', price_type='purchase'.",
        unit: "đồng/độ TSC (VNĐ trên mỗi độ hàm lượng cao su khô — TSC)",
        note: "Đã nạp sẵn ~302 bản ghi (21/06/2024 → 20/06/2026).",
      },
    ],
  },

  physical: {
    kind: "manual",
    tagline: "Nhập tay giá giao ngay (Asian physical) theo grade, USD/tấn; nền lịch sử nạp từ Excel chuyên viên.",
    intro: "Lưới: hàng = ngày, cột = chủng loại (RSS3 · STR20 · SMR20 · SIR20 · Thai Latex 60%…).",
    sources: [
      {
        name: "Báo cáo giá physical hằng ngày của chuyên viên (Reuters)",
        where: "Nguồn gốc: báo cáo giá giao ngay của chuyên viên; lịch sử từ file Excel sheet 'Lưu'.",
        method: "Nhập tay tại trang này (số liệu mới)",
        steps: [
          "Chọn ngày → '＋ Thêm ngày' → bấm ô để nhập giá theo grade.",
          "Lịch sử 14/05/2024 → 29/12/2025 đã nạp sẵn từ Excel chuyên viên.",
        ],
        field: "price. Lưu với source='reuters', price_type='physical'.",
        unit: "USD/tấn (đã quy đổi sẵn)",
        note: "ANRPC đã gỡ (28/06/2026). Ngoài ra crawler MRB/LGM cũng cấp giá physical dự phòng.",
      },
    ],
  },

  inventory: {
    kind: "manual",
    tagline: "Nhập tay theo tuần từ báo cáo tuần (chị Hạnh) — Tồn kho + Tồn kho đã có hợp đồng (tấn).",
    intro: "Chuỗi tồn kho thành phẩm theo tuần; dùng làm biến cho mô hình gợi ý giá sàn.",
    sources: [
      {
        name: "Báo cáo tuần (PDF) — chị Hạnh",
        where: "Nguồn gốc: file PDF báo cáo tuần của chị Hạnh (dòng 'Tổng cộng').",
        method: "Nhập tay (hoặc nạp từ PDF)",
        steps: [
          "Mở báo cáo tuần, tìm dòng 'Tổng cộng' — 2 số cuối = Tồn kho và Tồn kho đã có hợp đồng.",
          "Chọn 'Ngày tuần', điền 'Tồn kho (tấn)' và 'Tồn kho đã có HĐ (tấn)'.",
          "Bấm '＋ Thêm tuần' (hoặc 'Cập nhật tuần' nếu ngày đã có).",
        ],
        field: "ton_kho, ton_kho_hd (tấn), note. Cột 'Nguồn' hiển thị 'PDF tuần' hoặc 'Nhập tay'.",
        unit: "tấn",
        note: "Đã nạp sẵn ~71 tuần.",
      },
    ],
  },

  "member-unit": {
    kind: "manual",
    tagline: "Đơn vị thành viên + khu vực (2 tab) — quản trị viên thêm/sửa; dùng cho 'Giá mủ nguyên liệu'.",
    intro: "Đây là danh mục hỗ trợ (không phải số liệu giá): danh sách đơn vị (cột nhập giá mủ nước) và khu vực (nhóm đơn vị để gom giá theo khu vực trong bản tin).",
    sources: [
      {
        name: "Danh sách đơn vị thành viên VRG",
        where: "Nguồn gốc: cơ cấu đơn vị thành viên của VRG.",
        method: "Quản trị nhập tay tại trang này",
        steps: [
          "Tab Đơn vị: nhập tên đơn vị → '＋ Thêm đơn vị'; cột Khu vực để gán đơn vị vào 1 khu vực (không bắt buộc).",
          "Tab Khu vực: thêm / đổi tên / ẩn-hiện / sắp xếp / xoá khu vực.",
          "Dùng các nút thao tác để Đổi tên / Ẩn-Hiện / Sắp xếp thứ tự.",
        ],
        field: "name, is_active, thứ tự sắp xếp; region (khu vực đã gán, tùy chọn).",
        note: "Đổi tên vẫn giữ nguyên lịch sử giá. Bản tin gom giá mủ theo khu vực (khoảng min–max); đơn vị chưa gán khu vực không lên báo cáo.",
      },
    ],
  },
};
