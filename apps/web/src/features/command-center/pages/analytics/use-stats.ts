/* Hook dùng chung cho các màn Thống kê: nạp danh mục bộ lọc + gọi báo cáo theo bộ lọc hiện tại. */

import { message } from "antd";
import { useCallback, useEffect, useState } from "react";

import { rangeOf } from "../../../../lib/date-presets";
import {
  type FilterCatalog, type StatsFilters, fetchFilterCatalog,
} from "../../../../lib/unit-analytics-client";

/** Bộ lọc khởi tạo: kỳ mặc định = tuần này, không lọc gì thêm. */
export const initialFilters = (groupBy = "company"): StatsFilters => {
  const r = rangeOf("Tuần này")!;
  return { from: r.from, to: r.to, companies: [], regions: [], grades: [], groupBy };
};

export function useFilterCatalog(): FilterCatalog | null {
  const [catalog, setCatalog] = useState<FilterCatalog | null>(null);
  useEffect(() => {
    fetchFilterCatalog().then(setCatalog).catch((e) => message.error(e.message));
  }, []);
  return catalog;
}

/** Gọi API báo cáo mỗi khi bộ lọc đổi. `load` phải là hàm ỔN ĐỊNH (khai báo ngoài component). */
export function useStatsReport<T>(load: (f: StatsFilters) => Promise<T>, filters: StatsFilters) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(() => {
    if (filters.from > filters.to) {
      message.warning("Khoảng ngày không hợp lệ: từ ngày sau đến ngày.");
      return;
    }
    setLoading(true);
    load(filters).then(setData).catch((e: Error) => message.error(e.message)).finally(() => setLoading(false));
  }, [load, filters]);

  useEffect(() => { reload(); }, [reload]);
  return { data, loading, reload };
}
