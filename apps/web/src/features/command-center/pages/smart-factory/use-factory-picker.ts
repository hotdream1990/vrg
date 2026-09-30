/* Danh sách nhà máy + nhà máy đang xem (nhớ ở trình duyệt theo `storeKey` riêng từng màn) — dùng chung
   cho Giám sát chỉ số và Sơ đồ vận hành. `reload()` tải lại danh sách: giữ nhà máy đang/đã chọn nếu còn,
   không thì lấy nhà máy đầu tiên (vd nhà máy vừa bị tắt/xoá → tự chuyển sang nhà máy còn lại). */

import { useEffect, useState } from "react";

import { type FactoryBrief, fetchFactories } from "../../../../lib/smart-factory-client";
import { errText } from "./smart-factory-format";

const LOAD_FAIL = "Không tải được dữ liệu, vui lòng thử lại.";

/** Nhớ nhà máy đang xem — chỉ là tiện lợi, trình duyệt chặn bộ nhớ thì bỏ qua. */
function readStoredId(storeKey: string): number | null {
  try {
    const v = Number(localStorage.getItem(storeKey));
    return Number.isInteger(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

function storeId(storeKey: string, id: number): void {
  try { localStorage.setItem(storeKey, String(id)); } catch { /* bộ nhớ bị chặn */ }
}

/** `only` lọc danh sách (hằng số ở cấp module — chỉ đọc lúc tải). */
export function useFactoryPicker(storeKey: string, only?: (f: FactoryBrief) => boolean) {
  const [factories, setFactories] = useState<FactoryBrief[] | null>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);
  const [factoryId, setFactoryId] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    setError("");
    fetchFactories()
      .then(({ factories: all }) => {
        if (!alive) return;
        const list = only ? all.filter(only) : all;
        setFactories(list);
        setFactoryId((cur) => {
          const want = cur ?? readStoredId(storeKey);
          return list.some((f) => f.id === want) ? want : (list[0]?.id ?? null);
        });
      })
      .catch((e: unknown) => { if (alive) setError(errText(e, LOAD_FAIL)); });
    return () => { alive = false; };
  }, [tick]);   // storeKey · only là hằng của từng màn

  const pick = (id: number) => { setFactoryId(id); storeId(storeKey, id); };
  const reload = () => setTick((t) => t + 1);
  return { factories, error, factoryId, pick, reload };
}
