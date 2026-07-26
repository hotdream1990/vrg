/* Thống kê TỒN KHO (để riêng) — lọc theo đơn vị · khu vực · kỳ · chủng loại.
   Tồn kho là số THỜI ĐIỂM: mỗi đơn vị lấy số của NGÀY CUỐI CÙNG có nhập tồn trong kỳ và
   hiện rõ ngày đó ở cột "Ngày lấy số" — không cộng dồn, không lấy số của ngày khác thay thế.
   Phần "Hợp đồng đã ký chưa giao" nằm ở màn riêng (Thống kê hợp đồng). */

import { InboxOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useState } from "react";

import {
  type StatsFilters, type StatsReport, downloadStatsXlsx, fetchStockStats,
} from "../../../../lib/unit-analytics-client";
import AnalyticsFilters from "./AnalyticsFilters";
import StatsTable, { type StatsCol } from "./StatsTable";
import { initialFilters, useFilterCatalog, useStatsReport } from "./use-stats";
import "../../../bulletin/bulletin.css";

const COLS: StatsCol[] = [
  { key: "as_of", label: "Ngày lấy số", date: true, note: "— nếu nhóm gồm nhiều ngày" },
  { key: "not_warehoused", label: "Tồn chưa nhập kho", unit: "tấn", note: "thời điểm" },
  { key: "warehoused", label: "Tồn đã nhập kho", unit: "tấn", note: "thời điểm" },
  { key: "total", label: "Tổng tồn thành phẩm", unit: "tấn", note: "= 2 khối trên" },
  { key: "material", label: "Tồn nguyên liệu", unit: "tấn", note: "quy khô" },
];

const GROUPS = [
  { value: "company", label: "Đơn vị" },
  { value: "region", label: "Khu vực" },
  { value: "grade", label: "Chủng loại" },
];
const GROUP_LABEL: Record<string, string> = { company: "Đơn vị", region: "Khu vực", grade: "Chủng loại" };

export default function StockStatsPage() {
  const catalog = useFilterCatalog();
  const [filters, setFilters] = useState<StatsFilters>(initialFilters());
  const [saving, setSaving] = useState(false);
  const { data, loading, reload } = useStatsReport<StatsReport>(fetchStockStats, filters);

  const exportXlsx = async () => {
    setSaving(true);
    try {
      await downloadStatsXlsx("stock", filters);
      message.success("Đã tải file Excel.");
    } catch (e) { message.error((e as Error).message); } finally { setSaving(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><InboxOutlined style={{ marginRight: 8 }} />Thống kê tồn kho</h2>
          <p>
            Tồn kho là số <b>thời điểm</b>: mỗi đơn vị lấy số của ngày cuối cùng có nhập tồn trong kỳ
            (xem cột <b>Ngày lấy số</b>) — không cộng dồn các ngày. Hợp đồng đã ký chưa giao xem ở
            mục <b>Thống kê hợp đồng</b>.
          </p>
        </div>
      </div>

      <AnalyticsFilters
        catalog={catalog} value={filters} onChange={setFilters} groupOptions={GROUPS} showGrades
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      <StatsTable
        groupLabel={GROUP_LABEL[filters.groupBy] ?? "Nhóm"}
        cols={COLS} rows={data?.rows ?? []} totals={data?.totals ?? null}
        showRegion={filters.groupBy === "company"} loading={loading} warnings={data?.warnings}
        empty="Kỳ này chưa đơn vị nào nhập tồn kho khớp bộ lọc."
      />
    </div>
  );
}
