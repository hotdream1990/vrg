import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./features/command-center/AppLayout";
import BulletinDetailPage from "./features/command-center/pages/BulletinDetailPage";
import BulletinListPage from "./features/command-center/pages/BulletinListPage";
import BulletinPage from "./features/command-center/pages/BulletinPage";
import DashboardPage from "./features/command-center/pages/DashboardPage";
import ScanPage from "./features/command-center/pages/ScanPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/quet-da-san" element={<ScanPage />} />
          <Route path="/ban-tin" element={<BulletinListPage />} />
          <Route path="/ban-tin/tao" element={<BulletinPage />} />
          <Route path="/ban-tin/xem/:filename" element={<BulletinDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
