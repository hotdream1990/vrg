/* Dữ liệu nền của Sơ đồ vận hành: danh sách nhà máy CÓ sơ đồ (layout_key) + nhà máy đang xem (nhớ ở
   trình duyệt) + bố cục sơ đồ của nhà máy đó. */

import { useEffect, useState } from "react";

import { ApiError } from "../../../../../lib/http";
import { type FactoryBrief, type PlantLayout, fetchPlantLayout } from "../../../../../lib/smart-factory-client";
import { errText } from "../smart-factory-format";
import { useFactoryPicker } from "../use-factory-picker";

const STORE_KEY = "vrg.smart-factory.plant-factory-id";
const LOAD_FAIL = "Không tải được dữ liệu, vui lòng thử lại.";

const hasLayout = (f: FactoryBrief) => !!f.layout_key;

export const usePlantFactories = () => useFactoryPicker(STORE_KEY, hasLayout);

/** Bố cục sơ đồ của nhà máy đang xem; 404 (nhà máy vừa bị gỡ sơ đồ/tắt) → `onGone` để tải lại danh sách. */
export function usePlantLayout(factoryId: number | null, onGone: () => void) {
  const [data, setData] = useState<{ factoryId: number; layout: PlantLayout } | null>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (factoryId == null) return undefined;
    let alive = true;
    setError("");
    fetchPlantLayout(factoryId)
      .then((r) => { if (alive) setData({ factoryId, layout: r.layout }); })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(errText(e, LOAD_FAIL));
        if (e instanceof ApiError && e.status === 404) onGone();
      });
    return () => { alive = false; };
  }, [factoryId, tick]);   // onGone chỉ là lệnh tải lại danh sách — không cần theo dõi

  return {
    layout: data?.factoryId === factoryId ? data.layout : null,
    error,
    retry: () => setTick((t) => t + 1),
  };
}
