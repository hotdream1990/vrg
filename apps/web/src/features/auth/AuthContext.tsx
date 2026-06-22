import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { type User, fetchMe, login as apiLogin } from "../../lib/auth-client";
import { clearToken, getToken, setToken } from "../../lib/auth-token";

type AuthCtx = {
  user: User | null;
  loading: boolean;
  canEdit: boolean; // admin hoặc editor (chuyên viên nhập liệu) — viewer = chỉ xem
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
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
  const logout = () => { clearToken(); setUser(null); };
  const refreshUser = async () => { setUser(await fetchMe()); };
  const canEdit = user?.role === "admin" || user?.role === "editor";

  return <Ctx.Provider value={{ user, loading, canEdit, login, logout, refreshUser }}>{children}</Ctx.Provider>;
}
