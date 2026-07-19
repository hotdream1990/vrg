import { App as AntApp, ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AdminLayout from "./features/command-center/AdminLayout";
import AssistantPage from "./features/command-center/pages/AssistantPage";
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
import MemberUnitPage from "./features/command-center/pages/MemberUnitPage";
import PhysicalSheetPage from "./features/command-center/pages/PhysicalSheetPage";
import PriceSheetPage from "./features/command-center/pages/PriceSheetPage";
import ProfilePage from "./features/command-center/pages/ProfilePage";
import RawMaterialPage from "./features/command-center/pages/RawMaterialPage";
import ScanPage from "./features/command-center/pages/ScanPage";
import SchedulePage from "./features/command-center/pages/SchedulePage";
import SystemConfigPage from "./features/command-center/pages/SystemConfigPage";
import PeriodReportPage from "./features/command-center/pages/PeriodReportPage";
import UnitDailyPage from "./features/command-center/pages/UnitDailyPage";
import YearPlanPage from "./features/command-center/pages/YearPlanPage";
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
  if (user?.role === "member") return <Navigate to="/bao-cao-thu-mua" replace />;
  return <DashboardPage />;
}

/** Nhu cầu thị trường (timeline): đơn vị thành viên → chỉ đơn vị của mình; chuyên viên có quyền → mọi đơn vị. */
function MarketDemandRoute() {
  const { user, can } = useAuth();
  if (user?.role === "member" || can("market_demand")) return <MarketDemandTimelinePage />;
  return <Navigate to="/" replace />;
}

/** Báo cáo tiêu thụ–tồn kho theo ngày: đơn vị thành viên nhập của mình; chuyên viên có quyền `unit_daily` → mọi đơn vị. */
function UnitDailyRoute(props: React.ComponentProps<typeof UnitDailyPage>) {
  const { user, can } = useAuth();
  if (user?.role === "member" || can("unit_daily")) return <UnitDailyPage {...props} />;
  return <Navigate to="/" replace />;
}

/** Báo cáo tổng hợp theo kỳ: đơn vị thành viên → đơn vị mình; chuyên viên có quyền → mọi đơn vị. */
function PeriodReportRoute() {
  const { user, can } = useAuth();
  if (user?.role === "member" || can("unit_daily")) return <PeriodReportPage />;
  return <Navigate to="/" replace />;
}

/** Kế hoạch năm (số liệu nhập 1 lần/năm): đơn vị thành viên → đơn vị mình; chuyên viên có quyền → mọi đơn vị. */
function YearPlanRoute() {
  const { user, can } = useAuth();
  if (user?.role === "member" || can("unit_daily")) return <YearPlanPage />;
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
                  {/* Nhu cầu thị trường — đơn vị thành viên (đơn vị mình) hoặc chuyên viên có quyền */}
                  <Route path="/nhu-cau-thi-truong" element={<MarketDemandRoute />} />
                  {/* 3 báo cáo theo ngày + kế hoạch năm — đơn vị thành viên hoặc chuyên viên có quyền `unit_daily` */}
                  <Route path="/bao-cao-thu-mua" element={
                    <UnitDailyRoute kind="purchase" title="Báo cáo thu mua"
                      subtitle="Sản lượng & đơn giá thu mua mủ nguyên liệu theo ngày." />} />
                  <Route path="/bao-cao-tieu-thu" element={
                    <UnitDailyRoute kind="consumption" defaultTab="sales" title="Báo cáo tiêu thụ"
                      subtitle="Sản lượng tiêu thụ theo hợp đồng, giá bán và doanh thu theo ngày." />} />
                  <Route path="/bao-cao-ton-kho" element={
                    <UnitDailyRoute kind="consumption" defaultTab="stock" title="Báo cáo tồn kho"
                      subtitle="Tồn kho thành phẩm (đã/chưa có hợp đồng) và tồn kho nguyên liệu theo ngày." />} />
                  <Route path="/ke-hoach-nam" element={<YearPlanRoute />} />
                  <Route path="/bao-cao-tong-hop" element={<PeriodReportRoute />} />
                  {/* Đường dẫn cũ → giữ cho link đã lưu */}
                  <Route path="/bao-cao-tieu-thu-ton-kho" element={<Navigate to="/bao-cao-tieu-thu" replace />} />
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
                  <Route element={<RequireCap caps={["assistant"]} />}>
                    <Route path="/tro-ly-ai" element={<AssistantPage />} />
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
