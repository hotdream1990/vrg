import { App as AntApp, ConfigProvider } from "antd";
import viVN from "antd/locale/vi_VN";
import "dayjs/locale/vi";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import AdminLayout from "./features/command-center/AdminLayout";
import AssistantHistoryPage from "./features/command-center/pages/AssistantHistoryPage";
import AssistantPage from "./features/command-center/pages/AssistantPage";
import AuditLogPage from "./features/command-center/pages/AuditLogPage";
import BulletinDetailPage from "./features/command-center/pages/BulletinDetailPage";
import BulletinListPage from "./features/command-center/pages/BulletinListPage";
import BulletinPage from "./features/command-center/pages/BulletinPage";
import ConsumptionReportPage from "./features/command-center/pages/ConsumptionReportPage";
import CustomerPage from "./features/command-center/pages/CustomerPage";
import DashboardPage from "./features/command-center/pages/DashboardPage";
import EntryWarnPreview from "./features/command-center/pages/EntryWarnPreview";
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
import SupportPage from "./features/command-center/pages/SupportPage";
import SupportBatchPage from "./features/command-center/pages/SupportBatchPage";
import SupportThreadPage from "./features/command-center/pages/SupportThreadPage";
import SupportReminderPage from "./features/command-center/pages/SupportReminderPage";
import DataLockPage from "./features/command-center/pages/DataLockPage";
import MasterContractPage from "./features/command-center/pages/MasterContractPage";
import SalesContractPage from "./features/command-center/pages/SalesContractPage";
import ScanPage from "./features/command-center/pages/ScanPage";
import SchedulePage from "./features/command-center/pages/SchedulePage";
import StockContractHistoryPage from "./features/command-center/pages/StockContractHistoryPage";
import SystemConfigPage from "./features/command-center/pages/SystemConfigPage";
import PeriodReportPage from "./features/command-center/pages/PeriodReportPage";
import ConsumptionStatsPage from "./features/command-center/pages/analytics/ConsumptionStatsPage";
import PurchaseStatsPage from "./features/command-center/pages/analytics/PurchaseStatsPage";
import StockStatsPage from "./features/command-center/pages/analytics/StockStatsPage";
import SubmissionStatusPage from "./features/command-center/pages/analytics/SubmissionStatusPage";
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

/** Trang chủ: đơn vị thành viên → biểu nhập đầu tiên của họ (Thu mua nếu có giao KH, không thì Tồn kho); còn lại → Dashboard. */
function HomeRoute() {
  const { user } = useAuth();
  if (user?.role === "leader") return <Navigate to="/ho-tro" replace />;
  if (user?.role === "member") {
    return <Navigate to={user.member_has_purchase_plan ? "/bao-cao-thu-mua" : "/bao-cao-ton-kho"} replace />;
  }
  return <DashboardPage />;
}

/** Quản lý hợp đồng (khách hàng · hợp đồng & đợt giao): tài khoản đơn vị (nhập liệu + lãnh đạo)
 *  → đơn vị mình; chuyên viên có quyền `sales_contract` → mọi đơn vị. */
function ContractRoute({ children }: { children: React.ReactNode }) {
  const { isUnitAccount, can } = useAuth();
  if (isUnitAccount || can("sales_contract")) return <>{children}</>;
  return <Navigate to="/" replace />;
}

/** Hỗ trợ & Thông báo: lãnh đạo đơn vị (role=leader) hoặc tài khoản có quyền `support`.
 *  Tài khoản `member` (nhập liệu) KHÔNG vào — hộp thư này chỉ dành cho lãnh đạo đơn vị. */
function SupportRoute({ children }: { children: React.ReactNode }) {
  const { user, can } = useAuth();
  if (user?.role === "leader" || can("support")) return <>{children}</>;
  return <Navigate to="/" replace />;
}

/** Nhu cầu thị trường (timeline): đơn vị thành viên → chỉ đơn vị của mình; chuyên viên có quyền → mọi đơn vị. */
function MarketDemandRoute() {
  const { isUnitAccount, can } = useAuth();
  if (isUnitAccount || can("market_demand")) return <MarketDemandTimelinePage />;
  return <Navigate to="/" replace />;
}

/** Báo cáo tiêu thụ–tồn kho theo ngày: đơn vị thành viên nhập của mình; chuyên viên có quyền `unit_daily` → mọi đơn vị. */
function UnitDailyRoute(props: React.ComponentProps<typeof UnitDailyPage>) {
  const { user, can, isUnitAccount } = useAuth();
  const isMember = isUnitAccount;
  // Đơn vị thành viên KHÔNG được giao kế hoạch thu mua → không vào biểu Thu mua (kể cả gõ URL).
  if (isMember && props.kind === "purchase" && !user?.member_has_purchase_plan) {
    return <Navigate to="/bao-cao-ton-kho" replace />;
  }
  if (isMember || can("unit_daily")) return <UnitDailyPage {...props} />;
  return <Navigate to="/" replace />;
}

/** Báo cáo tổng hợp theo kỳ — CHỈ admin / người được cấp quyền `unit_daily` (đơn vị thành viên KHÔNG xem). */
function PeriodReportRoute() {
  const { can } = useAuth();
  if (can("unit_daily")) return <PeriodReportPage />;
  return <Navigate to="/" replace />;
}

