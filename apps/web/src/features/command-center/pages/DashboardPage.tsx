import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { pageTitle } from "../../../data/sample-data";
import ArchitectureAndWorkflow from "../sections/ArchitectureAndWorkflow";
import ConvergenceAndAlerts from "../sections/ConvergenceAndAlerts";
import HeatmapAndVrg from "../sections/HeatmapAndVrg";
import KpiRow from "../sections/KpiRow";
import RagChat from "../sections/RagChat";
import ScenarioAndForecast from "../sections/ScenarioAndForecast";
import SecurityRow from "../sections/SecurityRow";
import SupplyDemandSection from "../sections/SupplyDemandSection";

/** Trang Dashboard — các phần mockup từ demo (sẽ tách dần thành route riêng sau). */
export default function DashboardPage() {
  const { hash } = useLocation();

  // Cuộn tới section khi điều hướng kèm hash (từ sidebar).
  useEffect(() => {
    if (!hash) return;
    const el = document.querySelector(hash);
    if (el) requestAnimationFrame(() => el.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [hash]);

  return (
    <>
      <div className="page-title" id="top">
        <div>
          <h2>{pageTitle.h2}</h2>
          <p>{pageTitle.p}</p>
        </div>
        <div className="actions">
          <button className="btn">⟳ Cập nhật</button>
          <button className="btn">⎙ Xuất báo cáo</button>
          <button className="btn btn-primary">＋ Tạo cảnh báo</button>
        </div>
      </div>

      <KpiRow />
      <ConvergenceAndAlerts />
      <ScenarioAndForecast />
      <HeatmapAndVrg />
      <SupplyDemandSection />
      <ArchitectureAndWorkflow />
      <RagChat />
      <SecurityRow />
    </>
  );
}
