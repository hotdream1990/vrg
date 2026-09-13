/* Dashboard THEO DÕI NỘP BÁO CÁO — ma trận đơn vị × ngày cho biết đơn vị nào chưa nhập số liệu.
   Đây là màn phục vụ đúng mục đích "kiểm tra số liệu các đơn vị nhập": nhìn một lần thấy ngay
   ô trống của ngày nào, đơn vị nào — thay vì phải mở từng ngày một. */

import {
  CheckCircleFilled, CloseCircleFilled, MinusCircleFilled, ReloadOutlined, StopOutlined,
} from "@ant-design/icons";
import { Button, Segmented, Spin, message } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";

import { dm, isoDate } from "../../../../lib/date";
import {
  type StatsFilters, type StatusCell, type StatusReport, fetchSubmissionStatus,
} from "../../../../lib/unit-analytics-client";
import DateInput from "../../sections/DateInput";
import UnitLoginButton from "../components/UnitLoginButton";
import { MultiSelect } from "./AnalyticsFilters";
import MarkNoPurchaseButton from "./MarkNoPurchaseButton";
import { initialFilters, useFilterCatalog } from "./use-stats";
import "../../../bulletin/bulletin.css";

const KINDS = [{ label: "Thu mua", value: "purchase" }, { label: "Tồn kho", value: "consumption" }];
const SPANS = [7, 14, 30, 90, 180, 365] as const;
const MAX_STATUS_DAYS = 366;

const CELL: Record<StatusCell, { icon: JSX.Element; title: string }> = {
  ok: { icon: <CheckCircleFilled style={{ color: "var(--ok, #52c41a)" }} />, title: "Đã nhập" },
  no_purchase: { icon: <MinusCircleFilled style={{ color: "var(--muted)" }} />, title: "Không tổ chức thu mua" },
  none: { icon: <CloseCircleFilled style={{ color: "var(--danger, #ff4d4f)" }} />, title: "Chưa nhập" },
  // Đơn vị đã sáp nhập: từ ngày hiệu lực họ KHÔNG còn phải nộp — ô này không phải lỗi, và cũng
  // không nằm trong mẫu số "cần nộp" ở dòng tổng.
  merged: { icon: <StopOutlined style={{ color: "var(--muted)", opacity: 0.5 }} />, title: "Đã sáp nhập — không còn phải nộp" },
};

/** Khoảng N ngày gần nhất (tính cả hôm nay). */
function lastDays(n: number): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - (n - 1));
  return { from: isoDate(from), to: isoDate(to) };
}

function Kpi({ label, value, sub, color }: { label: string; value: number; sub?: string; color?: string }) {
  return (
    <div className="card" style={{ flex: "1 1 160px", minWidth: 160 }}>
      <div style={{ color: "var(--muted)", fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 700, color }}>{value.toLocaleString("vi-VN")}</div>
      {sub && <div style={{ color: "var(--muted)", fontSize: 12 }}>{sub}</div>}
    </div>
  );
}

