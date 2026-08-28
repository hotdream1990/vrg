/* Thống kê THU MUA — dashboard drill-down: Toàn Tập đoàn → Khu vực → Đơn vị → Ngày → Loại mủ.
   Bấm dòng (hoặc cột trong biểu đồ) để đi sâu; đường dẫn phía trên để quay lại lớp bất kỳ.
   Bộ lọc (đơn vị · khu vực · kỳ · loại mủ · chủng loại) áp chồng lên lớp đang mở.
   Đơn giá BQ tách riêng theo đơn vị tính (mủ nước/chén = đồng/độ, thành phẩm = triệu đ/tấn). */

import { ShoppingOutlined } from "@ant-design/icons";
import { message } from "antd";
import { useMemo, useState } from "react";

import {
  type StatsFilters, type StatsReport, downloadStatsXlsx, fetchPurchaseStats,
} from "../../../../lib/unit-analytics-client";
import AnalyticsFilters, { MultiSelect } from "./AnalyticsFilters";
import DrillHeader, { type Kpi } from "./DrillHeader";
import StatsTable, { type StatsCol } from "./StatsTable";
import { initialFilters, useFilterCatalog, useStatsReport } from "./use-stats";
import { CHAINS, DIM_LABEL, type DrillDim, applyDrill, useDrill } from "./use-drill";
import "../../../bulletin/bulletin.css";
import { CUP_PRICE_UNIT, LACE_PRICE_UNIT } from "../../../../lib/purchase-price-unit";

// THỨ TỰ CỘT kể một mạch: mủ nước + mủ chén + mủ dây → tổng mủ nguyên liệu → kế hoạch & % thực hiện, RỒI
// MỚI tới thành phẩm mua ngoài (chốt 14/08/2026). Thành phẩm là hàng ĐÃ CHẾ BIẾN mua lại, không
// nằm trong kế hoạch thu mua, nên xen nó vào giữa là người đọc tưởng nó thuộc mẫu số của %.
const COLS: StatsCol[] = [
  // Mủ nguyên liệu khai theo QUY KHÔ, thành phẩm khai theo số thực mua → nói rõ ở từng cột, vì
  // "Tổng sản lượng" cộng cả hai loại số này lại với nhau.
  { key: "qty_latex", label: "SL mủ nước", unit: "tấn", note: "cộng dồn · quy khô" },
  { key: "qty_cup", label: "SL mủ chén", unit: "tấn", note: "cộng dồn · quy khô" },
  { key: "qty_lace", label: "SL mủ dây", unit: "tấn", note: "cộng dồn · quy khô" },
  // % kế hoạch so TỬ SỐ = mủ nước + mủ chén + mủ dây, đều theo số QUY KHÔ (không gồm thành phẩm
  // mua ngoài) với chỉ tiêu NĂM —
  // đúng mẫu gốc Ban TTKD và khớp Báo cáo tổng hợp. Hiện luôn tử số để người đọc tự đối chiếu được,
  // và nói rõ "kỳ này / KH năm" vì kỳ mặc định là TUẦN → % nhỏ, dễ bị hiểu nhầm là luỹ kế cả năm.
  { key: "qty_material", label: "Tổng mủ nguyên liệu", unit: "tấn", note: "= nước + chén + dây (quy khô)" },
  { key: "plan_tonnes", label: "KH thu mua năm", unit: "tấn", note: "chỉ tiêu năm" },
  { key: "pct_plan", label: "% KH năm", unit: "%", note: "= mủ NL kỳ này / KH năm" },
  { key: "qty_finished", label: "SL thành phẩm", unit: "tấn", note: "cộng dồn · số thực mua" },
  { key: "qty_total", label: "Tổng sản lượng", unit: "tấn", note: "= mủ NL + thành phẩm" },
  { key: "price_latex_avg", label: "Đơn giá BQ mủ nước", unit: "đồng/độ", note: "BQ gia quyền" },
  { key: "price_cup_avg", label: "Đơn giá BQ mủ chén", unit: CUP_PRICE_UNIT, note: "BQ gia quyền" },
  { key: "price_lace_avg", label: "Đơn giá BQ mủ dây", unit: LACE_PRICE_UNIT, note: "BQ gia quyền" },
  { key: "price_finished_avg", label: "Đơn giá BQ thành phẩm", unit: "triệu đ/tấn", note: "BQ gia quyền" },
  { key: "days", label: "Số ngày có số liệu", unit: "ngày", note: "đếm" },
  { key: "no_purchase_days", label: "Ngày không thu mua", unit: "ngày", note: "đếm" },
];

