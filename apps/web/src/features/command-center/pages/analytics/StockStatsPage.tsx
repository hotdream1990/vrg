/* Thống kê TỒN KHO (để riêng) — trục NGÀY CHỐT, drill-down: Toàn Tập đoàn → Khu vực → Đơn vị →
   Ngày → Chủng loại.
   Tồn kho là số THỜI ĐIỂM nên không có khái niệm "tổng của một kỳ": chọn 1 ngày chốt, mỗi đơn vị
   lấy số MỚI NHẤT ≤ ngày đó (cũ tối đa N ngày) — luôn hiện ngày thật ở cột "Ngày lấy số" + "Số cũ",
   và luôn báo rõ đơn vị nào chưa có số (không lấy số ngày khác đắp vào).
   "Đã ký HĐ chưa giao" + "Tồn có thể giao dịch" là số SUY RA từ hợp đồng (server tính tại đúng
   ngày của số tồn); chi tiết từng hợp đồng vẫn ở màn riêng (Thống kê hợp đồng). */

import { InboxOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useMemo, useState } from "react";

import {
  type StatsReport, type StockFilters as Filters, downloadStockXlsx, fetchStockStats,
} from "../../../../lib/unit-analytics-client";
import DrillHeader, { type Kpi } from "./DrillHeader";
import StatsTable, { type StatsCol } from "./StatsTable";
import StockCoverageBar from "./StockCoverageBar";
import StockFilters, { initialStockFilters } from "./StockFilters";
import { useFilterCatalog, useStatsReport } from "./use-stats";
import { CHAINS, DIM_LABEL, type DrillDim, applyStockDrill, useDrill } from "./use-drill";
import "../../../bulletin/bulletin.css";

const COLS: StatsCol[] = [
  { key: "as_of", label: "Ngày lấy số", date: true, note: "— nếu nhóm gồm nhiều ngày" },
  { key: "age_days", label: "Số cũ", unit: "ngày", note: "cũ nhất trong nhóm" },
  { key: "not_warehoused", label: "Tồn chưa nhập kho", unit: "tấn", note: "thời điểm" },
  { key: "warehoused", label: "Tồn đã nhập kho", unit: "tấn", note: "thời điểm" },
  { key: "total", label: "Tổng tồn thành phẩm", unit: "tấn", note: "= 2 khối trên" },
  { key: "signed_undelivered", label: "Đã ký HĐ chưa giao", unit: "tấn quy khô", note: "nằm trong tồn TP" },
  { key: "tradable", label: "Tồn có thể giao dịch", unit: "tấn", note: "= tổng − chưa giao" },
  { key: "material", label: "Tồn nguyên liệu", unit: "tấn", note: "quy khô" },
];

const KPIS: Kpi[] = [
  { key: "total", label: "Tổng tồn thành phẩm", unit: "tấn" },
  { key: "not_warehoused", label: "Chưa nhập kho", unit: "tấn" },
  { key: "warehoused", label: "Đã nhập kho", unit: "tấn" },
  { key: "signed_undelivered", label: "Đã ký HĐ chưa giao", unit: "tấn quy khô" },
  { key: "tradable", label: "Tồn có thể giao dịch", unit: "tấn" },
  { key: "material", label: "Tồn nguyên liệu", unit: "tấn" },
];

const GROUPS = (["region", "company", "day", "grade"] as const)
  .map((v) => ({ value: v, label: DIM_LABEL[v] }));

export default function StockStatsPage() {
  const catalog = useFilterCatalog();
  const [base, setBase] = useState<Filters>(initialStockFilters);
  const [groupOverride, setGroupOverride] = useState<DrillDim | null>(null);
  const [saving, setSaving] = useState(false);
  const drill = useDrill(CHAINS.stock);

  const dim: DrillDim = groupOverride ?? drill.currentDim;
  const filters = useMemo(() => {
    const f = applyStockDrill(base, drill.steps, catalog);
    return { ...f, groupBy: dim };
  }, [base, drill.steps, catalog, dim]);
  const { data, loading, reload } = useStatsReport<StatsReport, Filters>(fetchStockStats, filters);

  const canDrill = drill.canDrill;
  const goDeeper = (value: string) => { setGroupOverride(null); drill.down(value, dim); };
  const change = (f: Filters) => { drill.reset(); setBase(f); };

  const exportXlsx = async () => {
    setSaving(true);
    try {
      await downloadStockXlsx(filters);
      message.success("Đã tải file Excel.");
    } catch (e) { message.error((e as Error).message); } finally { setSaving(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><InboxOutlined style={{ marginRight: 8 }} />Thống kê tồn kho</h2>
          <p>
            Ảnh chụp tại <b>một ngày chốt</b> — tồn kho là số <b>thời điểm</b>, không cộng dồn các
            ngày. Đơn vị chưa nhập đúng ngày chốt thì lấy số mới nhất trước đó trong giới hạn
            <b> số cũ tối đa</b>, và <b>hiện rõ ngày thật</b> của số đó; quá hạn coi như chưa có số.
            <b> Đã ký HĐ chưa giao</b> là số hệ thống tự tính từ hợp đồng (sản lượng hợp đồng −
            đã giao) tại đúng ngày của số tồn, <b>nằm trong</b> tồn thành phẩm; phần còn bán được
            là <b>tồn có thể giao dịch = tổng tồn − đã ký chưa giao</b> (âm nghĩa là đã ký nhiều
            hơn lượng đang có trong kho). Chi tiết từng hợp đồng xem ở mục
            <b> Thống kê hợp đồng</b>.
          </p>
        </div>
      </div>

      <StockFilters
        catalog={catalog} value={base} onChange={change} groupOptions={GROUPS}
        groupValue={dim} onGroupChange={(v) => setGroupOverride(v as DrillDim)}
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      {data?.coverage && (
        <StockCoverageBar asOf={filters.asOf} coverage={data.coverage} />
      )}

      <DrillHeader
        steps={drill.steps} onUpTo={drill.upTo} currentDim={dim} canDrill={canDrill}
        rows={data?.rows ?? []} totals={data?.totals ?? null} kpis={KPIS}
        chartKey="total" chartLabel="Tồn kho thành phẩm" onPick={goDeeper}
      />

      <StatsTable
        groupLabel={DIM_LABEL[dim]} groupIsDate={dim === "day"}
        // Nhóm theo ngày thì cột nhóm ĐÃ là ngày → bỏ 2 cột mốc thời gian cho khỏi lặp.
        cols={dim === "day" ? COLS.slice(2) : COLS} rows={data?.rows ?? []}
        totals={data?.totals ?? null} showRegion={dim === "company"} loading={loading}
        warnings={data?.warnings} onRowClick={canDrill ? (r) => goDeeper(r.key) : undefined}
        empty="Chưa đơn vị nào có số tồn kho tại ngày chốt (theo bộ lọc hiện tại)."
      />
    </div>
  );
}
