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
 *  trong danh sách xổ xuống.
 *
 *  `compact` = chỉ biểu tượng, dùng khi nút nằm CHEN trong ô có sẵn nội dung (ma trận theo dõi nộp
 *  báo cáo cuộn ngang, không thể thêm cột mới ở cuối vì cột đó nằm ngoài màn hình). */
export default function UnitLoginButton({ unit, compact }: { unit: string; compact?: boolean }) {
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

  // Ở chế độ compact thì im lặng khi chưa tải xong / đơn vị chưa có tài khoản — ma trận theo dõi
  // có tới 67 dòng, thêm chữ "…" hay "chưa có tài khoản" vào mỗi dòng là rối mắt.
  if (!users) return compact ? null : <span style={{ color: "var(--muted)", fontSize: 12 }}>…</span>;
  if (!accounts.length) {
    return compact ? null : <span style={{ color: "var(--muted)", fontSize: 12 }}>chưa có tài khoản</span>;
  }
  const label = (n: number) => (compact ? "" : ` Đăng nhập hộ${n > 1 ? ` (${n})` : ""}`);
  const style = compact
    ? { padding: "0 6px", lineHeight: 1.6, marginLeft: 6 }
    : { whiteSpace: "nowrap" as const };

  // Một tài khoản: bấm là vào luôn (vẫn hỏi lại — đang mạo danh thì mọi thao tác ghi mang tên đơn vị).
  if (accounts.length === 1) {
    return (
      <Tooltip title={`Đăng nhập hộ ${accounts[0].username}`}>
        <Popconfirm title={`Đăng nhập với tư cách "${accounts[0].username}"?`}
          description="Bạn sẽ thấy đúng giao diện và quyền của đơn vị; thoát bằng nút trên thanh cảnh báo."
          okText="Đăng nhập" cancelText="Huỷ" onConfirm={() => go(accounts[0].username)}>
          <button className="btn" style={style}><LoginOutlined />{label(1)}</button>
        </Popconfirm>
      </Tooltip>
    );
  }
  return (
    <Tooltip title={`${accounts.length} tài khoản — chọn tài khoản để đăng nhập hộ`}>
      <Dropdown menu={{
        items: accounts.map((u) => ({ key: u.username, label: u.username, onClick: () => go(u.username) })),
      }}>
        <button className="btn" style={style}><LoginOutlined />{label(accounts.length)}</button>
      </Dropdown>
    </Tooltip>
  );
}
