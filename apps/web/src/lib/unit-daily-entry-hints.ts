/* Chú thích cách nhập cho từng khối biểu mẫu báo cáo ngày — dùng chung Thu mua / Tiêu thụ / Tồn kho.
   Đặt cạnh tiêu đề khối để đơn vị biết mỗi khối nhập theo kiểu nào (khách VRG yêu cầu). */

/** Sự kiện phát sinh mới ghi (thu mua, tiêu thụ) — không phát sinh thì bỏ trống. */
export const HINT_DAILY_EVENT = "Nhập hàng ngày khi có phát sinh";

/** Tồn kho khối 1/2/4: dùng nguyên chữ khách "lũy kế tại thời điểm báo cáo".
    Bản chất dữ liệu là SỐ TỔNG ĐANG ĐỨNG cuối ngày (số dư tại thời điểm), nhập lại MỖI ngày —
    không cộng dồn giữa các ngày (xem ghi chú đỏ "số tại thời điểm cuối ngày" trên chính màn Tồn kho). */
export const HINT_STOCK_BALANCE = "Nhập lũy kế tại thời điểm báo cáo";

/** Hợp đồng đã ký: nhập MỘT LẦN cho mỗi HĐ, hệ thống tự giữ đến khi giao — không nhập lại mỗi ngày. */
export const HINT_ONCE_PER_CONTRACT = "Nhập một lần cho mỗi hợp đồng";
