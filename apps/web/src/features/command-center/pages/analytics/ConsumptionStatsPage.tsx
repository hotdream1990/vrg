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
  { key: "qty_principle", label: "HĐ nguyên tắc", unit: "tấn", note: "cộng dồn" },
  { key: "qty_unknown_type", label: "HĐ chưa khai loại", unit: "tấn", note: "cần bổ sung" },
  { key: "qty_export", label: "XK / UTXK", unit: "tấn", note: "cộng dồn" },
  { key: "qty_domestic", label: "Tiêu thụ trong nước", unit: "tấn", note: "cộng dồn" },
  { key: "qty_internal", label: "Tiêu thụ nội bộ", unit: "tấn", note: "cộng dồn" },
  { key: "revenue_ty", label: "Doanh thu", unit: "tỷ đồng", note: "cộng dồn" },
  { key: "avg_price_trieu", label: "Giá bán bình quân", unit: "triệu đ/tấn", note: "= DT / SL" },
  { key: "lines", label: "Số dòng bán", unit: "dòng", note: "đếm" },
];

/* Kế hoạch tiêu thụ là chỉ tiêu NĂM của TỪNG ĐƠN VỊ và chỉ đặt cho HĐ CHUYẾN → chỉ hiện khi nhóm
   theo đơn vị/khu vực (nhóm theo ngày/chủng loại thì cả cột rỗng), và % so với riêng HĐ chuyến.
   % KH doanh thu theo RỔ đơn vị được giao KH doanh thu như Dashboard (ở cấp khu vực/Tổng cộng, cột
   Doanh thu vẫn là tổng cả nhóm); để TRỐNG khi đơn vị trong rổ có lần giao thiếu tỷ giá/đơn giá
   hoặc đơn giá vượt trần — lý do đã nêu ở dòng cảnh báo phía trên. */
const PLAN_DIMS = new Set(["company", "region"]);
const PLAN_COLS: StatsCol[] = [
  { key: "plan_sales_spot_tonnes", label: "KH tiêu thụ HĐ chuyến", unit: "tấn", note: "chỉ tiêu năm" },
  { key: "pct_plan_sales_spot", label: "% thực hiện KH", unit: "%", note: "= HĐ chuyến / KH" },
  { key: "plan_revenue_ty", label: "KH doanh thu", unit: "tỷ đồng", note: "chỉ tiêu năm" },
  { key: "pct_plan_revenue", label: "% thực hiện KH doanh thu", unit: "%",
    note: "= DT đơn vị có KH / KH năm · — nếu thiếu/sai giá" },
];

const withPlanCols = (cols: StatsCol[]): StatsCol[] => {
  // Chèn ngay cạnh cột HĐ chuyến (KH chỉ đặt cho HĐ chuyến) — cột HĐ nguyên tắc lùi ra sau.
  const i = cols.findIndex((c) => c.key === "qty_spot") + 1;
  return [...cols.slice(0, i), ...PLAN_COLS, ...cols.slice(i)];
};

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
  // Mẫu số là kế hoạch của MỌI đơn vị khớp bộ lọc (kể cả đơn vị kỳ này chưa bán) → luôn hiện được,
  // không phụ thuộc đang nhóm theo gì.
  { key: "pct_plan_sales_spot", label: "% KH tiêu thụ (HĐ chuyến)", unit: "%" },
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
  const cols = useMemo(
    () => (detail ? DETAIL_COLS : PLAN_DIMS.has(dim) ? withPlanCols(SUMMARY_COLS) : SUMMARY_COLS),
    [detail, dim]);
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
            <b> % thực hiện kế hoạch</b> so sản lượng <b>HĐ chuyến</b> với chỉ tiêu năm ở màn
            {" "}<b>Kế hoạch năm</b> (kế hoạch tiêu thụ chỉ đặt cho HĐ chuyến).
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
        cols={cols}
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
