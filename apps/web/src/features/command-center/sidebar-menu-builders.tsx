import {
  ApartmentOutlined,
  AuditOutlined,
  BankOutlined,
  BarChartOutlined,
  BulbOutlined,
  CameraOutlined,
  CheckSquareOutlined,
  ClockCircleOutlined,
  ClusterOutlined,
  ContactsOutlined,
  ControlOutlined,
  CustomerServiceOutlined,
  DashboardOutlined,
  DeleteOutlined,
  DeploymentUnitOutlined,
  DiffOutlined,
  EditOutlined,
  ExperimentOutlined,
  ExportOutlined,
  FileDoneOutlined,
  FileProtectOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FormOutlined,
  FundOutlined,
  FundProjectionScreenOutlined,
  HistoryOutlined,
  IdcardOutlined,
  InboxOutlined,
  LineChartOutlined,
  LockOutlined,
  NotificationOutlined,
  ProfileOutlined,
  RobotOutlined,
  SafetyOutlined,
  ScheduleOutlined,
  SettingOutlined,
  ShoppingOutlined,
  SolutionOutlined,
  SwapOutlined,
  TableOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UsergroupAddOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Badge, type Menu } from "antd";

import { type User, hasEntryType } from "../../lib/auth-client";
import type { EntryType } from "../../lib/entry-types";
import type { Cap } from "../../lib/permissions";

type MenuItems = NonNullable<Parameters<typeof Menu>[0]["items"]>;

/** Nhóm menu mở sẵn khi vào trang (khớp key của các `group` bên dưới). */
export const DEFAULT_OPEN_KEYS = ["data-auto", "data-manual", "data-market", "data-unit", "contracts",
  "stats", "smart-factory", "reports", "support", "analysis", "admin"];

/** Gom một nhóm menu, tự bỏ qua khi tài khoản không được cấp mục con nào. */
function group(key: string, icon: JSX.Element, label: string, children: unknown[]): MenuItems {
  const kids = children.filter(Boolean) as MenuItems;
  return kids.length ? [{ key, icon, label, children: kids }] : [];
}

