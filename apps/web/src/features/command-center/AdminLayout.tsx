import {
  ApartmentOutlined,
  AuditOutlined,
  BankOutlined,
  BulbOutlined,
  ClockCircleOutlined,
  DashboardOutlined,
  EditOutlined,
  ExperimentOutlined,
  FileDoneOutlined,
  FileTextOutlined,
  FundOutlined,
  HistoryOutlined,
  IdcardOutlined,
  InboxOutlined,
  LineChartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  SafetyOutlined,
  ProfileOutlined,
  ScheduleOutlined,
  SettingOutlined,
  SolutionOutlined,
  SwapOutlined,
  TableOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UsergroupAddOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Dropdown, Layout, Menu, Typography } from "antd";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import type { Cap } from "../../lib/permissions";
import { VRG } from "../../theme";
import { useAuth } from "../auth/AuthContext";
import { IMPERSONATION_BANNER_HEIGHT } from "../auth/ImpersonationBanner";

const { Header, Sider, Content, Footer } = Layout;

/** Menu động theo quyền: chỉ hiện mục mà tài khoản được cấp (admin=tất cả, viewer=chỉ phần chung). */
function buildMenu(can: (cap: Cap) => boolean, isAdmin: boolean) {
  const items: NonNullable<Parameters<typeof Menu>[0]["items"]> = [
    { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  ];
  if (can("auto_data")) {
    items.push({ key: "/quet-da-san", icon: <ThunderboltOutlined />, label: "Quét Đa sàn" });
    items.push({
      key: "data-auto", icon: <RobotOutlined />, label: "Quản lý số liệu (tự động)",
      children: [
        { key: "/quan-ly-so-lieu/bang-gia-san", icon: <TableOutlined />, label: "Bảng tính giá các sàn" },
        { key: "/quan-ly-so-lieu/ty-gia", icon: <SwapOutlined />, label: "Tỷ giá" },
      ],
    });
  }
  const manual = [
    (can("market_quote") || can("raw_material")) &&
      { key: "/quan-ly-so-lieu/bao-gia-mu", icon: <SolutionOutlined />, label: "Báo giá mủ thị trường" },
    can("floor") && { key: "/quan-ly-so-lieu/gia-san-tap-doan", icon: <BankOutlined />, label: "Giá sàn Tập đoàn" },
    can("raw_material") && { key: "/quan-ly-so-lieu/gia-mu-nguyen-lieu", icon: <ExperimentOutlined />, label: "Giá mủ nguyên liệu" },
    can("physical") && { key: "/quan-ly-so-lieu/gia-physical", icon: <FundOutlined />, label: "Giá Physical" },
    can("inventory") && { key: "/quan-ly-so-lieu/ton-kho", icon: <InboxOutlined />, label: "Tồn kho" },
    can("member_unit") && { key: "/quan-ly-so-lieu/don-vi-thanh-vien", icon: <TeamOutlined />, label: "Đơn vị thành viên" },
    can("unit_daily") && { key: "/bao-cao-thu-mua", icon: <ScheduleOutlined />, label: "Báo cáo thu mua" },
    can("unit_daily") && { key: "/bao-cao-tieu-thu", icon: <ScheduleOutlined />, label: "Báo cáo tiêu thụ" },
    can("unit_daily") && { key: "/bao-cao-ton-kho", icon: <InboxOutlined />, label: "Báo cáo tồn kho" },
    can("unit_daily") && { key: "/thong-ke-hop-dong", icon: <HistoryOutlined />, label: "Thống kê hợp đồng" },
    can("market_demand") && { key: "/nhu-cau-thi-truong", icon: <ApartmentOutlined />, label: "Nhu cầu thị trường" },
    can("unit_daily") && { key: "/ke-hoach-nam", icon: <ProfileOutlined />, label: "Kế hoạch năm" },
    can("unit_daily") && { key: "/bao-cao-tong-hop", icon: <FileDoneOutlined />, label: "Báo cáo tổng hợp" },
  ].filter(Boolean) as NonNullable<Parameters<typeof Menu>[0]["items"]>;
  if (manual.length) {
    items.push({ key: "data-manual", icon: <EditOutlined />, label: "Quản lý số liệu (thủ công)", children: manual });
  }
  // Các màn phân tích/bản tin — hiện theo quyền (admin=tất cả, editor=được-cấp, viewer=không).
  const analysis = [
    can("floor_suggest") && { key: "/goi-y-gia-san", icon: <BulbOutlined />, label: "Gợi ý giá sàn" },
    can("bulletin_daily") && { key: "/ban-tin", icon: <FileTextOutlined />, label: "Bản tin ngày" },
    can("bulletin_weekly") && { key: "/ban-tin/tuan", icon: <FileDoneOutlined />, label: "Báo cáo tuần" },
    can("market_movement") && { key: "/ban-tin-bien-dong", icon: <LineChartOutlined />, label: "Bản tin biến động" },
    can("assistant") && { key: "/tro-ly-ai", icon: <RobotOutlined />, label: "Trợ lý AI" },
    // Admin đã có mục này trong nhóm Quản trị → chỉ hiện ở đây cho tài khoản được CẤP quyền.
    !isAdmin && can("audit") && { key: "/quan-tri/nhat-ky", icon: <AuditOutlined />, label: "Nhật ký hoạt động" },
  ].filter(Boolean) as NonNullable<Parameters<typeof Menu>[0]["items"]>;
  items.push(...analysis);
  return items;
}

// Mục Quản trị chỉ hiện với role=admin.
const ADMIN_MENU = {
  key: "admin", icon: <SafetyOutlined />, label: "Quản trị",
  children: [
    { key: "/quan-tri/nguoi-dung", icon: <UsergroupAddOutlined />, label: "Người dùng" },
    { key: "/quan-tri/nhat-ky", icon: <AuditOutlined />, label: "Nhật ký hoạt động" },
    { key: "/quan-tri/cau-hinh", icon: <SettingOutlined />, label: "Cấu hình hệ thống" },
    { key: "/quan-tri/lich-chay", icon: <ClockCircleOutlined />, label: "Lịch chạy" },
  ],
};

// Menu cho tài khoản Đơn vị thành viên: 3 báo cáo theo ngày + số liệu năm.
// Giá thu mua nhập thẳng trong biểu "Báo cáo thu mua" nên không còn mục riêng.
const MEMBER_MENU = [
  {
    key: "data-manual", icon: <EditOutlined />, label: "Quản lý số liệu (thủ công)",
    children: [
      { key: "/bao-cao-thu-mua", icon: <ScheduleOutlined />, label: "Báo cáo thu mua" },
      { key: "/bao-cao-tieu-thu", icon: <ScheduleOutlined />, label: "Báo cáo tiêu thụ" },
      { key: "/bao-cao-ton-kho", icon: <InboxOutlined />, label: "Báo cáo tồn kho" },
      { key: "/thong-ke-hop-dong", icon: <HistoryOutlined />, label: "Thống kê hợp đồng" },
      { key: "/nhu-cau-thi-truong", icon: <ApartmentOutlined />, label: "Nhu cầu thị trường" },
      { key: "/ke-hoach-nam", icon: <ProfileOutlined />, label: "Kế hoạch năm" },
    ],
  },
];

// Mục Hồ sơ cá nhân (đổi mật khẩu) — hiện cuối sidebar cho mọi vai trò.
const PROFILE_ITEM = { key: "/ho-so", icon: <IdcardOutlined />, label: "Hồ sơ cá nhân" };

/** Khung admin: Sider thu gọn + Menu icon vector + Header (user/logout) + nội dung route. */
export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [broken, setBroken] = useState(false); // true = màn hẹp (mobile): Sider thành overlay
  const nav = useNavigate();
  const { pathname } = useLocation();
  const { user, logout, can, isImpersonating } = useAuth();

  // Đang đăng nhập hộ → thanh cảnh báo cố định chiếm phần trên, khung admin lùi xuống đúng chừng đó.
  const bannerH = isImpersonating ? IMPERSONATION_BANNER_HEIGHT : 0;
  const frameHeight = `calc(100vh - ${bannerH}px)`;

  const isAdmin = user?.role === "admin";
  const isMember = user?.role === "member";
  const menuItems = isMember
    ? [...MEMBER_MENU, PROFILE_ITEM]
    : [...buildMenu(can, isAdmin), ...(isAdmin ? [ADMIN_MENU] : []), PROFILE_ITEM];

  const ROUTE_KEYS = [
    "/quet-da-san",
    "/quan-ly-so-lieu/bang-gia-san", "/quan-ly-so-lieu/ty-gia", "/quan-ly-so-lieu/gia-san-tap-doan",
    "/quan-ly-so-lieu/gia-mu-nguyen-lieu", "/quan-ly-so-lieu/gia-physical",
    "/quan-ly-so-lieu/ton-kho", "/quan-ly-so-lieu/bao-gia-mu", "/quan-ly-so-lieu/don-vi-thanh-vien",
    "/nhu-cau-thi-truong", "/bao-cao-thu-mua", "/bao-cao-tieu-thu", "/bao-cao-ton-kho",
    "/thong-ke-hop-dong", "/ke-hoach-nam",
    "/goi-y-gia-san", "/ban-tin-bien-dong", "/tro-ly-ai", "/ban-tin/tuan", "/ban-tin", "/quan-tri/nguoi-dung", "/quan-tri/cau-hinh",
    "/quan-tri/lich-chay", "/quan-tri/nhat-ky", "/ho-so",
  ];
  const selected = pathname === "/"
    ? "/"
    : (ROUTE_KEYS.find((k) => pathname === k || pathname.startsWith(k + "/")) ?? pathname);

  return (
    // Khóa chiều cao = viewport + ẩn tràn để menu sidebar dài KHÔNG kéo giãn cả trang
    // (menu tự cuộn trong Sider, nội dung cuộn trong Content) — xem CSS .ant-layout-sider .ant-menu.
    <Layout style={{ height: frameHeight, marginTop: bannerH, overflow: "hidden" }}>
      <Sider
        collapsible trigger={null} width={288}
        breakpoint="lg" collapsedWidth={broken ? 0 : 80}
        collapsed={collapsed}
        onCollapse={setCollapsed}
        onBreakpoint={(b) => { setBroken(b); setCollapsed(b); }}
        style={broken
          ? { position: "fixed", height: frameHeight, top: bannerH, left: 0, zIndex: 1000 }
          : undefined}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 14px 12px" }}>
          <div style={{
            width: 40, height: 40, borderRadius: "50%", flex: "0 0 auto", background: "#fff",
            display: "grid", placeItems: "center", overflow: "hidden", boxShadow: "0 0 0 1px #ffffff33",
          }}>
            <img src="/logo-vrg.png" alt="VRG" style={{ width: 34, height: 34, objectFit: "contain" }} />
          </div>
          {!collapsed && (
            <div style={{ lineHeight: 1.2, overflow: "hidden" }}>
              <div style={{ fontWeight: 700, color: "#fff", whiteSpace: "nowrap" }}>VRG Command</div>
              <div style={{ fontSize: 11, color: "#bfe3cd", whiteSpace: "nowrap" }}>Rubber Price Intelligence</div>
            </div>
          )}
        </div>
        <Menu
          theme="dark" mode="inline"
          selectedKeys={[selected]} defaultOpenKeys={["data-auto", "data-manual", "admin"]}
          items={menuItems}
          onClick={(e) => { nav(e.key); if (broken) setCollapsed(true); }}
        />
      </Sider>

      {/* Backdrop: chỉ hiện khi mở Sider trên mobile (overlay) */}
      {broken && !collapsed && (
        <div
          onClick={() => setCollapsed(true)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 999 }}
        />
      )}

      <Layout>
        <Header style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: broken ? "0 14px" : "0 24px", borderBottom: "1px solid #e3e9e4" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
            <span onClick={() => setCollapsed((c) => !c)}
              style={{ fontSize: 18, cursor: "pointer", color: VRG.dark }}>
              {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            </span>
            {!broken && (
              <Typography.Text strong style={{ fontSize: 15, color: "#16241d" }}>
                Hệ thống Dự báo & Quản trị Giá Cao su
              </Typography.Text>
            )}
          </div>
          <Dropdown
            menu={{
              items: [
                { key: "profile", icon: <IdcardOutlined />, label: "Hồ sơ cá nhân" },
                { type: "divider" },
                { key: "logout", icon: <LogoutOutlined />, label: "Đăng xuất", danger: true },
              ],
              onClick: ({ key }) => {
                if (key === "profile") { nav("/ho-so"); return; }
                logout(); nav("/login", { replace: true });
              },
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <Avatar size="small" style={{ background: VRG.primary }} icon={<UserOutlined />} />
              {!broken && <span style={{ color: "#16241d" }}>{user?.full_name || user?.username || "Admin"}</span>}
            </div>
          </Dropdown>
        </Header>

        <Content style={{ overflow: "auto" }}>
          <main className="main"><Outlet /></main>
        </Content>
        <Footer style={{ textAlign: "center", color: "#5f6f67", fontSize: 12, padding: "12px 24px" }}>
          VRG · Command Center v{__APP_VERSION__} (PoC) — Bizino AI × Thái Hưng Infotech
        </Footer>
      </Layout>
    </Layout>
  );
}
