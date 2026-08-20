import { Segmented } from "antd";
import { useEffect, useState } from "react";

import { dmy } from "../../../lib/date";
import { type StockGroupBy, type StockSeries, fetchStockSeries } from "../../../lib/inventory-client";
import StockSeriesChart from "../charts/StockSeriesChart";

const fmt = (n: number | null | undefined) => (n == null ? "—" : Math.round(n).toLocaleString("vi-VN"));

const VIEWS: { value: StockGroupBy; label: string }[] = [
  { value: "structure", label: "Cơ cấu hợp đồng" },
  { value: "grade", label: "Chủng loại" },
  { value: "region", label: "Khu vực" },
];

/** Ý nghĩa từng cách xem — hiện ngay dưới tiêu đề để người đọc biết cột đang chia theo gì. */
const SUBTITLE: Record<StockGroupBy, string> = {
  structure: "Mỗi cột = tồn kho tổng = đã ký hợp đồng (đã có bên mua) + tồn tự do (chưa ký) — tấn, theo ngày",
  grade: "Mỗi cột = tồn kho tổng chia theo chủng loại mủ — tấn, theo ngày",
  region: "Mỗi cột = tồn kho tổng chia theo khu vực của đơn vị thành viên — tấn, theo ngày",
};

/** Dòng số của ngày mới nhất — nói đúng cái đang xem, không lặp lại con số của cách xem khác. */
function summary(s: StockSeries, last: StockSeries["rows"][number]): string {
  const head = `Ngày ${dmy(last.as_of)}: tồn ${fmt(last.total)} tấn`;
  if (s.group_by === "structure") {
    return `${head} = đã ký ${fmt(last.values.signed)} + tự do ${fmt(last.values.free)} tấn.`;
  }
  const top = Object.entries(last.values).sort((a, b) => b[1] - a[1]).slice(0, 3)
    .map(([k, v]) => `${k} ${fmt(v)}`).join(", ");
  return `${head} — cao nhất: ${top} tấn.`;
}

/** Tồn kho Tập đoàn theo NGÀY, cộng thẳng từ biểu "Tồn kho" của các đơn vị thành viên.
 *  Xem được theo 3 chiều: cơ cấu hợp đồng · chủng loại · khu vực. */
export default function InventoryBalanceSection() {
  const [view, setView] = useState<StockGroupBy>("structure");
  const [data, setData] = useState<StockSeries | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    fetchStockSeries(view).then(setData).catch((e) => setErr(e.message));
  }, [view]);

  const rows = data?.rows ?? [];
  const last = [...rows].reverse().find((r) => r.total != null);

  return (
    <div className="card" id="sec-tonkho">
      <div className="card-head">
        <div>
          <h3>Tồn kho VRG theo ngày · {VIEWS.find((v) => v.value === view)!.label}</h3>
          <div className="sub">{SUBTITLE[view]}</div>
        </div>
        <div className="actions" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Segmented size="small" value={view} onChange={(v) => setView(v as StockGroupBy)} options={VIEWS} />
          <span className="chip">Dữ liệu thật</span>
        </div>
      </div>
      {err ? (
        <div className="scan-empty">Chưa tải được tồn kho: {err}</div>
      ) : !data ? (
        <div className="scan-empty">Đang tải…</div>
      ) : !last ? (
        <div className="scan-empty">Chưa có đơn vị nào nhập biểu Tồn kho trong khoảng này.</div>
      ) : (
        <div className="chart-wrap"><StockSeriesChart series={data} /></div>
      )}
      {data && last && (
        <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
          Cộng từ khối “Đã nhập kho” của các đơn vị thành viên, mỗi ngày là số thời điểm (không cộng dồn);
          đơn vị chưa nhập đúng ngày thì lấy số gần nhất trong {data.max_age_days} ngày.
          Chuỗi bắt đầu từ {dmy(data.start_floor)} — trước đó chưa đủ đơn vị nhập để cộng thành số Tập đoàn.
          {view === "structure" && " Tồn tự do cao ⇒ áp lực bán ⇒ có thể điều chỉnh giá sàn hợp lý hơn để dễ tiêu thụ."}
          {" "}{summary(data, last)} Độ phủ: {last.units_counted}/{last.units_expected} đơn vị.
        </p>
      )}
    </div>
  );
}
