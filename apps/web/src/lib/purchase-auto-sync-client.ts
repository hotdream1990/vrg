/* Client API "Tự động lấy giá mủ nguyên liệu từ đơn vị" — cầu giá đơn vị tự khai → lớp chuyên viên.
   Backend: apps/api/app/services/purchase_price_sync.py */

import { apiFetch } from "./http";

export type AutoSyncUnit = { name: string; auto: boolean };

export type AutoSyncConfig = {
  enabled: boolean;              // công tắc TỔNG (tắt = dừng hết, vẫn giữ danh sách đã chọn)
  backfill_days: number;         // số ngày mặc định của nút "Lấy số đã có"
  units: AutoSyncUnit[];         // mọi đơn vị đang hoạt động + đơn vị nào đang được lấy tự động
};

const J = { "Content-Type": "application/json" };
const PATH = "/api/prices/purchase-auto-sync";

/** Trạng thái cấu hình hiện tại. */
export const fetchAutoSync = () => apiFetch<AutoSyncConfig>(PATH);

/** Lưu công tắc tổng + DANH SÁCH ĐẦY ĐỦ đơn vị được bật (đơn vị vắng mặt sẽ bị tắt). */
export const saveAutoSync = (enabled: boolean, companies: string[]) =>
  apiFetch<AutoSyncConfig>(PATH, { method: "PUT", headers: J, body: JSON.stringify({ enabled, companies }) });

/** Lấy ngay số các đơn vị đã nộp trong N ngày gần nhất (bù cho quãng trước khi bật). */
export const backfillAutoSync = (days: number) =>
  apiFetch<{ companies: string[]; days: number; copied: number }>(
    `${PATH}/backfill?days=${days}`, { method: "POST" });
