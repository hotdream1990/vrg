import {
  BankOutlined,
  BulbOutlined,
  ClockCircleOutlined,
  DashboardOutlined,
  EditOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FundOutlined,
  IdcardOutlined,
  InboxOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
  SafetyOutlined,
  SettingOutlined,
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

import { VRG } from "../../theme";
import { useAuth } from "../auth/AuthContext";

const { Header, Sider, Content, Footer } = Layout;

const MENU = [
  { key: "/", icon: <DashboardOutlined />, label: "Dashboard" },
  { key: "/quet-da-san", icon: <ThunderboltOutlined />, label: "Quét Đa sàn" },
  {
    key: "data-auto", icon: <RobotOutlined />, label: "Quản lý số liệu (tự động)",
    children: [
      { key: "/quan-ly-so-lieu/bang-gia-san", icon: <TableOutlined />, label: "Bảng tính giá các sàn" },
      { key: "/quan-ly-so-lieu/ty-gia", icon: <SwapOutlined />, label: "Tỷ giá" },
    ],
  },
  {
    key: "data-manual", icon: <EditOutlined />, label: "Quản lý số liệu (thủ công)",
    children: [
      { key: "/quan-ly-so-lieu/gia-san-tap-doan", icon: <BankOutlined />, label: "Giá sàn Tập đoàn" },
      { key: "/quan-ly-so-lieu/gia-mu-nguyen-lieu", icon: <ExperimentOutlined />, label: "Giá mủ nguyên liệu" },
      { key: "/quan-ly-so-lieu/gia-physical", icon: <FundOutlined />, label: "Giá Physical" },
      { key: "/quan-ly-so-lieu/ton-kho", icon: <InboxOutlined />, label: "Tồn kho" },
      { key: "/quan-ly-so-lieu/don-vi-thanh-vien", icon: <TeamOutlined />, label: "Đơn vị thành viên" },
    ],
  },
  { key: "/goi-y-gia-san", icon: <BulbOutlined />, label: "Gợi ý giá sàn" },
  { key: "/ban-tin", icon: <FileTextOutlined />, label: "Bản tin ngày" },
];

// Mục Quản trị chỉ hiện với role=admin.
const ADMIN_MENU = {
  key: "admin", icon: <SafetyOutlined />, label: "Quản trị",
  children: [
    { key: "/quan-tri/nguoi-dung", icon: <UsergroupAddOutlined />, label: "Người dùng" },
    { key: "/quan-tri/cau-hinh", icon: <SettingOutlined />, label: "Cấu hình hệ thống" },
    { key: "/quan-tri/lich-chay", icon: <ClockCircleOutlined />, label: "Lịch chạy" },
  ],
};

/** Khung admin: Sider thu gọn + Menu icon vector + Header (user/logout) + nội dung route. */
export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [broken, setBroken] = useState(false); // true = màn hẹp (mobile): Sider thành overlay
  const nav = useNavigate();
  const { pathname } = useLocation();
  const { user, logout } = useAuth();

  const isAdmin = user?.role === "admin";
  const menuItems = isAdmin ? [...MENU, ADMIN_MENU] : MENU;

  const ROUTE_KEYS = [
    "/quet-da-san",
    "/quan-ly-so-lieu/bang-gia-san", "/quan-ly-so-lieu/ty-gia", "/quan-ly-so-lieu/gia-san-tap-doan",
    "/quan-ly-so-lieu/gia-mu-nguyen-lieu", "/quan-ly-so-lieu/gia-physical",
    "/quan-ly-so-lieu/ton-kho", "/quan-ly-so-lieu/don-vi-thanh-vien",
    "/goi-y-gia-san", "/ban-tin", "/quan-tri/nguoi-dung", "/quan-tri/cau-hinh",
    "/quan-tri/lich-chay", "/ho-so",
  ];
  const selected = pathname === "/"
    ? "/"
    : (ROUTE_KEYS.find((k) => pathname === k || pathname.startsWith(k + "/")) ?? pathname);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        collapsible trigger={null} width={288}
        breakpoint="lg" collapsedWidth={broken ? 0 : 80}
        collapsed={collapsed}
        onCollapse={setCollapsed}
        onBreakpoint={(b) => { setBroken(b); setCollapsed(b); }}
        style={broken
          ? { position: "fixed", height: "100vh", top: 0, left: 0, zIndex: 1000 }
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
