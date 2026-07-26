/* Thống kê THU MUA — lọc theo đơn vị · khu vực · kỳ · loại mủ (mủ nước / mủ chén / thành phẩm)
   và chủng loại (chỉ áp cho mủ thành phẩm). Cuối bảng: Tổng sản lượng + 3 đơn giá bình quân
   TÁCH RIÊNG theo đơn vị tính (mủ nước & mủ chén = đồng/độ, thành phẩm = triệu đ/tấn). */

import { ShoppingOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useState } from "react";

import {
  type StatsFilters, type StatsReport, downloadStatsXlsx, fetchPurchaseStats,
} from "../../../../lib/unit-analytics-client";
import AnalyticsFilters, { MultiSelect } from "./AnalyticsFilters";
import StatsTable, { type StatsCol } from "./StatsTable";
import { initialFilters, useFilterCatalog, useStatsReport } from "./use-stats";
import "../../../bulletin/bulletin.css";

const COLS: StatsCol[] = [
  { key: "qty_latex", label: "SL mủ nước", unit: "tấn", note: "cộng dồn" },
  { key: "qty_cup", label: "SL mủ chén", unit: "tấn", note: "cộng dồn" },
  { key: "qty_finished", label: "SL thành phẩm", unit: "tấn", note: "cộng dồn" },
  { key: "qty_total", label: "Tổng sản lượng", unit: "tấn", note: "theo bộ lọc" },
  { key: "price_latex_avg", label: "Đơn giá BQ mủ nước", unit: "đồng/độ", note: "BQ gia quyền" },
  { key: "price_cup_avg", label: "Đơn giá BQ mủ chén", unit: "đồng/độ", note: "BQ gia quyền" },
  { key: "price_finished_avg", label: "Đơn giá BQ thành phẩm", unit: "triệu đ/tấn", note: "BQ gia quyền" },
  { key: "days", label: "Số ngày có số liệu", unit: "ngày", note: "đếm" },
  { key: "no_purchase_days", label: "Ngày không thu mua", unit: "ngày", note: "đếm" },
];

const GROUPS = [
  { value: "company", label: "Đơn vị" },
  { value: "region", label: "Khu vực" },
  { value: "material", label: "Loại mủ" },
  { value: "grade", label: "Chủng loại" },
  { value: "day", label: "Ngày" },
];
const GROUP_LABEL: Record<string, string> = {
  company: "Đơn vị", region: "Khu vực", material: "Loại mủ", grade: "Chủng loại", day: "Ngày",
};

export default function PurchaseStatsPage() {
  const catalog = useFilterCatalog();
  const [filters, setFilters] = useState<StatsFilters>({ ...initialFilters(), materials: [] });
  const [saving, setSaving] = useState(false);
  const { data, loading, reload } = useStatsReport<StatsReport>(fetchPurchaseStats, filters);

  // Bỏ chọn "Thành phẩm" thì xoá luôn bộ lọc chủng loại (chủng loại chỉ có ở mủ thành phẩm).
  const change = (f: StatsFilters) =>
    setFilters(f.materials?.includes("finished") ? f : { ...f, grades: [] });

  const exportXlsx = async () => {
    setSaving(true);
    try {
      await downloadStatsXlsx("purchase", filters);
      message.success("Đã tải file Excel.");
    } catch (e) { message.error((e as Error).message); } finally { setSaving(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ShoppingOutlined style={{ marginRight: 8 }} />Thống kê thu mua</h2>
          <p>
            Kiểm tra số liệu thu mua các đơn vị đã nhập — lọc theo <b>đơn vị · khu vực · kỳ · loại mủ</b>.
            Đơn giá bình quân tính <b>gia quyền theo sản lượng</b> và tách riêng theo đơn vị tính.
          </p>
        </div>
      </div>

      <AnalyticsFilters
        catalog={catalog} value={filters} onChange={change} groupOptions={GROUPS}
        showGrades={!!filters.materials?.includes("finished")}
        extra={
          <MultiSelect
            placeholder="Tất cả loại mủ" options={catalog?.materials ?? []} width={200}
            value={filters.materials ?? []} onChange={(v) => change({ ...filters, materials: v })}
          />
        }
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      <StatsTable
        groupLabel={GROUP_LABEL[filters.groupBy] ?? "Nhóm"}
        cols={COLS} rows={data?.rows ?? []} totals={data?.totals ?? null}
        showRegion={filters.groupBy === "company"} loading={loading}
        warnings={data?.warnings}
        empty="Kỳ này chưa đơn vị nào nhập số liệu thu mua khớp bộ lọc."
      />
    </div>
  );
}