export default function SubmissionStatusPage() {
  const catalog = useFilterCatalog();
  const [kind, setKind] = useState("purchase");
  const [span, setSpan] = useState<number | null>(14);
  const [filters, setFilters] = useState<StatsFilters>({ ...initialFilters(), ...lastDays(14) });
  const [data, setData] = useState<StatusReport | null>(null);
  const [loading, setLoading] = useState(false);

  const latest = useRef(0);
  const reload = useCallback(() => {
    if (filters.from > filters.to) { message.warning("Khoảng ngày không hợp lệ."); return; }
    const days = Math.floor((new Date(`${filters.to}T00:00:00`).getTime() -
      new Date(`${filters.from}T00:00:00`).getTime()) / 86_400_000) + 1;
    if (days > MAX_STATUS_DAYS) {
      message.warning(`Chỉ có thể theo dõi tối đa ${MAX_STATUS_DAYS} ngày trong một lần xem.`);
      return;
    }
    // Chỉ nhận lượt gọi mới nhất — đổi kỳ/biểu nhanh thì lượt cũ về sau không được đè lên.
    const seq = ++latest.current;
    const current = () => seq === latest.current;
    setLoading(true);
    fetchSubmissionStatus(kind, filters)
      .then((d) => { if (current()) setData(d); })
      .catch((e: Error) => { if (current()) message.error(e.message); })
      .finally(() => { if (current()) setLoading(false); });
  }, [kind, filters]);
  useEffect(() => { reload(); }, [reload]);

  const pickSpan = (n: number) => { setSpan(n); setFilters({ ...filters, ...lastDays(n) }); };
  const unitOptions = (catalog?.units ?? [])
    .filter((u) => !filters.regions.length || filters.regions.includes(u.region ?? ""))
    .map((u) => u.name);
  /* Đơn vị chọn được cho thao tác đánh dấu = ĐÚNG các dòng đang có trên ma trận (đơn vị được giao
     kế hoạch thu mua), không phải toàn bộ danh mục — chọn đơn vị không phải nộp thì không có ô nào
     để đánh dấu, chỉ gây hiểu nhầm. */
  const markUnits = (data?.rows ?? []).map((r) => r.company);
  const t = data?.totals;
  const pct = t?.expected ? Math.round((t.filled + t.no_purchase) / t.expected * 100) : 0;

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2>Theo dõi nộp báo cáo</h2>
          <p>
            Ma trận <b>đơn vị × ngày</b> cho biết đơn vị nào chưa nhập số liệu ngày nào.
            Có thể chọn nhanh đến <b>365 ngày</b> hoặc tự chọn kỳ theo dõi (tối đa 366 ngày mỗi lần xem).
            Cả hai biểu đều nhập <b>theo từng ngày</b>. Biểu Thu mua chỉ tính các đơn vị{" "}
            <b>được giao kế hoạch thu mua</b>; ngày chỉ tính là đã nộp khi bản ghi <b>có số liệu
            thật</b> (hoặc đơn vị đã tích “không tổ chức thu mua” / “không phát sinh tồn kho”).
          </p>
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <Segmented value={kind} onChange={(v) => setKind(v as string)} options={KINDS} />
        <Segmented
          value={span ?? 0}
          onChange={(v) => pickSpan(v as number)}
          options={SPANS.map((n) => ({ label: `${n} ngày`, value: n }))}
        />
        <DateInput value={filters.from} onChange={(v) => { setSpan(null); setFilters({ ...filters, from: v }); }} style={{ width: 160 }} />
        <span style={{ color: "var(--muted)" }}>→</span>
        <DateInput value={filters.to} onChange={(v) => { setSpan(null); setFilters({ ...filters, to: v }); }} style={{ width: 160 }} />
        <MultiSelect placeholder="Tất cả khu vực" options={catalog?.regions ?? []} width={190}
                     value={filters.regions} onChange={(v) => setFilters({ ...filters, regions: v })} />
        <MultiSelect placeholder="Tất cả đơn vị" width={230} options={unitOptions}
                     value={filters.companies} onChange={(v) => setFilters({ ...filters, companies: v })} />
        <Button icon={<ReloadOutlined />} onClick={reload} loading={loading}>Làm mới</Button>
        {/* Dọn ô trống hàng loạt — chỉ biểu Thu mua mới có cờ này, và chỉ admin thấy nút.
            Đơn vị + khoảng ngày chọn LẠI trong hộp thoại; bộ lọc ở đây chỉ là mặc định. */}
        {kind === "purchase" && (
          <MarkNoPurchaseButton filters={filters} unitOptions={markUnits} onDone={reload} />
        )}
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <Kpi label="Lượt cần nhập" value={t?.expected ?? 0} sub={`${data?.rows.length ?? 0} đơn vị × ${data?.dates.length ?? 0} ngày`} />
        <Kpi label="Đã nhập" value={t?.filled ?? 0} color="var(--ok, #52c41a)" sub={`Hoàn thành ${pct}%`} />
        <Kpi label="Không tổ chức thu mua" value={t?.no_purchase ?? 0} sub="đã báo, không tính thiếu" />
        <Kpi label="Chưa nhập" value={t?.missing ?? 0} color="var(--danger, #ff4d4f)" sub="cần nhắc đơn vị" />
      </div>

      <Spin spinning={loading}>
        <div className="card" style={{ padding: 0, overflow: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ minWidth: 110, position: "sticky", left: 0, zIndex: 2, background: "var(--card, #fff)" }}>Khu vực</th>
                <th style={{ minWidth: 210, position: "sticky", left: 110, zIndex: 2, background: "var(--card, #fff)" }}>Đơn vị</th>
                {(data?.dates ?? []).map((d) => (
                  <th key={d} className="r" style={{ minWidth: 46 }}>{dm(d)}</th>
                ))}
                <th className="r" style={{ minWidth: 78 }}>Đã nhập</th>
                <th className="r" style={{ minWidth: 78 }}>Chưa nhập</th>
              </tr>
            </thead>
            <tbody>
              {(data?.rows ?? []).map((r) => (
                <tr key={r.company}>
                  <td style={{ position: "sticky", left: 0, zIndex: 1, background: "var(--card, #fff)" }}>{r.region ?? "—"}</td>
                  {/* Nút đăng nhập hộ nằm NGAY CẠNH TÊN: bảng cuộn ngang theo số ngày nên cột
                      thêm ở cuối sẽ nằm ngoài màn hình. Chỉ admin thấy (component tự ẩn). */}
                  <td style={{ fontWeight: 500, whiteSpace: "nowrap", position: "sticky", left: 110, zIndex: 1, background: "var(--card, #fff)" }}>
                    {r.company}
                    {r.merged_into && (
                      <span className="chip info" style={{ fontSize: 10, marginLeft: 6 }}>
                        → {r.merged_into}
                      </span>
                    )}
                    <UnitLoginButton unit={r.company} compact />
                  </td>
                  {(data?.dates ?? []).map((d) => (
                    <td key={d} style={{ textAlign: "center" }} title={`${dm(d)} — ${CELL[r.cells[d]].title}`}>
                      {CELL[r.cells[d]].icon}
                    </td>
                  ))}
                  <td className="r">{r.filled}</td>
                  <td className="r" style={{ color: r.missing ? "var(--danger, #ff4d4f)" : undefined, fontWeight: r.missing ? 600 : 400 }}>
                    {r.missing}
                  </td>
                </tr>
              ))}
              {!data?.rows.length && !loading && (
                <tr><td colSpan={(data?.dates.length ?? 0) + 4}
                        style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                  Không có đơn vị nào khớp bộ lọc.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Spin>
    </div>
  );
}
