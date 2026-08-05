/* Thống kê TIÊU THỤ (tách hẳn khỏi tồn kho) — dashboard drill-down:
   Toàn Tập đoàn → Khu vực → Đơn vị → Ngày → Chi tiết từng dòng bán (số HĐ, xuất kho, hoá đơn).
   Lọc chồng thêm: chủng loại · loại HĐ · hình thức HĐ · nguồn mủ. */

import { ExportOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useMemo, useState } from "react";

import {
  DETAIL_PAGE_SIZE, type StatsFilters, type StatsReport, downloadStatsXlsx, fetchConsumptionStats,
} from "../../../../lib/unit-analytics-client";
import AnalyticsFilters, { MultiSelect } from "./AnalyticsFilters";
import DrillHeader, { type Kpi } from "./DrillHeader";
import StatsTable, { type StatsCol } from "./StatsTable";
import { initialFilters, useFilterCatalog, useStatsReport } from "./use-stats";
import { CHAINS, DIM_LABEL, type DrillDim, applyDrill, useDrill } from "./use-drill";
import "../../../bulletin/bulletin.css";

const SUMMARY_COLS: StatsCol[] = [
  { key: "qty", label: "Tổng sản lượng", unit: "tấn", note: "theo bộ lọc" },
  { key: "qty_long_term", label: "HĐ dài hạn", unit: "tấn", note: "cộng dồn" },
  { key: "qty_spot", label: "HĐ chuyến", unit: "tấn", note: "cộng dồn" },
  { key: "qty_unknown_type", label: "HĐ chưa khai loại", unit: "tấn", note: "cần bổ sung" },
  { key: "qty_export", label: "XK / UTXK", unit: "tấn", note: "cộng dồn" },
  { key: "qty_domestic", label: "Tiêu thụ trong nước", unit: "tấn", note: "cộng dồn" },
  { key: "qty_internal", label: "Tiêu thụ nội bộ", unit: "tấn", note: "cộng dồn" },
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

const KPIS: Kpi[] = [
  { key: "qty", label: "Tổng sản lượng tiêu thụ", unit: "tấn" },
  { key: "revenue_ty", label: "Doanh thu", unit: "tỷ đồng" },
  { key: "avg_price_trieu", label: "Giá bán bình quân", unit: "triệu đ/tấn" },
  { key: "lines", label: "Số dòng bán", unit: "dòng" },
];

// Ngoài chuỗi drill còn xem nhanh theo chủng loại / loại HĐ / hình thức.
// KHÔNG còn nhóm/lọc theo "nguồn mủ" (mủ thu mua ↔ mủ khai thác): từ 30/07/2026 tiêu thụ tính từ
// lần giao của hợp đồng nên không tách 2 nguồn nữa, số liệu mới luôn rơi vào một nhãn duy nhất.
const GROUPS = [
  ...(["region", "company", "day", "grade"] as const).map((v) => ({ value: v, label: DIM_LABEL[v] })),
  { value: "contract", label: "Loại HĐ" },
  { value: "channel", label: "Hình thức HĐ" },
  { value: "none", label: "Chi tiết từng dòng" },
];
/** Các cách nhóm KHÔNG nằm trong chuỗi drill → chỉ để xem, không bấm sâu tiếp được. */
const OFF_CHAIN = new Set(["contract", "channel", "none"]);

export default function ConsumptionStatsPage() {
  const catalog = useFilterCatalog();
  const [base, setBase] = useState<StatsFilters>(
    { ...initialFilters("region"), contract: [], channel: [] });
  const [groupOverride, setGroupOverride] = useState<string | null>(null);
  // Chế độ chi tiết (từng dòng bán) cắt trang Ở SERVER — số lần giao tăng theo ngày.
  const [page, setPage] = useState(1);
  const [saving, setSaving] = useState(false);
  const drill = useDrill(CHAINS.consumption);

  const dim = groupOverride ?? drill.currentDim;
  const filters = useMemo(() => {
    const f = applyDrill(base, CHAINS.consumption, drill.steps, catalog);
    return { ...f, groupBy: dim, page };
  }, [base, drill.steps, catalog, dim, page]);
  const { data, loading, reload } = useStatsReport<StatsReport>(fetchConsumptionStats, filters);

  const detail = dim === "none";
  const canDrill = drill.canDrill && !OFF_CHAIN.has(dim);
  const goDeeper = (value: string) => {
    setPage(1); setGroupOverride(null); drill.down(value, dim as DrillDim);
  };
  const change = (f: StatsFilters) => { setPage(1); drill.reset(); setBase(f); };
  const pages = Math.ceil((data?.total ?? 0) / DETAIL_PAGE_SIZE);

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
            Toàn Tập đoàn → <b>khu vực</b> → <b>công ty</b> → <b>ngày</b> → <b>từng dòng bán</b>.
            Lọc thêm theo chủng loại · loại HĐ · hình thức HĐ.
            Dòng bán bằng USD thiếu tỷ giá không được tính vào doanh thu.
          </p>
        </div>
      </div>

      <AnalyticsFilters
        catalog={catalog} value={base} onChange={change} groupOptions={GROUPS}
        groupValue={dim} onGroupChange={setGroupOverride} showGrades
        extra={
          <>
            <MultiSelect placeholder="Tất cả loại HĐ" options={catalog?.contracts ?? []} width={170}
                         value={base.contract ?? []} onChange={(v) => change({ ...base, contract: v })} />
            <MultiSelect placeholder="Tất cả hình thức" options={catalog?.channels ?? []} width={175}
                         value={base.channel ?? []} onChange={(v) => change({ ...base, channel: v })} />
          </>
        }
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      <DrillHeader
        steps={drill.steps} onUpTo={drill.upTo} currentDim={dim as DrillDim} canDrill={canDrill}
        rows={detail ? [] : (data?.rows ?? [])} totals={data?.totals ?? null} kpis={KPIS}
        chartKey="qty" chartLabel="Sản lượng tiêu thụ" onPick={goDeeper}
      />

      <StatsTable
        groupLabel={detail ? "" : DIM_LABEL[dim as DrillDim]} groupIsDate={dim === "day"}
        cols={detail ? DETAIL_COLS : SUMMARY_COLS}
        rows={data?.rows ?? []} totals={detail ? null : (data?.totals ?? null)}
        showRegion={dim === "company"} loading={loading} warnings={data?.warnings}
        onRowClick={canDrill ? (r) => goDeeper(r.key) : undefined}
        empty="Kỳ này chưa có dòng tiêu thụ nào khớp bộ lọc."
      />

      {/* Chi tiết: server chỉ trả trang đang xem — dòng Tổng cộng phía trên vẫn tính cả kỳ. */}
      {detail && pages > 1 && (
        <div className="blt-toolbar" style={{ justifyContent: "flex-end", gap: 10 }}>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>
            {(data?.total ?? 0).toLocaleString("vi-VN")} dòng bán
          </span>
          <button className="btn" disabled={page <= 1 || loading}
            onClick={() => setPage((v) => Math.max(1, v - 1))}>‹ Trước</button>
          <span style={{ fontSize: 13 }}>Trang {page} / {pages}</span>
          <button className="btn" disabled={page >= pages || loading}
            onClick={() => setPage((v) => v + 1)}>Sau ›</button>
        </div>
      )}
    </div>
  );
}
