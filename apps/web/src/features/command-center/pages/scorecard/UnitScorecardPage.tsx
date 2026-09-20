/* Màn "CHỈ SỐ ĐƠN VỊ" — xem nhiều chỉ số của từng đơn vị thành viên trong MỘT bảng, có gom khu vực.

   Khác các màn Thống kê (mỗi màn một chủ đề, nhóm theo MỘT chiều): ở đây luôn hiện đồng thời dòng
   khu vực và dòng đơn vị, đổi tab không mất kỳ/bộ lọc đang xem. Số liệu lấy lại đúng các bảng
   thống kê đó nên hai nơi không thể lệch nhau.

   Tab cuối "Theo chủng loại" lật bảng: cột trở thành các chủng loại, ô đổ MỘT chỉ số chọn được —
   để nhìn cơ cấu chủng loại của mọi đơn vị cùng lúc thay vì lọc lần lượt từng chủng loại.

   Ba luật gom khu vực (server tính, web chỉ hiển thị): cộng dồn với sản lượng/doanh thu/kế hoạch ·
   bình quân GIA QUYỀN với các loại giá · tính lại từ tổng với % kế hoạch và tỷ lệ nộp. */

import { BarChartOutlined } from "@ant-design/icons";
import { Alert, Segmented } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { dmy } from "../../../../lib/date";
import { rangeOf } from "../../../../lib/date-presets";
import {
  type GradeReport, type MeasureInfo, type ScorecardFilters, type ScorecardReport,
  type TabInfo, fetchScorecard, fetchScorecardByGrade, fetchScorecardTabs,
} from "../../../../lib/unit-scorecard-client";
import StockCoverageBar from "../analytics/StockCoverageBar";
import { useFilterCatalog, useStatsReport } from "../analytics/use-stats";
import ScorecardFilterBar from "./ScorecardFilterBar";
import ScorecardTable from "./ScorecardTable";
import "../../../bulletin/bulletin.css";
import "./scorecard.css";

/** Tab lật bảng (cột = chủng loại) — chỉ có ở web, server có endpoint riêng cho nó. */
export const BY_GRADE = "by_grade" as const;

const initialFilters = (): ScorecardFilters => {
  const r = rangeOf("Tháng này")!;
  return { tab: "overview", from: r.from, to: r.to, asOf: r.to, companies: [], regions: [],
           grades: [], statusKind: "purchase", splitMerged: false };
};

type Query = ScorecardFilters & { measure: string };

/** Khai NGOÀI component để `useStatsReport` không gọi lại mỗi lần render (xem `use-stats.ts`). */
const load = (q: Query): Promise<ScorecardReport> =>
  q.tab === BY_GRADE ? fetchScorecardByGrade(q, q.measure) : fetchScorecard(q);

export default function UnitScorecardPage() {
  const catalog = useFilterCatalog();
  const [tabs, setTabs] = useState<TabInfo[]>([]);
  const [measures, setMeasures] = useState<MeasureInfo[]>([]);
  const [filters, setFilters] = useState<ScorecardFilters>(initialFilters);
  const [measure, setMeasure] = useState("con_qty");
  const [hideEmpty, setHideEmpty] = useState(false);

  useEffect(() => {
    fetchScorecardTabs()
      .then((r) => { setTabs(r.tabs); setMeasures(r.measures); })
      .catch(() => { setTabs([]); setMeasures([]); });
  }, []);

  const query = useMemo<Query>(() => ({ ...filters, measure }), [filters, measure]);
  const { data, loading, reload } = useStatsReport<ScorecardReport, Query>(load, query);

  const byGrade = filters.tab === BY_GRADE;
  const pickedMeasure = measures.find((m) => m.key === measure);
  // Tab "Theo chủng loại" mượn trục thời gian của chỉ số đang chọn: tồn kho thì hiện ô Chốt ngày.
  const tab: TabInfo | undefined = byGrade
    ? { key: BY_GRADE, label: "Theo chủng loại", grade_filter: "none",
        axis: pickedMeasure?.axis ?? "period" }
    : tabs.find((t) => t.key === filters.tab);

  const pickTab = useCallback((key: string) => {
    setFilters((f) => ({ ...f, tab: key as ScorecardFilters["tab"] }));
  }, []);

  const hint = data?.latest_stock_day;
  const hidden = (data as GradeReport | undefined)?.hidden_grades ?? [];

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><BarChartOutlined style={{ marginRight: 8 }} />Chỉ số đơn vị</h2>
          <p>
            Chỉ số của <b>từng đơn vị thành viên</b> trong một bảng, gom hai cấp
            <b> Tập đoàn → khu vực → đơn vị</b>. Đổi tab vẫn giữ nguyên kỳ và bộ lọc đang xem.
            Dòng khu vực <b>không phải phép cộng đơn thuần</b>: sản lượng/doanh thu/kế hoạch thì
            cộng dồn, các loại <b>giá là bình quân gia quyền</b>, còn <b>% kế hoạch</b> và
            <b> tỷ lệ nộp</b> tính lại trên tổng. Ô để trống nghĩa là <b>chưa có số</b> —
            không phải bằng 0.
          </p>
        </div>
      </div>

      <Segmented
        value={filters.tab} onChange={(v) => pickTab(v as string)} style={{ marginBottom: 10 }}
        options={[...tabs.map((t) => ({ value: t.key, label: t.label })),
                  { value: BY_GRADE, label: "Theo chủng loại" }]}
      />

      {byGrade && (
        <div className="card sc-measure">
          <b>Ô trong bảng đổ chỉ số:</b>
          <Segmented value={measure} onChange={(v) => setMeasure(v as string)}
                     options={measures.map((m) => ({ value: m.key, label: m.label }))} />
          <span className="sc-measure-unit">{pickedMeasure?.unit}</span>
        </div>
      )}

      <ScorecardFilterBar
        catalog={catalog} tab={tab} value={filters} onChange={setFilters}
        hideEmpty={hideEmpty} onHideEmptyChange={setHideEmpty}
        onReload={reload} loading={loading}
      />

      {data?.coverage && <StockCoverageBar asOf={data.as_of} coverage={data.coverage} />}

      {hint && (
        <Alert
          type="info" showIcon style={{ marginBottom: 10 }}
          message={`Không đơn vị nào khai tồn kho ngày ${dmy(data!.as_of)}. Ngày gần nhất có số là ${dmy(hint)}.`}
          description="Tồn kho không mượn số của ngày khác đắp sang, nên bảng để trống. Đổi ô “Chốt ngày” sang ngày đó để xem."
          action={<a onClick={() => setFilters((f) => ({ ...f, asOf: hint }))}>Xem ngày {dmy(hint)}</a>}
        />
      )}

      {byGrade && pickedMeasure?.note && (
        <Alert type="warning" showIcon style={{ marginBottom: 10 }} message={pickedMeasure.note} />
      )}

      {byGrade && hidden.length > 0 && (
        <Alert
          type="info" showIcon style={{ marginBottom: 10 }}
          message={`Cột “Các loại còn lại” gồm ${hidden.length} chủng loại lặt vặt (mỗi loại dưới 1% tổng): ${hidden.join(" · ")}.`}
        />
      )}

      <ScorecardTable
        cols={data?.cols ?? []} regions={data?.regions ?? []} totals={data?.totals ?? {}}
        loading={loading} warnings={data?.warnings} hideEmptyUnits={hideEmpty}
        empty="Không có đơn vị nào khớp bộ lọc."
      />
    </div>
  );
}
