/* Thống kê TỒN KHO (để riêng) — dashboard drill-down:
   Toàn Tập đoàn → Khu vực → Đơn vị → Ngày → Chủng loại.
   Tồn kho là số THỜI ĐIỂM: mỗi đơn vị lấy ngày CUỐI có nhập tồn (cột "Ngày lấy số"); khi nhóm theo
   ngày thì mỗi dòng là ảnh chụp của riêng ngày đó và dòng Tổng cộng lấy ngày cuối — không cộng dồn.
   Hợp đồng đã ký chưa giao nằm ở màn riêng (Thống kê hợp đồng). */

import { InboxOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useMemo, useState } from "react";

import {
  type StatsFilters, type StatsReport, downloadStatsXlsx, fetchStockStats,
} from "../../../../lib/unit-analytics-client";
import AnalyticsFilters from "./AnalyticsFilters";
import DrillHeader, { type Kpi } from "./DrillHeader";
import StatsTable, { type StatsCol } from "./StatsTable";
import { initialFilters, useFilterCatalog, useStatsReport } from "./use-stats";
import { CHAINS, DIM_LABEL, type DrillDim, applyDrill, useDrill } from "./use-drill";
import "../../../bulletin/bulletin.css";

const COLS: StatsCol[] = [
  { key: "as_of", label: "Ngày lấy số", date: true, note: "— nếu nhóm gồm nhiều ngày" },
  { key: "not_warehoused", label: "Tồn chưa nhập kho", unit: "tấn", note: "thời điểm" },
  { key: "warehoused", label: "Tồn đã nhập kho", unit: "tấn", note: "thời điểm" },
  { key: "total", label: "Tổng tồn thành phẩm", unit: "tấn", note: "= 2 khối trên" },
  { key: "material", label: "Tồn nguyên liệu", unit: "tấn", note: "quy khô" },
];

const KPIS: Kpi[] = [
  { key: "total", label: "Tổng tồn thành phẩm", unit: "tấn" },
  { key: "not_warehoused", label: "Chưa nhập kho", unit: "tấn" },
  { key: "warehoused", label: "Đã nhập kho", unit: "tấn" },
  { key: "material", label: "Tồn nguyên liệu", unit: "tấn" },
];

const GROUPS = (["region", "company", "day", "grade"] as const)
  .map((v) => ({ value: v, label: DIM_LABEL[v] }));

export default function StockStatsPage() {
  const catalog = useFilterCatalog();
  const [base, setBase] = useState<StatsFilters>(initialFilters("region"));
  const [groupOverride, setGroupOverride] = useState<DrillDim | null>(null);
  const [saving, setSaving] = useState(false);
  const drill = useDrill(CHAINS.stock);

  const dim: DrillDim = groupOverride ?? drill.currentDim;
  const filters = useMemo(() => {
    const f = applyDrill(base, CHAINS.stock, drill.steps, catalog);
    return { ...f, groupBy: dim };
  }, [base, drill.steps, catalog, dim]);
  const { data, loading, reload } = useStatsReport<StatsReport>(fetchStockStats, filters);

  const canDrill = drill.canDrill;
  const goDeeper = (value: string) => { setGroupOverride(null); drill.down(value, dim); };
  const change = (f: StatsFilters) => { drill.reset(); setBase(f); };

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
            Toàn Tập đoàn → <b>khu vực</b> → <b>công ty</b> → <b>ngày</b> → <b>chủng loại</b>.
            Tồn kho là số <b>thời điểm</b> (xem cột <b>Ngày lấy số</b>) — không cộng dồn các ngày.
            Hợp đồng đã ký chưa giao xem ở mục <b>Thống kê hợp đồng</b>.
          </p>
        </div>
      </div>

      <AnalyticsFilters
        catalog={catalog} value={base} onChange={change} groupOptions={GROUPS}
        groupValue={dim} onGroupChange={(v) => setGroupOverride(v as DrillDim)} showGrades
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      <DrillHeader
        steps={drill.steps} onUpTo={drill.upTo} currentDim={dim} canDrill={canDrill}
        rows={data?.rows ?? []} totals={data?.totals ?? null} kpis={KPIS}
        chartKey="total" chartLabel="Tồn kho thành phẩm" onPick={goDeeper}
      />

      <StatsTable
        groupLabel={DIM_LABEL[dim]} groupIsDate={dim === "day"}
        // Nhóm theo ngày thì cột nhóm ĐÃ là ngày → bỏ cột "Ngày lấy số" cho khỏi lặp.
        cols={dim === "day" ? COLS.slice(1) : COLS} rows={data?.rows ?? []}
        totals={data?.totals ?? null} showRegion={dim === "company"} loading={loading}
        warnings={data?.warnings} onRowClick={canDrill ? (r) => goDeeper(r.key) : undefined}
        empty="Kỳ này chưa đơn vị nào nhập tồn kho khớp bộ lọc."
      />
    </div>
  );
}