// Dải KPI + biểu đồ CHỈ nói về MỦ NGUYÊN LIỆU và kế hoạch của nó (chốt 14/08/2026): tổng ở đây là
// mủ nước + mủ chén + mủ dây (quy khô), đúng bằng tử số của % kế hoạch — để các con số trên cùng
// một dải luôn khớp nhau.
// Thành phẩm mua ngoài xuống bảng bên dưới, KHÔNG có thẻ riêng ở dải này.
const KPIS: Kpi[] = [
  { key: "qty_material", label: "Tổng thu mua mủ nguyên liệu", unit: "tấn" },
  { key: "qty_latex", label: "Mủ nước", unit: "tấn" },
  { key: "qty_cup", label: "Mủ chén", unit: "tấn" },
  { key: "qty_lace", label: "Mủ dây", unit: "tấn" },
  { key: "plan_tonnes", label: "KH thu mua năm", unit: "tấn" },
  // Mẫu số là kế hoạch của MỌI đơn vị khớp bộ lọc (kể cả đơn vị kỳ này chưa mua) → luôn hiện được,
  // không phụ thuộc đang nhóm theo gì.
  { key: "pct_plan", label: "% thực hiện KH (kỳ đã chọn)", unit: "%" },
];

const GROUPS = (["region", "company", "day", "material", "grade"] as const)
  .map((v) => ({ value: v, label: DIM_LABEL[v] }));

export default function PurchaseStatsPage() {
  const catalog = useFilterCatalog();
  const [base, setBase] = useState<StatsFilters>({ ...initialFilters("region"), materials: [] });
  const [groupOverride, setGroupOverride] = useState<DrillDim | null>(null);
  const [saving, setSaving] = useState(false);
  const drill = useDrill(CHAINS.purchase);

  const dim: DrillDim = groupOverride ?? drill.currentDim;
  const filters = useMemo(() => {
    const f = applyDrill(base, CHAINS.purchase, drill.steps, catalog);
    return { ...f, groupBy: dim };
  }, [base, drill.steps, catalog, dim]);
  const { data, loading, reload } = useStatsReport<StatsReport>(fetchPurchaseStats, filters);

  // Đổi bộ lọc = xem lát cắt khác → quay về lớp ngoài cùng cho khỏi lẫn với nhánh đang mở.
  const change = (f: StatsFilters) => {
    drill.reset();
    setBase(f.materials?.includes("finished") ? f : { ...f, grades: [] });
  };
  const canDrill = drill.canDrill && dim !== "none";
  const goDeeper = (value: string) => { setGroupOverride(null); drill.down(value, dim); };

  // Biểu đồ vẽ MỦ NGUYÊN LIỆU cho mọi lớp (khu vực · đơn vị · ngày) — cùng câu chuyện với dải KPI.
  // RIÊNG lớp "loại mủ" phải vẽ `qty_total`: ở lớp đó mỗi dòng LÀ một loại mủ, nên dòng "Thành phẩm"
  // có `qty_material` rỗng và sẽ BIẾN MẤT khỏi biểu đồ (không phải hiện 0) — người xem tưởng kỳ này
  // không mua thành phẩm. Mỗi dòng ở lớp này chỉ có đúng một loại nên `qty_total` = sản lượng của nó.
  const chart = dim === "material"
    ? { key: "qty_total", label: "Sản lượng thu mua" }
    : { key: "qty_material", label: "Sản lượng thu mua mủ nguyên liệu" };

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
            Toàn Tập đoàn → <b>khu vực</b> → <b>công ty</b> → <b>ngày</b> → <b>loại mủ</b>:
            bấm vào dòng để xem chi tiết. Đơn giá bình quân tính <b>gia quyền theo sản lượng</b>.
          </p>
        </div>
      </div>

      <AnalyticsFilters
        catalog={catalog} value={base} onChange={change} groupOptions={GROUPS}
        groupValue={dim} onGroupChange={(v) => setGroupOverride(v as DrillDim)}
        showGrades={!!base.materials?.includes("finished")}
        extra={
          <MultiSelect
            placeholder="Tất cả loại mủ" options={catalog?.materials ?? []} width={200}
            value={base.materials ?? []} onChange={(v) => change({ ...base, materials: v })}
          />
        }
        onReload={reload} onExport={exportXlsx} loading={loading} exporting={saving}
      />

      <DrillHeader
        steps={drill.steps} onUpTo={drill.upTo} currentDim={dim} canDrill={canDrill}
        rows={data?.rows ?? []} totals={data?.totals ?? null} kpis={KPIS}
        chartKey={chart.key} chartLabel={chart.label} onPick={goDeeper}
      />

      <StatsTable
        groupLabel={DIM_LABEL[dim]} groupIsDate={dim === "day"} cols={COLS} rows={data?.rows ?? []}
        totals={data?.totals ?? null} showRegion={dim === "company"} loading={loading}
        warnings={data?.warnings} onRowClick={canDrill ? (r) => goDeeper(r.key) : undefined}
        empty="Kỳ này chưa đơn vị nào nhập số liệu thu mua khớp bộ lọc."
      />
    </div>
  );
}
