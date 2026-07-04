import type { DataSourceNote } from "./types";

/** Các trang SỐ LIỆU THỦ CÔNG — người nhập tay từ văn bản/báo cáo nguồn (không có crawler). */
export const MANUAL_NOTES: Record<string, DataSourceNote> = {
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
    tagline: "Danh mục công ty thành viên — quản trị viên thêm/sửa; dùng làm cột cho 'Giá mủ nguyên liệu'.",
    intro: "Đây là danh mục hỗ trợ (không phải số liệu giá): danh sách đơn vị để tạo cột nhập giá mủ nước.",
    sources: [
      {
        name: "Danh sách đơn vị thành viên VRG",
        where: "Nguồn gốc: cơ cấu đơn vị thành viên của VRG.",
        method: "Quản trị nhập tay tại trang này",
        steps: [
          "Nhập tên đơn vị → '＋ Thêm đơn vị'.",
          "Dùng các nút thao tác để Đổi tên / Ẩn-Hiện / Sắp xếp thứ tự.",
        ],
        field: "name (tên đơn vị), is_active (đang dùng/ẩn), thứ tự sắp xếp.",
        note: "Đổi tên vẫn giữ nguyên lịch sử giá đã nhập theo đơn vị đó.",
      },
    ],
  },
};
