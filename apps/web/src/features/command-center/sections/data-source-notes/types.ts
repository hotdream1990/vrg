/** Kiểu dữ liệu cho ghi chú "cách lấy số liệu" của mỗi trang Quản lý số liệu.
 *  2 loại: `auto` = máy tự quét/tính; `manual` = người nhập tay. */
export type SourceKind = "auto" | "manual";

/** Một nguồn cụ thể (1 trang có thể gồm nhiều nguồn, vd trang các sàn có SHFE/OSE/SGX/MRB). */
export interface SourceDetail {
  /** Tên nguồn, vd "SHFE — Sàn kỳ hạn Thượng Hải". */
  name: string;
  /** Lấy Ở ĐÂU: URL/endpoint (tự động) hoặc mô tả nguồn gốc (thủ công). */
  where: string;
  /** Phương thức ngắn gọn, vd "GET JSON", "Tải ZIP → đọc PDF", "Nhập tay". */
  method?: string;
  /** VÀO NHƯ THẾ NÀO: các bước truy cập / thao tác. */
  steps: string[];
  /** VÀO TRƯỜNG GÌ, LẤY GÌ: trường/cột số liệu được lấy. */
  field: string;
  /** Đơn vị số liệu. */
  unit?: string;
  /** Lưu ý riêng cho nguồn này. */
  note?: string;
}

export interface DataSourceNote {
  kind: SourceKind;
  /** Tóm tắt 1 dòng hiện ở thanh gập (khi chưa mở). */
  tagline: string;
  /** Mô tả chung 1–2 câu (tuỳ chọn). */
  intro?: string;
  /** Danh sách nguồn. */
  sources: SourceDetail[];
  /** Lưu ý chung cuối hộp. */
  caveats?: string[];
}
