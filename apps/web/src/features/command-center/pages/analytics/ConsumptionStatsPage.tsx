/* Thống kê TIÊU THỤ (tách hẳn khỏi tồn kho) — lọc theo đơn vị · khu vực · kỳ · chủng loại ·
   loại HĐ · hình thức HĐ · nguồn mủ. Cuối bảng: Tổng sản lượng + giá bán bình quân.
   Nhóm theo "Chi tiết từng dòng" để soi lại đúng từng lần bán (số HĐ, ngày xuất kho, hoá đơn). */

import { ExportOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useState } from "react";

import {
  type StatsFilters, type StatsReport, downloadStatsXlsx, fetchConsumptionStats,
} from "../../../../lib/unit-analytics-client";
import AnalyticsFilters, { MultiSelect } from "./AnalyticsFilters";
import StatsTable, { type StatsCol } from "./StatsTable";
import { initialFilters, useFilterCatalog, useStatsReport } from "./use-stats";
import "../../../bulletin/bulletin.css";

const SUMMARY_COLS: StatsCol[] = [
  { key: "qty", label: "Tổng sản lượng", unit: "tấn", note: "theo bộ lọc" },
  { key: "qty_long_term", label: "HĐ dài hạn", unit: "tấn", note: "cộng dồn" },
  { key: "qty_spot", label: "HĐ chuyến", unit: "tấn", note: "cộng dồn" },
  { key: "qty_export", label: "XK / UTXK", unit: "tấn", note: "cộng dồn" },
  { key: "qty_domestic", label: "Nội tiêu", unit: "tấn", note: "cộng dồn" },
  { key: "revenue_ty", label: "Doanh thu", unit: "tỷ đồng", note: "cộng dồn" },
  { key: "avg_price_trieu", label: "Giá bán bình quân", unit: "triệu đ/tấn", note: "= DT / SL" },
  { key: "lines", label: "Số dòng bán", unit: "dòng", note: "đếm" },
];

const DETAIL_COLS: StatsCol[] = [
  { key: "as_of", date: true, label: "Ngày" },
  { key: "company", label: "Đơn vị", text: true },
  { key: "source_label", label: "Nguồn mủ", text: true },
  { key: "code", label: "Số HĐ/PL", text: true },
  { key: "contract_label", label: "Loại HĐ", text: true },
  { key: "channel_label", label: "Hình thức", text: true },
  { key: "grade", label: "Chủng loại", text: true },
  { key: "qty", label: "Số lượng", unit: "tấn" },
  { key: "price", label: "Đơn giá", note: "theo loại tiền" },
  { key: "ccy", label: "Loại tiền", text: true },
  { key: "revenue_vnd", label: "Doanh thu", unit: "đồng" },
  { key: "warehouse_date", date: true, label: "Ngày xuất kho" },
  { key: "invoice_date", date: true, label: "Ngày hoá đơn" },
];

const GROUPS = [
  { value: "company", label: "Đơn vị" },
  { value: "region", label: "Khu vực" },
  { value: "grade", label: "Chủng loại" },
  { value: "contract", label: "Loại HĐ" },
  { value: "channel", label: "Hình thức HĐ" },
  { value: "source", label: "Nguồn mủ" },
  { value: "day", label: "Ngày" },
  { value: "none", label: "Chi tiết từng dòng" },
];
const GROUP_LABEL: Record<string, string> = {
  company: "Đơn vị", region: "Khu vực", grade: "Chủng loại", contract: "Loại HĐ",
  channel: "Hình thức HĐ", source: "Nguồn mủ", day: "Ngày", none: "Chi tiết",
};

export default function ConsumptionStatsPage() {
  const catalog = useFilterCatalog();
  const [filters, setFilters] = useState<StatsFilters>(
    { ...initialFilters(), contract: [], channel: [], source: [] });
  const [saving, setSaving] = useState(false);
  const { data, loading, reload } = useStatsReport<StatsReport>(fetchConsumptionStats, filters);
  const detail = filters.groupBy === "none";

  const exportXlsx = async () => {
    setSaving(true);
    try {
      await downloadStatsXlsx("consumption", filters);
      message.success("Đã tải file Excel.");
    } catch (e) { message.error((e as Error).message); } finally { setSaving(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><ExportOutlined style={{ marginRight: 8 }} />Thống kê tiêu thụ</h2>
          <p>
            Riêng phần tiêu thụ — lọc theo <b>đơn vị · khu vực · kỳ · chủng loại · loại HĐ ·
            hình thức HĐ · nguồn mủ</b>. Dòng bán bằng USD thiếu tỷ giá không được tính vào doanh thu.
          </p>
        </div>
      </div>

      <AnalyticsFilters
        catalog={catalog} value={filters} onChange={setFilters} groupOptions={GROUPS} showGrades
        extra={
          <>
            <MultiSelect placeholder="Tất cả loại HĐ" options={catalog?.contracts ?? []} width={170}
                         value={filters.contract ?? []} onChange={(v) => setFilters({ ...filters, contract: v })} />
            <MultiSelect placeholder="Tất cả hình thức" options={catalog?.channels ?? []} width={175}
                         value={filters.channel ?? []} onChange={(v) => setFilters({ ...filters, channel: v })} />
            <MultiSelect placeholder="Tất cả nguồn mủ" options={catalog?.sources ?? []} width={180}
                         value={filters.source ?? []} onChange={(v) => setFilters({ ...filters, source: v })} />
          </>
        }
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      <StatsTable
        groupLabel={detail ? "" : (GROUP_LABEL[filters.groupBy] ?? "Nhóm")}
        cols={detail ? DETAIL_COLS : SUMMARY_COLS}
        rows={data?.rows ?? []} totals={detail ? null : (data?.totals ?? null)}
        showRegion={filters.groupBy === "company"} loading={loading} warnings={data?.warnings}
        empty="Kỳ này chưa có dòng tiêu thụ nào khớp bộ lọc."
      />
      {detail && data?.totals && (
        <p style={{ color: "var(--muted)", fontSize: 13, marginTop: 10 }}>
          Tổng theo bộ lọc: <b>{(data.totals.qty as number | null)?.toLocaleString("vi-VN") ?? "—"} tấn</b>
          {" · "}giá bán BQ <b>{(data.totals.avg_price_trieu as number | null)?.toFixed(2) ?? "—"} triệu đ/tấn</b>
        </p>
      )}
    </div>
  );
}
