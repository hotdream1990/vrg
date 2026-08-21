import { LineChartOutlined, ReloadOutlined } from "@ant-design/icons";

import ConvergenceAndAlerts from "../sections/ConvergenceAndAlerts";
import HeatmapAndVrg from "../sections/HeatmapAndVrg";
import InventoryBalanceSection from "../sections/InventoryBalanceSection";
import KpiRow from "../sections/KpiRow";
import AssessmentBox from "../sections/market-movement/AssessmentBox";
import ConsumptionBlock from "../sections/market-movement/ConsumptionBlock";
import FxTrendBlock from "../sections/market-movement/FxTrendBlock";
import MarketHistoryBlock from "../sections/market-movement/MarketHistoryBlock";
import ModelVsActualBlock from "../sections/market-movement/ModelVsActualBlock";
import PhysicalBlock from "../sections/market-movement/PhysicalBlock";
import RawMaterialBlock from "../sections/market-movement/RawMaterialBlock";
import "../../bulletin/bulletin.css";

/** Bản tin biến động — dashboard tổng hợp mọi nhóm số liệu (chart/table) + box nhận định AI.
 *  Mục đích: cho lãnh đạo nắm nhanh biến động thị trường qua các nhóm dữ liệu. */
export default function MarketMovementPage() {
  return (
    <>
      <div className="page-title" id="top">
        <div>
          <h2><LineChartOutlined style={{ marginRight: 8 }} />Bản tin biến động</h2>
          <p>Bảng tổng hợp <b>tất cả nhóm số liệu</b> hệ thống (sàn quốc tế · physical · tỷ giá · thu mua · tồn kho · tiêu thụ · giá sàn) dạng biểu đồ/bảng. Trên cùng: nhận định AI theo từng nhóm.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => window.location.reload()}><ReloadOutlined /> Cập nhật</button>
        </div>
      </div>

      <AssessmentBox />

      <KpiRow />
      <ConvergenceAndAlerts />
      <HeatmapAndVrg />

      <MarketHistoryBlock />

      <div className="grid-2">
        <FxTrendBlock />
        <PhysicalBlock />
      </div>

      <RawMaterialBlock />

      <ModelVsActualBlock />
      <InventoryBalanceSection />
      <ConsumptionBlock />
    </>
  );
}
