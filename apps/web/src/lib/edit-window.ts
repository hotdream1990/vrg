/* Cửa sổ nhập liệu của CHUYÊN VIÊN: chỉ sửa được N ngày gần nhất; cũ hơn = chỉ xem.
   Admin luôn sửa được. Số ngày do admin cấu hình (đọc từ /api/settings/edit-windows). */

import { useEffect, useMemo, useState } from "react";

import { useAuth } from "../features/auth/AuthContext";
import { fetchEditWindows } from "./settings-client";

/** Số ngày từ ISO date `a` đến `b` (a cũ hơn b → dương). An toàn theo lịch (không lệch múi giờ). */
function daysBetween(aISO: string, bISO: string): number {
  const [ay, am, ad] = aISO.split("-").map(Number);
  const [by, bm, bd] = bISO.split("-").map(Number);
  return Math.round((Date.UTC(by, bm - 1, bd) - Date.UTC(ay, am - 1, ad)) / 86_400_000);
}

/** Lùi `delta` ngày từ 1 ISO date (YYYY-MM-DD). */
function shiftISO(iso: string, delta: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + delta);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
}

/** Hook cửa sổ sửa của chuyên viên. `isEditable(dateISO)`: admin→luôn true; editor→trong N ngày.
 *  `windowDates` = các ngày sửa được (hôm nay lùi N ngày) để lưới hiện sẵn dòng trống cho nhập. */
export function useEditorWindow() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [w, setW] = useState<{ days: number; today: string } | null>(null);

  useEffect(() => {
    fetchEditWindows().then((r) => setW({ days: r.editor_days, today: r.today })).catch(() => {});
  }, []);

  const isEditable = (dateISO: string): boolean => {
    if (isAdmin) return true;
    if (!w) return true; // chưa tải xong → tạm cho (backend vẫn là hàng rào thật)
    if (dateISO > w.today) return false; // tương lai
    return daysBetween(dateISO, w.today) <= w.days;
  };

  const windowDates = useMemo(
    () => (w ? Array.from({ length: w.days + 1 }, (_, i) => shiftISO(w.today, -i)) : []),
    [w],
  );

  return { isEditable, days: w?.days ?? null, today: w?.today ?? null, windowDates, ready: !!w, isAdmin };
}
