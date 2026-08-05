import { LoginOutlined } from "@ant-design/icons";
import { Dropdown, Popconfirm, Tooltip, message } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { type AppUser, listUsers } from "../../../../lib/user-client";
import { useAuth } from "../../../auth/AuthContext";

/** Danh sách tài khoản tải MỘT LẦN cho cả bảng: mỗi dòng đơn vị tự gọi thì 67 đơn vị = 67 lượt gọi
 *  y hệt nhau. Cache ở cấp module, không phải state của từng nút. */
let cache: Promise<AppUser[]> | null = null;
const memberAccounts = () => (cache ??= listUsers());

/** Nút ĐĂNG NHẬP HỘ tài khoản của một đơn vị — chỉ admin thấy.
 *
 *  Trước đây muốn vào tài khoản đơn vị phải sang màn Tài khoản rồi dò theo tên đăng nhập (là email,
 *  không gợi ra tên đơn vị). Nút này đi thẳng từ dòng đơn vị; đơn vị có nhiều tài khoản thì chọn
 *  trong danh sách xổ xuống. */
export default function UnitLoginButton({ unit }: { unit: string }) {
  const { user: me, impersonate } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState<AppUser[] | null>(null);

  useEffect(() => {
    if (me?.role === "admin") memberAccounts().then(setUsers).catch(() => setUsers([]));
  }, [me?.role]);

  if (me?.role !== "admin") return null;

  const accounts = (users ?? []).filter(
    (u) => u.role === "member" && u.is_active && (u.member_units ?? []).includes(unit));

  const go = async (username: string) => {
    try {
      await impersonate(username);
      message.success(`Đang xem với tư cách ${username}`);
      navigate("/");
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
  };

  if (!users) return <span style={{ color: "var(--muted)", fontSize: 12 }}>…</span>;
  if (!accounts.length) {
    return <span style={{ color: "var(--muted)", fontSize: 12 }}>chưa có tài khoản</span>;
  }
  // Một tài khoản: bấm là vào luôn (vẫn hỏi lại — đang mạo danh thì mọi thao tác ghi mang tên đơn vị).
  if (accounts.length === 1) {
    return (
      <Tooltip title={`Đăng nhập hộ ${accounts[0].username}`}>
        <Popconfirm title={`Đăng nhập với tư cách "${accounts[0].username}"?`}
          description="Bạn sẽ thấy đúng giao diện và quyền của đơn vị; thoát bằng nút trên thanh cảnh báo."
          okText="Đăng nhập" cancelText="Huỷ" onConfirm={() => go(accounts[0].username)}>
          <button className="btn" style={{ whiteSpace: "nowrap" }}>
            <LoginOutlined /> Đăng nhập hộ
          </button>
        </Popconfirm>
      </Tooltip>
    );
  }
  return (
    <Dropdown menu={{
      items: accounts.map((u) => ({ key: u.username, label: u.username, onClick: () => go(u.username) })),
    }}>
      <button className="btn" style={{ whiteSpace: "nowrap" }}>
        <LoginOutlined /> Đăng nhập hộ ({accounts.length})
      </button>
    </Dropdown>
  );
}
