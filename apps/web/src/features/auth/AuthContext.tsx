import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { type User, fetchMe, impersonateUser, login as apiLogin } from "../../lib/auth-client";
import {
  clearAdminToken, clearToken, getAdminToken, getToken, setAdminToken, setToken,
} from "../../lib/auth-token";
import { clearSessionProposals } from "../../lib/floor-proposal-client";
import { type Cap, effectiveCaps, hasCap } from "../../lib/permissions";
import ImpersonationBanner from "./ImpersonationBanner";

type AuthCtx = {
  user: User | null;
  loading: boolean;
  canEdit: boolean; // admin hoặc editor (chuyên viên nhập liệu) — viewer = chỉ xem
  // Tài khoản GẮN ĐƠN VỊ (nhập liệu `member` + lãnh đạo `leader`): dùng bộ endpoint /api/member/*
  // và chỉ thấy đơn vị được gán. Khớp `UNIT_ROLES` ở backend.
  isUnitAccount: boolean;
  // Trong nhóm trên, chỉ `member` được nhập/sửa; lãnh đạo đơn vị CHỈ XEM (server cũng chặn).
  canEditUnitData: boolean;
  can: (cap: Cap) => boolean; // TRUY CẬP mục dữ liệu (mức Xem trở lên) — dùng cho menu + gác route
  canEditCap: (cap: Cap) => boolean; // được NHẬP/SỬA mục dữ liệu (mức Sửa) — dùng để khoá form/nút
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isImpersonating: boolean; // đang xem với tư cách tài khoản khác (admin đăng nhập hộ)
  impersonate: (username: string) => Promise<void>;
  stopImpersonation: () => Promise<void>;
};

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);
export const useAuth = () => useContext(Ctx);

/** Quản lý phiên đăng nhập: khôi phục từ token localStorage, login/logout. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    fetchMe()
      .then((u) => { if (!u) clearToken(); setUser(u); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const r = await apiLogin(username, password);
    setToken(r.access_token);
    setUser(r.user);
  };
  const logout = () => { clearToken(); clearAdminToken(); clearSessionProposals(); setUser(null); };
  const refreshUser = async () => { setUser(await fetchMe()); };
  const canEdit = user?.role === "admin" || user?.role === "editor";
  const isUnitAccount = user?.role === "member" || user?.role === "leader";
  const canEditUnitData = user?.role === "member";
  const caps = useMemo(() => effectiveCaps(user?.role, user?.permissions), [user?.role, user?.permissions]);
  const can = (cap: Cap) => hasCap(caps, cap);
  const canEditCap = (cap: Cap) => hasCap(caps, cap, "edit");

  /** Admin đăng nhập hộ tài khoản khác: cất token admin hiện tại rồi chuyển sang token tài khoản đích. */
  const impersonate = async (username: string) => {
    const adminToken = getToken();
    const r = await impersonateUser(username);
    if (adminToken) setAdminToken(adminToken);
    setToken(r.access_token);
    setUser(r.user);
  };

  /** Thoát phiên đăng nhập hộ: khôi phục token admin gốc + nạp lại thông tin user. */
  const stopImpersonation = async () => {
    const adminToken = getAdminToken();
    if (!adminToken) return;
    clearAdminToken();
    setToken(adminToken);
    setUser(await fetchMe());
  };

  const isImpersonating = Boolean(user?.impersonated_by);

  return (
    <Ctx.Provider value={{
      user, loading, canEdit, isUnitAccount, canEditUnitData, can, canEditCap, login, logout, refreshUser,
      isImpersonating, impersonate, stopImpersonation,
    }}>
      <ImpersonationBanner />
      {children}
    </Ctx.Provider>
  );
}
