---
title: "Refactor web → admin site thực thụ (Ant Design + Auth JWT + theme VRG)"
description: "Biến web thành trang quản trị nội bộ: login (FastAPI JWT), layout antd (Sider thu gọn + icon vector + header user/logout), theme màu VRG (giữ nền tối, accent xanh VRG), các trang chạy trong layout mới. Dashboard giữ component demo theo style chung."
status: done
priority: P1
created: 2026-06-20
branch: feature/exchange-crawlers
---

# Admin refactor (Ant Design + Auth)

## Quyết định
- **UI**: Ant Design (antd) + @ant-design/icons. ConfigProvider `darkAlgorithm` + `colorPrimary=#16AF67` (xanh VRG). Giữ nền tối (để dashboard demo nguyên), accent đổi sang xanh VRG.
- **Màu VRG** (từ banner/logo chính thức): primary `#16AF67`, dark `#0B6B3A`, lime `#6DC850/#89CE50`, tint `#A8E1C6`.
- **Auth**: FastAPI JWT thật. Bảng `app_user`, bcrypt + pyjwt. Seed admin từ env (mặc định admin/admin dev — cảnh báo đổi). Protect các router dữ liệu. FE: AuthContext (token localStorage) + LoginPage + ProtectedRoute + gắn Bearer vào mọi client; 401 → logout.
- **Layout**: antd `Layout` (Sider collapsible + Menu icon vector + Header collapse/user/logout + Content `<Outlet/>`). Thay Sidebar/TopBar/AppLayout cũ.
- **Trang**: render trong layout mới; remap CSS var `--accent/--grad` sang xanh VRG để đồng bộ. Chuyển nội bộ bảng sang antd Table = follow-up.

## Phase 1 — Backend auth (JWT)
- [ ] deps: pyjwt, bcrypt
- [ ] config: jwt_secret, jwt_expire_minutes, admin_username/password (env, dev default + warn)
- [ ] db.py + 02-schema.sql: table app_user
- [ ] core/security.py (hash/verify, encode/decode JWT) + get_current_user dep
- [ ] services/user_repo.py (seed_admin, get, authenticate)
- [ ] schemas/auth.py + routers/auth.py (POST /api/auth/login, GET /api/auth/me)
- [ ] main.py: include auth (open) + protect data routers (Depends)
- [ ] tests auth

## Phase 2 — FE foundation
- [ ] cài antd + @ant-design/icons
- [ ] theme.ts (token VRG) + bọc ConfigProvider
- [ ] lib/auth (token storage + authHeaders + 401 handling) → gắn vào các client
- [ ] AuthContext + LoginPage + ProtectedRoute
- [ ] AdminLayout (Sider collapse + Menu vector icon + Header user/logout)
- [ ] App.tsx: /login (open) + layout bọc route bảo vệ

## Phase 3 — Tích hợp + màu
- [ ] remap command-center.css --accent/--grad → xanh VRG
- [ ] các trang chạy trong AdminLayout; bỏ Sidebar/TopBar cũ
- [ ] verify: login → dashboard → điều hướng; sider thu gọn; logout; 401

## Success
- Vào web → bị chặn về /login; đăng nhập admin → vào dashboard; sider thu gọn/mở; icon vector; màu xanh VRG; mọi API cần token. pytest · tsc · build OK.
