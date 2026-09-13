import { ReloadOutlined } from "@ant-design/icons";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { pageTitle } from "../../../data/sample-data";
import ConvergenceAndAlerts from "../sections/ConvergenceAndAlerts";
import HeatmapAndVrg from "../sections/HeatmapAndVrg";
import InventoryBalanceSection from "../sections/InventoryBalanceSection";
import KpiRow from "../sections/KpiRow";
import PrivateLatexPriceCard from "../sections/PrivateLatexPriceCard";

/** Trang Dashboard — KPI/giá/heatmap/tồn kho dùng dữ liệu thật. Hỏi-đáp AI ở mục "Trợ lý AI". */
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
          <p>Thẻ KPI · biểu đồ giá · heatmap · tồn kho dùng <b>dữ liệu thật</b> từ kho giá. Hỏi-đáp AI xem ở mục <b>Trợ lý AI</b>.</p>
        </div>
        <div className="actions">
          <button className="btn" onClick={() => window.location.reload()}><ReloadOutlined /> Cập nhật</button>
        </div>
      </div>

      <KpiRow />
      <ConvergenceAndAlerts />
      <HeatmapAndVrg />
      <PrivateLatexPriceCard />
      <InventoryBalanceSection />
    </>
  );
}
