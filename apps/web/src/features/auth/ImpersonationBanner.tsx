import { LogoutOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useNavigate } from "react-router-dom";

import { ROLE_LABEL } from "../../lib/roles";
import { useAuth } from "./AuthContext";

/** Chiều cao thanh cảnh báo — khung admin chừa đúng khoảng này để không bị che header. */
export const IMPERSONATION_BANNER_HEIGHT = 36;

/** Thanh cảnh báo cố định trên cùng khi admin đang đăng nhập hộ (impersonation) một tài khoản khác. */
export default function ImpersonationBanner() {
  const { user, isImpersonating, stopImpersonation } = useAuth();
  const navigate = useNavigate();

  if (!isImpersonating || !user) return null;

  const back = async () => {
    await stopImpersonation();
    navigate("/quan-tri/nguoi-dung");
  };

  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 2000,
        height: IMPERSONATION_BANNER_HEIGHT, boxSizing: "border-box",
        display: "flex", alignItems: "center", justifyContent: "center", gap: 12,
        padding: "0 16px", background: "#faad14", color: "#1a1200",
        fontSize: 13, boxShadow: "0 1px 4px rgba(0,0,0,0.2)",
      }}
    >
      <span>
        Đang xem với tư cách <b>{user.full_name || user.username}</b> ({ROLE_LABEL[user.role] ?? user.role})
      </span>
      <Button size="small" icon={<LogoutOutlined />} onClick={back}>
        Quay lại tài khoản quản trị
      </Button>
    </div>
  );
}
