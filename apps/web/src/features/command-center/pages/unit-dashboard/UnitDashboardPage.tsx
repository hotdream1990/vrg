/* Màn "DASHBOARD ĐƠN VỊ" — bức tranh của MỘT phạm vi (toàn Tập đoàn · một khu vực · một đơn vị thành
   viên): thu mua · tiêu thụ · tồn kho · chỉ tiêu năm, chia theo loại mủ / chủng loại / loại hợp đồng /
   hình thức tiêu thụ / đã-chưa nhập kho.

   Khác màn "Chỉ số đơn vị" (bảng SO SÁNH nhiều đơn vị): ở đây là KPI + biểu đồ của một phạm vi.
   Số liệu lấy nguyên từ server (cùng luật với các báo cáo tổng hợp) — web KHÔNG tự cộng lại.

   5 khối tải SONG SONG và độc lập (thu mua · tiêu thụ · tồn kho · chỉ tiêu · diễn biến tồn kho):
   khối nào chậm/lỗi chỉ ảnh hưởng ô của nó. Đổi phạm vi/kỳ → tải lại cả 5; đổi cách xem diễn biến
   tồn kho → chỉ tải lại khối đó. */

import { FundProjectionScreenOutlined } from "@ant-design/icons";
import { Alert } from "antd";
import { useEffect, useMemo, useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type DashStockView, type ScopeCatalog, fetchDashConsumption, fetchDashPurchase, fetchDashScopes,
  fetchDashStock, fetchDashStockSeries, fetchDashTargets,
} from "../../../../lib/unit-dashboard-client";
import ConsumptionSection from "./ConsumptionSection";
import DashboardFilterBar from "./DashboardFilterBar";
import DashboardKpiRow from "./DashboardKpiRow";
import { type DashFilters, initialDashFilters, localScopeLabel, toQuery } from "./dashboard-filters";
import PurchaseSection from "./PurchaseSection";
import StockSection from "./StockSection";
import StockSeriesCard from "./StockSeriesCard";
import TargetsCard from "./TargetsCard";
import { useDashboardBlock } from "./use-dashboard-block";
import "./unit-dashboard.css";

export default function UnitDashboardPage() {
  const [catalog, setCatalog] = useState<ScopeCatalog | null>(null);
  const [catalogErr, setCatalogErr] = useState<string | null>(null);
  const [filters, setFilters] = useState<DashFilters | null>(null);
  const [view, setView] = useState<DashStockView>("warehouse");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    fetchDashScopes()
      .then((c) => { if (alive) { setCatalog(c); setFilters(initialDashFilters(c)); } })
      .catch((e: unknown) => { if (alive) setCatalogErr(e instanceof Error ? e.message : String(e)); });
    return () => { alive = false; };
  }, []);

  // Tham số gọi API phải ỔN ĐỊNH theo giá trị — hook tải lại mỗi khi tham chiếu đổi.
  // Đổi riêng nút preset (vd sang "Tự chọn") mà ngày không đổi thì KHÔNG tải lại.
  // Ngày chốt tồn kho CHỈ vào tham số của khối tồn kho: server không dùng nó ở khối khác, gắn chung
  // thì bấm "Xem ngày …" là xoá trắng và tính lại cả 4 khối kia.
  const { scope, key, from, to, asOf } = filters ?? {};
  const query = useMemo(() => toQuery({ scope, key, from, to, asOf: "" }), [scope, key, from, to]);
  const stockQuery = useMemo(() => (query ? { ...query, asOf: asOf ?? "" } : null), [query, asOf]);
  const seriesQuery = useMemo(() => (query ? { ...query, view } : null), [query, view]);

  const purchase = useDashboardBlock(fetchDashPurchase, query, tick);
  const consumption = useDashboardBlock(fetchDashConsumption, query, tick);
  const stock = useDashboardBlock(fetchDashStock, stockQuery, tick);
  const targets = useDashboardBlock(fetchDashTargets, query, tick);
  const series = useDashboardBlock(fetchDashStockSeries, seriesQuery, tick);

  const loading = [purchase, consumption, stock, targets, series].some((b) => b.loading);
  const scopeLabel = purchase.data?.scope.label ?? stock.data?.scope.label
    ?? (filters ? localScopeLabel(filters) : "");
  const badRange = !!filters && !!filters.from && !!filters.to && filters.from > filters.to;

  return (
    <div className="main ud-page">
      <div className="page-title">
        <div>
          <h2><FundProjectionScreenOutlined style={{ marginRight: 8 }} />Dashboard đơn vị</h2>
          <p>
            {filters ? (
              <>Đang xem <b>{scopeLabel}</b> · kỳ <b>{dmy(filters.from)} → {dmy(filters.to)}</b>. </>
            ) : null}
            Thu mua · tiêu thụ · tồn kho · chỉ tiêu năm của một phạm vi. Ô “—” là <b>chưa có số</b>,
            không phải bằng 0.
          </p>
        </div>
      </div>

      {catalogErr && (
        <Alert type="error" showIcon className="ud-alert" title={`Chưa tải được danh sách phạm vi: ${catalogErr}`} />
      )}
      {!catalog || !filters ? (
        !catalogErr && <div className="card scan-empty">Đang tải phạm vi xem…</div>
      ) : (
        <>
          <DashboardFilterBar
            catalog={catalog} value={filters} onChange={setFilters}
            onReload={() => setTick((t) => t + 1)} loading={loading}
          />
          {badRange && (
            <Alert type="warning" showIcon className="ud-alert"
                   title="Khoảng ngày không hợp lệ: “từ ngày” đang sau “đến ngày”." />
          )}
          <DashboardKpiRow purchase={purchase} consumption={consumption} stock={stock} />
          <TargetsCard state={targets} />
          <PurchaseSection state={purchase} />
          <ConsumptionSection state={consumption} />
          <StockSection state={stock}
                        onPickAsOf={(d) => setFilters((f) => (f ? { ...f, asOf: d } : f))} />
          <StockSeriesCard state={series} view={view} onViewChange={setView} />
        </>
      )}
    </div>
  );
}
