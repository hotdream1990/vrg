import { ReloadOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { pageTitle } from "../../../data/sample-data";
import ConvergenceAndAlerts from "../sections/ConvergenceAndAlerts";
import HeatmapAndVrg from "../sections/HeatmapAndVrg";
import InventoryBalanceSection from "../sections/InventoryBalanceSection";
import KpiRow from "../sections/KpiRow";
import RagChat from "../sections/RagChat";

/** Trang Dashboard — KPI/giá/heatmap/tồn kho dùng dữ liệu thật; RAG hỏi-đáp là tính năng sắp có. */
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
          <p>Thẻ KPI · biểu đồ giá · heatmap · tồn kho dùng <b>dữ liệu thật</b> từ kho giá. Trợ lý hỏi-đáp RAG là tính năng sắp tích hợp.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => window.location.reload()}><ReloadOutlined /> Cập nhật</button>
        </div>
      </div>

      <KpiRow />
      <ConvergenceAndAlerts />
      <HeatmapAndVrg />
      <InventoryBalanceSection />
      <RagChat />
    </>
  );
}