/** Kế hoạch năm (số liệu nhập 1 lần/năm): đơn vị thành viên → đơn vị mình; chuyên viên có quyền → mọi đơn vị. */
function YearPlanRoute() {
  const { can, isUnitAccount } = useAuth();
  const isMember = isUnitAccount;
  // Mở cho MỌI đơn vị thành viên, không phụ thuộc kế hoạch thu mua đã khai hay chưa: số khai ở đây
  // mới là công tắc bật màn Thu mua, chặn ở đây thì đơn vị chưa khai bị kẹt không lối ra.
  if (isMember || can("unit_daily")) return <YearPlanPage />;
  return <Navigate to="/" replace />;
}

/** Thống kê hợp đồng (tra cứu, kể cả đã giao): đơn vị thành viên → đơn vị mình; chuyên viên có quyền → mọi đơn vị. */
function StockContractHistoryRoute() {
  const { isUnitAccount, can } = useAuth();
  if (isUnitAccount || can("unit_daily")) return <StockContractHistoryPage />;
  return <Navigate to="/" replace />;
}

export default function App() {
  return (
    // locale vi_VN: lịch chọn ngày hiện Tháng/Thứ tiếng Việt thay vì "Jul 2026 / Su Mo Tu".
    <ConfigProvider theme={vrgTheme} locale={viVN}>
      <AntApp>
        <BrowserRouter>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              {/* CÔNG KHAI — đơn vị thành viên nhập giá mủ (gác bằng mật khẩu riêng, ngoài đăng nhập) */}
              <Route path="/nhap-gia-mu" element={<PublicPurchaseInputPage />} />
              {/* Xem thử giao diện cảnh báo nhập liệu — CHỈ DEV, bản production chuyển về trang chủ. */}
              <Route path="/xem-thu-canh-bao"
                element={import.meta.env.DEV ? <EntryWarnPreview /> : <Navigate to="/" replace />} />
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
                  <Route path="/bao-cao-ton-kho" element={
                    <UnitDailyRoute kind="consumption" defaultTab="stock" title="Báo cáo tồn kho"
                      subtitle="Tồn kho thành phẩm và tồn kho nguyên liệu theo ngày." />} />
                  {/* Tiêu thụ KHÔNG còn biểu nhập — số tính từ các lần giao trên hợp đồng */}
                  <Route path="/bao-cao-tieu-thu" element={
                    <ContractRoute><ConsumptionReportPage /></ContractRoute>} />
                  {/* Quản lý hợp đồng — khách hàng riêng từng đơn vị + hợp đồng 2 cấp */}
                  <Route path="/hop-dong/khach-hang" element={
                    <ContractRoute><CustomerPage /></ContractRoute>} />
                  <Route path="/hop-dong/hop-dong-me" element={
                    <ContractRoute><MasterContractPage /></ContractRoute>} />
                  <Route path="/hop-dong" element={
                    <ContractRoute><SalesContractPage /></ContractRoute>} />
                  {/* Hỗ trợ & Thông báo — mục con đứng TRƯỚC "/ho-tro/:id" để khỏi bị nuốt mất */}
                  <Route path="/ho-tro" element={<SupportRoute><SupportPage /></SupportRoute>} />
                  <Route path="/ho-tro/nhac-lich" element={
                    <SupportRoute><SupportReminderPage /></SupportRoute>} />
                  <Route path="/ho-tro/dot/:batchId" element={
                    <SupportRoute><SupportBatchPage /></SupportRoute>} />
                  <Route path="/ho-tro/:id" element={<SupportRoute><SupportThreadPage /></SupportRoute>} />
                  <Route path="/ke-hoach-nam" element={<YearPlanRoute />} />
                  <Route path="/bao-cao-tong-hop" element={<PeriodReportRoute />} />
                  <Route path="/thong-ke-hop-dong" element={<StockContractHistoryRoute />} />
                  {/* Thống kê / kiểm tra số liệu đơn vị đã nhập — CHỈ chuyên viên có quyền `unit_daily` */}
                  <Route element={<RequireCap caps={["unit_daily"]} />}>
                    <Route path="/thong-ke/thu-mua" element={<PurchaseStatsPage />} />
                    <Route path="/thong-ke/tieu-thu" element={<ConsumptionStatsPage />} />
                    <Route path="/thong-ke/ton-kho" element={<StockStatsPage />} />
                    <Route path="/thong-ke/tinh-trang-nop" element={<SubmissionStatusPage />} />
                    {/* Chốt số liệu: Ban TTKD theo dõi; riêng thao tác phát đợt/khoá/mở là của
                        quản trị — trang tự ẩn các nút đó, server chặn bằng require_admin. */}
                    <Route path="/chot-so-lieu" element={<DataLockPage />} />
                  </Route>
                  {/* Đường dẫn cũ → giữ cho link đã lưu */}
                  <Route path="/bao-cao-tieu-thu-ton-kho" element={<Navigate to="/bao-cao-ton-kho" replace />} />
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
                    <Route path="/tro-ly-ai/lich-su" element={<AssistantHistoryPage />} />
                    <Route path="/tro-ly-ai" element={<AssistantPage />} />
                  </Route>
                  {/* Nhật ký hoạt động — admin (mặc định đủ quyền) hoặc tài khoản được cấp quyền `audit` */}
                  <Route element={<RequireCap caps={["audit"]} />}>
                    <Route path="/quan-tri/nhat-ky" element={<AuditLogPage />} />
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
