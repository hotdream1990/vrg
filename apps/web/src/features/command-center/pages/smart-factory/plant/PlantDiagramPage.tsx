/* Màn "SƠ ĐỒ VẬN HÀNH" (nhóm Nhà máy thông minh) — mimic màn SCADA RELCO tại nhà máy: mỗi khu một sơ đồ
   thiết bị với đèn chạy/dừng + ô số Hz · A · °C thời gian thực; thanh điện tổng DƯỚI sơ đồ; tiêu thụ trong
   ngày vẽ trong khung (khu khai `usage_box`) hoặc ô trên trang. Hàng trên chỉ còn tiêu đề · nhà máy · giờ
   cập nhật; thanh tab khu luôn hiện (kể cả chỉ còn 1 khu). Bố cục do server khai (layout_key của nhà máy)
   — web chỉ vẽ; khu `hidden` bị lọc. Khu đang mở nằm trên URL (?khu=). Quyền: `smart_factory`. Hợp đồng: plans/260930-nha-may-thong-minh-scada/
   so-do-van-hanh-contract.md + so-do-van-hanh-contract-v2.md. */

import { BankOutlined, DeploymentUnitOutlined, ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, Button, Select, Skeleton, Tabs } from "antd";
import { useEffect, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useAuth } from "../../../../auth/AuthContext";
import { SCADA_CONFIG_PATH } from "../FactoryMeterAlerts";
import "../smart-factory.css";
import PlantAreaDiagram from "./PlantAreaDiagram";
import PlantDailyUsage from "./PlantDailyUsage";
import PlantLiveStamp from "./PlantLiveStamp";
import PlantPowerBar from "./PlantPowerBar";
import { isStale, latestAt } from "./plant-format";
import { usePlantLive } from "./use-plant-live";
import { usePlantFactories, usePlantLayout } from "./use-plant-setup";
import "./plant.css";

const AREA_PARAM = "khu";
/** Thanh điện + ô/bảng "Tiêu thụ trong ngày" (cả trên trang lẫn `usage_box` trong khung) — ẩn từ 01/10/2026,
 *  bật lại 03/10/2026. Tắt (false) = không dựng component → không gọi /meters/daily. */
const SHOW_POWER_AND_USAGE = true;

const RetryButton = ({ onClick }: { onClick: () => void }) => (
  <Button size="small" icon={<ReloadOutlined />} onClick={onClick}>Thử lại</Button>
);

export default function PlantDiagramPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { factories, error: listErr, factoryId, pick, reload } = usePlantFactories();
  const { layout, error: layoutErr, retry } = usePlantLayout(factoryId, reload);
  const [params, setParams] = useSearchParams();

  const factory = factories?.find((f) => f.id === factoryId) ?? null;
  const areas = useMemo(() => (layout?.areas ?? []).filter((a) => !a.hidden), [layout]);
  const wanted = params.get(AREA_PARAM);
  const area = areas.find((a) => a.key === wanted) ?? areas[0] ?? null;
  const live = usePlantLive(layout ? factoryId : null, area?.key ?? null, reload);
  const at = latestAt(live.values);
  // Số cũ: so 2 mốc giờ của server (không dùng đồng hồ máy người xem).
  const stale = !live.failed && isStale(live.fetchedAt, at);
  const dim = live.failed || stale;

  /** Khu trên URL (?khu=); null = bỏ. */
  const setArea = (key: string | null) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    if (key) next.set(AREA_PARAM, key);
    else next.delete(AREA_PARAM);
    return next;
  }, { replace: true });
  const pickFactory = (id: number) => { pick(id); setArea(null); };

  // ?khu= không có trong sơ đồ (link cũ, đổi nhà máy) → thay bằng khu đầu.
  useEffect(() => {
    if (wanted != null && areas.length > 0 && !areas.some((a) => a.key === wanted)) setArea(areas[0].key);
  }, [wanted, layout]);   // areas suy từ layout; setArea chỉ là lệnh ghi URL

  return (
    <div className="main sf-page pl-page">
      <div className="page-title">
        <div><h2><DeploymentUnitOutlined style={{ marginRight: 8 }} />Sơ đồ vận hành</h2></div>
        <div className="pl-head-end">
          {factories && factories.length > 1 ? (
            <Select style={{ minWidth: 220 }} value={factoryId ?? undefined} onChange={pickFactory}
              options={factories.map((f) => ({ value: f.id, label: f.name }))} />
          ) : factory && <span className="sf-factory-name"><BankOutlined /> {factory.name}</span>}
          {area && <PlantLiveStamp loaded={live.values != null} at={at} failed={live.failed} stale={stale} />}
        </div>
      </div>

      {listErr && (
        <Alert type="error" showIcon className="sf-alert" title={`Chưa tải được danh sách nhà máy: ${listErr}`}
          action={<RetryButton onClick={reload} />} />
      )}

      {!factories ? (
        !listErr && <div className="card"><Skeleton active paragraph={{ rows: 8 }} /></div>
      ) : factories.length === 0 ? (
        <Alert type="info" showIcon className="sf-alert" title="Chưa có sơ đồ vận hành"
          action={isAdmin && (
            <Link to={SCADA_CONFIG_PATH}><Button type="primary" icon={<SettingOutlined />}>Cấu hình</Button></Link>
          )} />
      ) : (
        <>
          {layoutErr && (
            <Alert type="error" showIcon className="sf-alert" title={layoutErr}
              action={<RetryButton onClick={retry} />} />
          )}
          {!layout ? (
            !layoutErr && <div className="card"><Skeleton active paragraph={{ rows: 8 }} /></div>
          ) : (
            <>
              {SHOW_POWER_AND_USAGE && area && !area.usage_box && factory && factory.metrics.length > 0 && (
                <PlantDailyUsage factoryId={factory.id} metrics={factory.metrics} />
              )}
              <div className="card pl-area-card">
                <Tabs activeKey={area?.key} onChange={setArea}
                  items={areas.map((a) => ({ key: a.key, label: a.label }))} />
                {area && (
                  <PlantAreaDiagram area={area} values={live.values} failed={live.failed} dim={dim}
                    usage={SHOW_POWER_AND_USAGE && factory ? { factoryId: factory.id, metrics: factory.metrics } : null} />
                )}
                {SHOW_POWER_AND_USAGE && layout.power.length > 0 && (
                  <PlantPowerBar items={layout.power} values={live.powerValues} dim={dim} />
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
