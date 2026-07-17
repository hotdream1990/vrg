import { App as AntApp, ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AdminLayout from "./features/command-center/AdminLayout";
import BulletinDetailPage from "./features/command-center/pages/BulletinDetailPage";
import BulletinListPage from "./features/command-center/pages/BulletinListPage";
import BulletinPage from "./features/command-center/pages/BulletinPage";
import DashboardPage from "./features/command-center/pages/DashboardPage";
import FloorSuggestPage from "./features/command-center/pages/FloorSuggestPage";
import FxRatePage from "./features/command-center/pages/FxRatePage";
import InventoryPage from "./features/command-center/pages/InventoryPage";
import MarketDemandTimelinePage from "./features/command-center/pages/MarketDemandTimelinePage";
import MarketMovementPage from "./features/command-center/pages/MarketMovementPage";
import MarketQuotePage from "./features/command-center/pages/MarketQuotePage";
import WeeklyReportPage from "./features/command-center/pages/WeeklyReportPage";
import MemberPricePage from "./features/command-center/pages/MemberPricePage";
import MemberUnitPage from "./features/command-center/pages/MemberUnitPage";
import PhysicalSheetPage from "./features/command-center/pages/PhysicalSheetPage";
import PriceSheetPage from "./features/command-center/pages/PriceSheetPage";
import ProfilePage from "./features/command-center/pages/ProfilePage";
import RawMaterialPage from "./features/command-center/pages/RawMaterialPage";
import ScanPage from "./features/command-center/pages/ScanPage";
import SchedulePage from "./features/command-center/pages/SchedulePage";
import SystemConfigPage from "./features/command-center/pages/SystemConfigPage";
import UnitWeeklyPage from "./features/command-center/pages/UnitWeeklyPage";
import UserManagementPage from "./features/command-center/pages/UserManagementPage";
import VrgFloorPage from "./features/command-center/pages/VrgFloorPage";
import { AuthProvider, useAuth } from "./features/auth/AuthContext";
import LoginPage from "./features/auth/LoginPage";
import PublicPurchaseInputPage from "./features/public/PublicPurchaseInputPage";
import ProtectedRoute from "./features/auth/ProtectedRoute";
import RequireCap from "./features/auth/RequireCap";
import RequireRole from "./features/auth/RequireRole";
import { vrgTheme } from "./theme";

/** Trang chủ: đơn vị thành viên → thẳng trang nhập giá của đơn vị; còn lại → Dashboard. */
function HomeRoute() {
  const { user } = useAuth();
  if (user?.role === "member") return <Navigate to="/don-vi/gia-mu" replace />;
  return <DashboardPage />;
}

/** Nhu cầu thị trường (timeline): đơn vị thành viên → chỉ đơn vị của mình; chuyên viên có quyền → mọi đơn vị. */
function MarketDemandRoute() {
  const { user, can } = useAuth();
  if (user?.role === "member" || can("market_demand")) return <MarketDemandTimelinePage />;
  return <Navigate to="/" replace />;
}

/** Báo cáo tuần đơn vị: đơn vị thành viên nhập của mình; chuyên viên có quyền `unit_weekly` → mọi đơn vị. */
function UnitWeeklyRoute() {
  const { user, can } = useAuth();
  if (user?.role === "member" || can("unit_weekly")) return <UnitWeeklyPage />;
  return <Navigate to="/" replace />;
}

export default function App() {
  return (
    <ConfigProvider theme={vrgTheme}>
      <AntApp>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              {/* CÔNG KHAI — đơn vị thành viên nhập giá mủ (gác bằng mật khẩu riêng, ngoài đăng nhập) */}
              <Route path="/nhap-gia-mu" element={<PublicPurchaseInputPage />} />
              {/* Mọi route khác cần đăng nhập + nằm trong khung admin */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AdminLayout />}>
                  <Route path="/" element={<HomeRoute />} />
                  {/* Tài khoản đơn vị thành viên — tự nhập giá mủ nước/mủ chén của đơn vị mình */}
                  <Route element={<RequireRole roles={["member"]} />}>
                    <Route path="/don-vi/gia-mu" element={<MemberPricePage />} />
                  </Route>
                  {/* Nhu cầu thị trường — đơn vị thành viên (đơn vị mình) hoặc chuyên viên có quyền */}
                  <Route path="/nhu-cau-thi-truong" element={<MarketDemandRoute />} />
                  {/* Báo cáo tuần đơn vị (thu mua · tiêu thụ–tồn kho) — đơn vị thành viên hoặc chuyên viên có quyền */}
                  <Route path="/bao-cao-tuan-don-vi" element={<UnitWeeklyRoute />} />
                  {/* Số liệu tự động (quét + bảng giá sàn + tỷ giá) — quyền auto_data */}
                  <Route element={<RequireCap caps={["auto_data"]} />}>
                    <Route path="/quet-da-san" element={<ScanPage />} />
                    <Route path="/quan-ly-so-lieu/bang-gia-san" element={<PriceSheetPage />} />
                    <Route path="/quan-ly-so-lieu/ty-gia" element={<FxRatePage />} />
                  </Route>
                  <Route element={<RequireCap caps={["floor"]} />}>
                    <Route path="/quan-ly-so-lieu/gia-san-tap-doan" element={<VrgFloorPage />} />
                  </Route>
                  <Route element={<RequireCap caps={["floor_suggest"]} />}>
                    <Route path="/goi-y-gia-san" element={<FloorSuggestPage />} />
                  </Route>
                  <Route element={<RequireCap caps={["raw_material"]} />}>
                    <Route path="/quan-ly-so-lieu/gia-mu-nguyen-lieu" element={<RawMaterialPage />} />
                  </Route>
                  <Route element={<RequireCap caps={["physical"]} />}>
                    <Route path="/quan-ly-so-lieu/gia-physical" element={<PhysicalSheetPage />} />
                  </Route>
                  <Route element={<RequireCap caps={["inventory"]} />}>
                    <Route path="/quan-ly-so-lieu/ton-kho" element={<InventoryPage />} />
                  </Route>
                  {/* Báo giá: cần Mục 1-4 (market_quote) HOẶC Mục 5 (raw_material) */}
                  <Route element={<RequireCap caps={["market_quote", "raw_material"]} />}>
                    <Route path="/quan-ly-so-lieu/bao-gia-mu" element={<MarketQuotePage />} />
                  </Route>
                  <Route element={<RequireCap caps={["member_unit"]} />}>
                    <Route path="/quan-ly-so-lieu/don-vi-thanh-vien" element={<MemberUnitPage />} />
                  </Route>
                  <Route path="/quet-da-san/records" element={<Navigate to="/quan-ly-so-lieu/bang-gia-san" replace />} />
                  <Route element={<RequireCap caps={["bulletin_daily"]} />}>
                    <Route path="/ban-tin" element={<BulletinListPage />} />
                    <Route path="/ban-tin/tao" element={<BulletinPage />} />
                    <Route path="/ban-tin/xem/:filename" element={<BulletinDetailPage />} />
                  </Route>
                  <Route element={<RequireCap caps={["market_movement"]} />}>
                    <Route path="/ban-tin-bien-dong" element={<MarketMovementPage />} />
                  </Route>
                  <Route element={<RequireCap caps={["bulletin_weekly"]} />}>
                    <Route path="/ban-tin/tuan" element={<WeeklyReportPage />} />
                  </Route>
                  {/* Khu quản trị — chỉ admin (chặn viewer/editor gõ thẳng URL) */}
                  <Route element={<RequireRole roles={["admin"]} />}>
                    <Route path="/quan-tri/nguoi-dung" element={<UserManagementPage />} />
                    <Route path="/quan-tri/cau-hinh" element={<SystemConfigPage />} />
                    <Route path="/quan-tri/lich-chay" element={<SchedulePage />} />
                  </Route>
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
