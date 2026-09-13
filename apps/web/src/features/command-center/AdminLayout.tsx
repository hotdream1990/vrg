import {
  IdcardOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Avatar, Dropdown, Layout, Menu, Typography } from "antd";
import { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";

import { VRG } from "../../theme";
import { useAuth } from "../auth/AuthContext";
import { IMPERSONATION_BANNER_HEIGHT } from "../auth/ImpersonationBanner";
import MemberChecklistBanner from "./sections/MemberChecklistBanner";
import MemberDataLockBanner from "./sections/MemberDataLockBanner";
import { DEFAULT_OPEN_KEYS, buildSidebarMenu } from "./sidebar-menu-builders";

const { Header, Sider, Content, Footer } = Layout;

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

  const isMember = user?.role === "member";
  const menuItems = buildSidebarMenu(user, can);

  const ROUTE_KEYS = [
    "/quet-da-san",
    "/quan-ly-so-lieu/bang-gia-san", "/quan-ly-so-lieu/ty-gia", "/quan-ly-so-lieu/gia-san-tap-doan",
    "/quan-ly-so-lieu/gia-mu-nguyen-lieu", "/quan-ly-so-lieu/gia-physical",
    "/quan-ly-so-lieu/ton-kho", "/quan-ly-so-lieu/bao-gia-mu", "/quan-ly-so-lieu/don-vi-thanh-vien",
    "/nhu-cau-thi-truong", "/bao-cao-thu-mua", "/bao-cao-tieu-thu", "/bao-cao-ton-kho",
    // Các mục con phải đứng TRƯỚC "/hop-dong" — khớp tiền tố sẽ nuốt mục con.
    "/hop-dong/khach-hang", "/hop-dong/hop-dong-me", "/hop-dong",
    "/thong-ke-hop-dong", "/ke-hoach-nam", "/bao-cao-tong-hop",
    "/thong-ke/tinh-trang-nop", "/thong-ke/thu-mua", "/thong-ke/tieu-thu", "/thong-ke/ton-kho",
    "/ho-tro/nhac-lich", "/ho-tro",
    "/goi-y-gia-san", "/ban-tin-bien-dong", "/tro-ly-ai/lich-su", "/tro-ly-ai",
    "/ban-tin/tuan", "/ban-tin", "/quan-tri/nguoi-dung", "/quan-tri/cau-hinh",
    "/quan-tri/lich-chay", "/quan-tri/nhat-ky", "/canh-bao-bat-thuong", "/ho-so",
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
          selectedKeys={[selected]}
          defaultOpenKeys={DEFAULT_OPEN_KEYS}
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
          {/* Nhắc việc của đơn vị đặt Ở ĐÂY (khung), không ở từng trang: đơn vị vào màn nào cũng
              thấy ngay mình còn nợ số liệu ngày nào. */}
          {/* Yêu cầu chốt số liệu đứng TRÊN bảng nhắc việc: đây là việc có hạn của Ban TTKD,
              còn bảng nhắc là việc thường ngày. */}
          {isMember && <MemberDataLockBanner />}
          {isMember && <MemberChecklistBanner />}
          <main className="main"><Outlet /></main>
        </Content>
        <Footer style={{ textAlign: "center", color: "#5f6f67", fontSize: 12, padding: "12px 24px" }}>
          VRG · Command Center v{__APP_VERSION__} (PoC) — Bizino AI × Thái Hưng Infotech
        </Footer>
      </Layout>
    </Layout>
  );
}
