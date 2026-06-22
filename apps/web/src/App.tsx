import { App as AntApp, ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AdminLayout from "./features/command-center/AdminLayout";
import BulletinDetailPage from "./features/command-center/pages/BulletinDetailPage";
import BulletinListPage from "./features/command-center/pages/BulletinListPage";
import BulletinPage from "./features/command-center/pages/BulletinPage";
import DashboardPage from "./features/command-center/pages/DashboardPage";
import FxRatePage from "./features/command-center/pages/FxRatePage";
import MemberUnitPage from "./features/command-center/pages/MemberUnitPage";
import PriceSheetPage from "./features/command-center/pages/PriceSheetPage";
import ProfilePage from "./features/command-center/pages/ProfilePage";
import RawMaterialPage from "./features/command-center/pages/RawMaterialPage";
import ScanPage from "./features/command-center/pages/ScanPage";
import UserManagementPage from "./features/command-center/pages/UserManagementPage";
import VrgFloorPage from "./features/command-center/pages/VrgFloorPage";
import { AuthProvider } from "./features/auth/AuthContext";
import LoginPage from "./features/auth/LoginPage";
import ProtectedRoute from "./features/auth/ProtectedRoute";
import { vrgTheme } from "./theme";

export default function App() {
  return (
    <ConfigProvider theme={vrgTheme}>
      <AntApp>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              {/* Mọi route khác cần đăng nhập + nằm trong khung admin */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AdminLayout />}>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/quet-da-san" element={<ScanPage />} />
                  <Route path="/quan-ly-so-lieu/bang-gia-san" element={<PriceSheetPage />} />
                  <Route path="/quan-ly-so-lieu/ty-gia" element={<FxRatePage />} />
                  <Route path="/quan-ly-so-lieu/gia-san-tap-doan" element={<VrgFloorPage />} />
                  <Route path="/quan-ly-so-lieu/gia-mu-nguyen-lieu" element={<RawMaterialPage />} />
                  <Route path="/quan-ly-so-lieu/don-vi-thanh-vien" element={<MemberUnitPage />} />
                  <Route path="/quet-da-san/records" element={<Navigate to="/quan-ly-so-lieu/bang-gia-san" replace />} />
                  <Route path="/ban-tin" element={<BulletinListPage />} />
                  <Route path="/ban-tin/tao" element={<BulletinPage />} />
                  <Route path="/ban-tin/xem/:filename" element={<BulletinDetailPage />} />
                  <Route path="/quan-tri/nguoi-dung" element={<UserManagementPage />} />
                  <Route path="/ho-so" element={<ProfilePage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Route>
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}
