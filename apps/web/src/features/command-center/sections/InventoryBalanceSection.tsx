import { Segmented } from "antd";
import { useEffect, useState } from "react";

import { dmy } from "../../../lib/date";
import { type StockGroupBy, type StockSeries, fetchStockSeries } from "../../../lib/series-client";
import StackedDaysChart from "../charts/StackedDaysChart";

const fmt = (n: number | null | undefined) => (n == null ? "—" : Math.round(n).toLocaleString("vi-VN"));

const VIEWS: { value: StockGroupBy; label: string }[] = [
  { value: "structure", label: "Cơ cấu hợp đồng" },
  { value: "grade", label: "Chủng loại" },
  { value: "free_grade", label: "Tồn tự do theo chủng loại" },
  { value: "region", label: "Khu vực" },
];

/** Ý nghĩa từng cách xem — hiện ngay dưới tiêu đề để người đọc biết cột đang chia theo gì. */
const SUBTITLE: Record<StockGroupBy, string> = {
  structure: "Mỗi cột = tồn kho tổng = đã ký hợp đồng (đã có bên mua) + tồn tự do (chưa ký) — tấn, theo ngày",
  grade: "Mỗi cột = tồn kho tổng chia theo chủng loại mủ — tấn, theo ngày",
  free_grade: "Mỗi cột = phần CÒN BÁN ĐƯỢC (tồn − đã ký hợp đồng) của từng chủng loại — tấn, theo ngày",
  region: "Mỗi cột = tồn kho tổng chia theo khu vực của đơn vị thành viên — tấn, theo ngày",
};

/** Tồn kho Tập đoàn theo NGÀY, cộng thẳng từ biểu "Tồn kho" của các đơn vị thành viên.
 *  Xem được theo 4 chiều: cơ cấu hợp đồng · chủng loại · tồn tự do theo chủng loại · khu vực. */
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
        <span className="chip">Dữ liệu thật</span>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <Segmented size="small" value={view} onChange={(v) => setView(v as StockGroupBy)} options={VIEWS} />
      </div>
      {err ? (
        <div className="scan-empty">Chưa tải được tồn kho: {err}</div>
      ) : !data ? (
        <div className="scan-empty">Đang tải…</div>
      ) : !last ? (
        <div className="scan-empty">Chưa có đơn vị nào nhập biểu Tồn kho trong khoảng này.</div>
      ) : (
        <div className="chart-wrap">
          <StackedDaysChart
            rows={data.rows} series={data.series}
            footer={(r) => `Tổng tồn: ${fmt(r.total)} tấn · ${(r as typeof last).units_counted} đơn vị có tồn thành phẩm`}
          />
        </div>
      )}
      {data && last && (
        <p style={{ color: "var(--muted)", fontSize: 11, margin: "10px 0 0" }}>
          Cộng từ khối “Đã nhập kho” của các đơn vị thành viên, mỗi ngày là số thời điểm (không cộng dồn).
          Đơn vị khai ngày nào thì lấy số ngày đó; đơn vị tick “không phát sinh tồn kho để khai” thì giữ
          nguyên số của lần khai gần nhất; đơn vị chưa khai thì không có số — rê chuột để xem mỗi ngày
          có bao nhiêu đơn vị. Chuỗi bắt đầu từ {dmy(data.start_floor)} — trước đó chưa đủ đơn vị nhập
          để cộng thành số Tập đoàn.
          {data.pending.length > 0 && ` Chưa vẽ ${data.pending.map((p) => dmy(p.as_of)).join(", ")} vì đang nhập dở (mới ${data.pending.map((p) => p.units_counted).join(", ")} đơn vị).`}
          {view === "structure" && " Tồn tự do cao ⇒ áp lực bán ⇒ có thể điều chỉnh giá sàn hợp lý hơn để dễ tiêu thụ."}
          {view === "free_grade" && " Phần đã ký hợp đồng được trừ theo TỪNG chủng loại của từng đơn vị (cắt trần, không âm)."}
        </p>
      )}
    </div>
  );
}
