import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./features/command-center/AppLayout";
import BulletinDetailPage from "./features/command-center/pages/BulletinDetailPage";
import BulletinListPage from "./features/command-center/pages/BulletinListPage";
import BulletinPage from "./features/command-center/pages/BulletinPage";
import DashboardPage from "./features/command-center/pages/DashboardPage";
import FxRatePage from "./features/command-center/pages/FxRatePage";
import MemberUnitPage from "./features/command-center/pages/MemberUnitPage";
import PriceSheetPage from "./features/command-center/pages/PriceSheetPage";
import RawMaterialPage from "./features/command-center/pages/RawMaterialPage";
import ScanPage from "./features/command-center/pages/ScanPage";
import VrgFloorPage from "./features/command-center/pages/VrgFloorPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/quet-da-san" element={<ScanPage />} />
          {/* Quản lý số liệu */}
          <Route path="/quan-ly-so-lieu/bang-gia-san" element={<PriceSheetPage />} />
          <Route path="/quan-ly-so-lieu/ty-gia" element={<FxRatePage />} />
          <Route path="/quan-ly-so-lieu/gia-san-tap-doan" element={<VrgFloorPage />} />
          <Route path="/quan-ly-so-lieu/gia-mu-nguyen-lieu" element={<RawMaterialPage />} />
          <Route path="/quan-ly-so-lieu/don-vi-thanh-vien" element={<MemberUnitPage />} />
          {/* Redirect route records cũ */}
          <Route path="/quet-da-san/records" element={<Navigate to="/quan-ly-so-lieu/bang-gia-san" replace />} />
          <Route path="/ban-tin" element={<BulletinListPage />} />
          <Route path="/ban-tin/tao" element={<BulletinPage />} />
          <Route path="/ban-tin/xem/:filename" element={<BulletinDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