// Mục menu mức Tập đoàn dùng chung giữa menu chuyên viên/quản trị và menu Lãnh đạo Tập đoàn.
const ITEM = {
  dashboard: { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  priceBoard: { key: "/quan-ly-so-lieu/bang-gia-san", icon: <TableOutlined />, label: "Bảng tính giá các sàn" },
  fxRate: { key: "/quan-ly-so-lieu/ty-gia", icon: <SwapOutlined />, label: "Tỷ giá" },
  marketQuote: { key: "/quan-ly-so-lieu/bao-gia-mu", icon: <SolutionOutlined />, label: "Báo giá mủ thị trường" },
  floor: { key: "/quan-ly-so-lieu/gia-san-tap-doan", icon: <BankOutlined />, label: "Giá sàn Tập đoàn" },
  physical: { key: "/quan-ly-so-lieu/gia-physical", icon: <FundOutlined />, label: "Giá Physical" },
  unitPurchase: { key: "/bao-cao-thu-mua", icon: <ScheduleOutlined />, label: "Thu mua" },
  unitStock: { key: "/bao-cao-ton-kho", icon: <InboxOutlined />, label: "Tồn kho" },
  marketDemand: { key: "/nhu-cau-thi-truong", icon: <ApartmentOutlined />, label: "Nhu cầu thị trường" },
  yearPlan: { key: "/ke-hoach-nam", icon: <ProfileOutlined />, label: "Kế hoạch năm" },
  customers: { key: "/hop-dong/khach-hang", icon: <ContactsOutlined />, label: "Khách hàng" },
  masterContracts: { key: "/hop-dong/hop-dong-me", icon: <FileTextOutlined />, label: "Hợp đồng mẹ (HĐNT/HĐDH)" },
  contracts: { key: "/hop-dong", icon: <FileProtectOutlined />, label: "Hợp đồng & đợt giao" },
  consumptionReport: { key: "/bao-cao-tieu-thu", icon: <ExportOutlined />, label: "Báo cáo tiêu thụ" },
  summaryReport: { key: "/bao-cao-tong-hop", icon: <FileDoneOutlined />, label: "Báo cáo tổng hợp" },
  weekSnapshot: { key: "/snapshot-so-lieu-tuan", icon: <CameraOutlined />, label: "Snapshot số liệu tuần" },
  submission: { key: "/thong-ke/tinh-trang-nop", icon: <CheckSquareOutlined />, label: "Theo dõi nộp báo cáo" },
  unitScorecard: { key: "/chi-so-don-vi", icon: <BarChartOutlined />, label: "Chỉ số đơn vị" },
  unitDashboard: { key: "/dashboard-don-vi", icon: <FundProjectionScreenOutlined />, label: "Dashboard đơn vị" },
  statPurchase: { key: "/thong-ke/thu-mua", icon: <ShoppingOutlined />, label: "Thống kê thu mua" },
  statStock: { key: "/thong-ke/ton-kho", icon: <InboxOutlined />, label: "Thống kê tồn kho" },
  statConsumption: { key: "/thong-ke/tieu-thu", icon: <ExportOutlined />, label: "Thống kê tiêu thụ" },
  floorSuggest: { key: "/goi-y-gia-san", icon: <BulbOutlined />, label: "Gợi ý giá sàn" },
  floorDrafts: { key: "/goi-y-gia-san/ban-nhap", icon: <FormOutlined />, label: "Quy trình giá sàn" },
  bulletinDaily: { key: "/ban-tin", icon: <FileTextOutlined />, label: "Bản tin ngày" },
  bulletinWeekly: { key: "/ban-tin/tuan", icon: <FileDoneOutlined />, label: "Báo cáo tuần" },
  marketMovement: { key: "/ban-tin-bien-dong", icon: <LineChartOutlined />, label: "Bản tin biến động" },
  assistant: { key: "/tro-ly-ai", icon: <RobotOutlined />, label: "Trợ lý AI" },
  assistantHistory: { key: "/tro-ly-ai/lich-su", icon: <HistoryOutlined />, label: "Lịch sử hỏi đáp" },
  myEditRequests: { key: "/de-nghi-sua", icon: <DiffOutlined />, label: "Đề nghị sửa số liệu" },
  unitInbox: { key: "/ho-tro", icon: <CustomerServiceOutlined />, label: "Hỗ trợ & Thông báo" },
  factoryMeters: { key: "/nha-may-thong-minh/chi-so", icon: <ControlOutlined />, label: "Giám sát chỉ số" },
  plantDiagram: {
    key: "/nha-may-thong-minh/so-do-van-hanh", icon: <DeploymentUnitOutlined />, label: "Sơ đồ vận hành",
  },
};

/** "Duyệt đề nghị sửa" kèm số đề nghị đang chờ (Badge ẩn khi 0). */
const reviewEditRequestsItem = (pending: number) => ({
  key: "/duyet-de-nghi-sua", icon: <FileSearchOutlined />,
  label: (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      Duyệt đề nghị sửa <Badge count={pending} size="small" overflowCount={99} />
    </span>
  ),
});

/** Menu động theo quyền — trục mới (chốt 30/07/2026): số liệu thị trường · số liệu đơn vị ·
 *  quản lý hợp đồng · báo cáo & thống kê · phân tích & bản tin. */
function buildMenu(can: (cap: Cap) => boolean, isAdmin: boolean, pendingEditRequests: number) {
  const items: MenuItems = [ITEM.dashboard];
  if (can("auto_data")) {
    items.push({ key: "/quet-da-san", icon: <ThunderboltOutlined />, label: "Quét Đa sàn" });
  }
  items.push(...group("data-auto", <RobotOutlined />, "Số liệu thị trường (tự động)", [
    can("auto_data") && ITEM.priceBoard,
    can("auto_data") && ITEM.fxRate,
  ]));
  items.push(...group("data-manual", <EditOutlined />, "Số liệu thị trường (thủ công)", [
    can("market_quote") && ITEM.marketQuote,
    can("floor") && ITEM.floor,
    can("physical") && ITEM.physical,
    // "Giá mủ nguyên liệu" + "Tồn kho Tập đoàn" đã chuyển xuống nhóm RETIRED_MENU (chỉ admin thấy).
  ]));
  items.push(...group("data-unit", <TeamOutlined />, "Số liệu đơn vị thành viên", [
    can("member_unit") && { key: "/quan-ly-so-lieu/don-vi-thanh-vien", icon: <TeamOutlined />, label: "Đơn vị thành viên" },
    can("unit_daily") && ITEM.unitPurchase,
    can("unit_daily") && ITEM.unitStock,
    can("market_demand") && ITEM.marketDemand,
    can("unit_daily") && ITEM.yearPlan,
    can("edit_request") && reviewEditRequestsItem(pendingEditRequests),
  ]));
  items.push(...group("contracts", <FileProtectOutlined />, "Quản lý hợp đồng", [
    can("sales_contract") && ITEM.customers,
    can("sales_contract") && ITEM.masterContracts,
    can("sales_contract") && ITEM.contracts,
  ]));
  items.push(...group("stats", <BarChartOutlined />, "Báo cáo & Thống kê", [
    can("unit_daily") && ITEM.unitDashboard,
    can("unit_daily") && ITEM.unitScorecard,
    can("sales_contract") && ITEM.consumptionReport,
    can("unit_daily") && ITEM.summaryReport,
    can("unit_daily") && ITEM.weekSnapshot,
    can("unit_daily") && ITEM.submission,
    can("unit_daily") && { key: "/chot-so-lieu", icon: <LockOutlined />, label: "Chốt số liệu đơn vị" },
    // Xếp theo dòng chảy nghiệp vụ: mua vào → giữ kho → bán ra.
    can("unit_daily") && ITEM.statPurchase,
    can("unit_daily") && ITEM.statStock,
    can("unit_daily") && ITEM.statConsumption,
    // "Hợp đồng cũ (trước 30/07)" ĐÃ ẨN khỏi menu (20/08/2026) — dữ liệu và route `/thong-ke-hop-dong`
    // vẫn còn để tra cứu bằng đường dẫn, chỉ thôi bày ra cho người dùng thường.
  ]));
  items.push(...group("smart-factory", <ClusterOutlined />, "Nhà máy thông minh", [
    can("smart_factory") && ITEM.plantDiagram,
    can("smart_factory") && ITEM.factoryMeters,
    // Cấu hình kết nối SCADA nằm ở Quản trị → Cấu hình hệ thống → tab "SCADA nhà máy".
  ]));
  items.push(...group("support", <CustomerServiceOutlined />, "Hỗ trợ đơn vị thành viên", [
    can("support") && { key: "/ho-tro", icon: <NotificationOutlined />, label: "Hỗ trợ & Thông báo" },
    // Xem được hộp thư là xem được lịch nhắc; thao tác tạo/sửa/gửi vẫn cần mức Sửa (server chặn).
    can("support") && { key: "/ho-tro/nhac-lich", icon: <ScheduleOutlined />, label: "Nhắc lịch" },
  ]));
  items.push(...group("analysis", <LineChartOutlined />, "Phân tích & Bản tin", [
    can("floor_suggest") && ITEM.floorSuggest,
    can("floor_suggest") && ITEM.floorDrafts,
    can("bulletin_daily") && ITEM.bulletinDaily,
    can("bulletin_weekly") && ITEM.bulletinWeekly,
    can("market_movement") && ITEM.marketMovement,
    can("assistant") && ITEM.assistant,
    can("assistant") && ITEM.assistantHistory,
    // Admin đã có mục này trong nhóm Quản trị → chỉ hiện ở đây cho tài khoản được CẤP quyền.
    !isAdmin && can("audit") && { key: "/quan-tri/nhat-ky", icon: <AuditOutlined />, label: "Nhật ký hoạt động" },
    !isAdmin && can("audit") && { key: "/quan-tri/truy-cap", icon: <HistoryOutlined />, label: "Lịch sử truy cập" },
  ]));
  return items;
}

/** Menu LÃNH ĐẠO TẬP ĐOÀN: đưa phần lãnh đạo dùng nhiều nhất (AI · bản tin · báo cáo) lên đầu,
 *  số liệu gốc xuống dưới và ghi rõ "(chỉ xem)". Cố ý KHÔNG có: Quét Đa sàn (chạy thu thập giá),
 *  Chốt số liệu (thao tác của Ban), danh mục Đơn vị thành viên, Hỗ trợ, Nhật ký, Quản trị. */
function buildExecutiveMenu(can: (cap: Cap) => boolean) {
  return [
    ITEM.dashboard,
    ...group("analysis", <LineChartOutlined />, "Phân tích & Bản tin", [
      can("assistant") && ITEM.assistant,
      can("floor_suggest") && ITEM.floorSuggest,
      can("floor_suggest") && ITEM.floorDrafts,
      can("market_movement") && ITEM.marketMovement,
      can("bulletin_daily") && ITEM.bulletinDaily,
      can("bulletin_weekly") && ITEM.bulletinWeekly,
      can("assistant") && ITEM.assistantHistory,
    ]),
    ...group("stats", <BarChartOutlined />, "Báo cáo & Thống kê", [
      can("unit_daily") && ITEM.unitDashboard,
      can("unit_daily") && ITEM.unitScorecard,
      can("unit_daily") && ITEM.summaryReport,
      can("unit_daily") && ITEM.weekSnapshot,
      can("sales_contract") && ITEM.consumptionReport,
      can("unit_daily") && ITEM.statPurchase,
      can("unit_daily") && ITEM.statStock,
      can("unit_daily") && ITEM.statConsumption,
      can("unit_daily") && ITEM.submission,
    ]),
    ...group("smart-factory", <ClusterOutlined />, "Nhà máy thông minh", [
      can("smart_factory") && ITEM.plantDiagram,
      can("smart_factory") && ITEM.factoryMeters,
    ]),
    ...group("data-market", <FundOutlined />, "Số liệu thị trường (chỉ xem)", [
      can("auto_data") && ITEM.priceBoard,
      can("auto_data") && ITEM.fxRate,
      can("market_quote") && ITEM.marketQuote,
      can("floor") && ITEM.floor,
      can("physical") && ITEM.physical,
    ]),
    ...group("data-unit", <TeamOutlined />, "Số liệu đơn vị (chỉ xem)", [
      can("unit_daily") && ITEM.unitPurchase,
      can("unit_daily") && ITEM.unitStock,
      can("market_demand") && ITEM.marketDemand,
      can("unit_daily") && ITEM.yearPlan,
    ]),
    ...group("contracts", <FileProtectOutlined />, "Hợp đồng (chỉ xem)", [
      can("sales_contract") && ITEM.customers,
      can("sales_contract") && ITEM.masterContracts,
      can("sales_contract") && ITEM.contracts,
    ]),
  ];
}

// Mục Quản trị chỉ hiện với role=admin.
const ADMIN_MENU = {
  key: "admin", icon: <SafetyOutlined />, label: "Quản trị",
  children: [
    { key: "/quan-tri/nguoi-dung", icon: <UsergroupAddOutlined />, label: "Người dùng" },
    { key: "/canh-bao-bat-thuong", icon: <WarningOutlined />, label: "Cảnh báo bất thường" },
    { key: "/quan-tri/nhat-ky", icon: <AuditOutlined />, label: "Nhật ký hoạt động" },
    { key: "/quan-tri/truy-cap", icon: <HistoryOutlined />, label: "Lịch sử truy cập" },
    { key: "/quan-tri/cau-hinh", icon: <SettingOutlined />, label: "Cấu hình hệ thống" },
    { key: "/quan-tri/lich-chay", icon: <ClockCircleOutlined />, label: "Lịch chạy" },
  ],
};

// Menu cho tài khoản Đơn vị thành viên — trục mới: chỉ còn 2 biểu nhập theo ngày (Thu mua · Tồn kho),
// TIÊU THỤ chuyển sang tính từ hợp đồng nên nằm ở nhóm Báo cáo (chỉ xem).
// Từ 01/10/2026 mỗi tài khoản chỉ thấy màn thuộc LOẠI NHẬP LIỆU được giao (Thu mua · Tồn kho ·
// Hợp đồng & tiêu thụ); "Thu mua" còn cần đơn vị được giao kế hoạch thu mua.
function buildMemberMenu(user: User | null, hasPurchasePlan: boolean) {
  const has = (t: EntryType) => hasEntryType(user, t);
  return [
    // Bức tranh thu mua · tồn kho · tiêu thụ · chỉ tiêu của chính đơn vị (server ép đúng đơn vị).
    ITEM.unitDashboard,
    ITEM.unitInbox,
    ...group("data-manual", <EditOutlined />, "Nhập liệu số liệu", [
      has("purchase") && hasPurchasePlan
        && { key: "/bao-cao-thu-mua", icon: <ScheduleOutlined />, label: "Thu mua (theo ngày)" },
      has("stock") && { key: "/bao-cao-ton-kho", icon: <InboxOutlined />, label: "Tồn kho (theo ngày)" },
      has("contract") && { key: "/nhu-cau-thi-truong", icon: <ApartmentOutlined />, label: "Nhu cầu thị trường" },
      // Kế hoạch năm không phụ thuộc kế hoạch thu mua đã khai hay chưa: chính ô thu mua ở màn này là
      // công tắc bật màn Thu mua, khoá màn lại thì đơn vị chưa khai lần nào không bao giờ tự khai được.
      // Ô thu mua thuộc loại Thu mua, các ô còn lại thuộc Hợp đồng & tiêu thụ.
      (has("purchase") || has("contract"))
        && { key: "/ke-hoach-nam", icon: <ProfileOutlined />, label: "Kế hoạch năm" },
      // Ngày cũ đã khoá (quá hạn sửa / đã chốt) chỉ sửa được qua đề nghị Ban duyệt.
      ITEM.myEditRequests,
    ]),
    ...group("contracts", <FileProtectOutlined />, "Quản lý hợp đồng",
      has("contract") ? [ITEM.customers, ITEM.masterContracts, ITEM.contracts] : []),
    ...group("reports", <BarChartOutlined />, "Báo cáo", [
      has("contract") && { key: "/bao-cao-tieu-thu", icon: <ExportOutlined />, label: "Tiêu thụ" },
    ]),
  ];
}

// Menu tài khoản LÃNH ĐẠO ĐƠN VỊ THÀNH VIÊN: hộp thư với Tập đoàn + XEM số liệu của đơn vị mình.
// Cùng các màn của tài khoản nhập liệu nhưng ở chế độ CHỈ XEM (server chặn mọi thao tác ghi),
// nên nhãn nhóm ghi rõ "(chỉ xem)" để lãnh đạo không đi tìm nút Lưu.
function buildLeaderMenu(hasPurchasePlan: boolean) {
  return [
    ITEM.unitDashboard,
    ITEM.unitInbox,
    // Chỗ nhân viên nhập sai/thiếu — để lãnh đạo nhắc đúng việc (chỉ đơn vị mình, server tự lọc).
    { key: "/canh-bao-bat-thuong", icon: <WarningOutlined />, label: "Cảnh báo bất thường" },
    ...group("data-manual", <BarChartOutlined />, "Số liệu đơn vị (chỉ xem)", [
      hasPurchasePlan && { key: "/bao-cao-thu-mua", icon: <ScheduleOutlined />, label: "Thu mua (theo ngày)" },
      { key: "/bao-cao-ton-kho", icon: <InboxOutlined />, label: "Tồn kho (theo ngày)" },
      { key: "/nhu-cau-thi-truong", icon: <ApartmentOutlined />, label: "Nhu cầu thị trường" },
      { key: "/ke-hoach-nam", icon: <ProfileOutlined />, label: "Kế hoạch năm" },
      ITEM.myEditRequests,
    ]),
    ...group("contracts", <FileProtectOutlined />, "Hợp đồng (chỉ xem)", [
      ITEM.customers, ITEM.masterContracts, ITEM.contracts,
    ]),
    ...group("reports", <BarChartOutlined />, "Báo cáo", [
      { key: "/bao-cao-tieu-thu", icon: <ExportOutlined />, label: "Tiêu thụ" },
    ]),
  ];
}

// Menu ĐÃ BỎ khỏi trục chính (chốt 11/09/2026) — chỉ admin thấy, nhãn gạch ngang.
// Route vẫn sống để tra cứu dữ liệu cũ; người dùng thường không còn thấy lối vào.
const strike = (text: string) => (
  <span style={{ textDecoration: "line-through", opacity: 0.65 }}>{text}</span>
);
const RETIRED_MENU = {
  key: "retired", icon: <DeleteOutlined />, label: strike("Menu đã bỏ"),
  children: [
    { key: "/quan-ly-so-lieu/gia-mu-nguyen-lieu", icon: <ExperimentOutlined />, label: strike("Giá mủ nguyên liệu") },
    { key: "/quan-ly-so-lieu/ton-kho", icon: <InboxOutlined />, label: strike("Tồn kho Tập đoàn") },
  ],
};

// Mục Hồ sơ cá nhân (đổi mật khẩu) — hiện cuối sidebar cho mọi vai trò.
const PROFILE_ITEM = { key: "/ho-so", icon: <IdcardOutlined />, label: "Hồ sơ cá nhân" };

/** Menu sidebar hoàn chỉnh theo vai trò của tài khoản đang đăng nhập. */
export function buildSidebarMenu(
  user: User | null, can: (cap: Cap) => boolean, pendingEditRequests = 0,
): MenuItems {
  const role = user?.role;
  const hasPlan = user?.member_has_purchase_plan ?? false;
  if (role === "leader") return [...buildLeaderMenu(hasPlan), PROFILE_ITEM];
  if (role === "member") return [...buildMemberMenu(user, hasPlan), PROFILE_ITEM];
  if (role === "executive") return [...buildExecutiveMenu(can), PROFILE_ITEM];
  const isAdmin = role === "admin";
  return [...buildMenu(can, isAdmin, pendingEditRequests), ...(isAdmin ? [ADMIN_MENU] : []), PROFILE_ITEM,
    ...(isAdmin ? [RETIRED_MENU] : [])];
}
