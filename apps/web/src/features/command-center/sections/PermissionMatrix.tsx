import { CheckOutlined, CloseOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Table, Tag } from "antd";

import { ROLES } from "../../../lib/roles";

type Allow = boolean | "grant";
type Cap = { key: string; label: string; allow: Record<string, Allow> };

// Ma trận phản ánh ĐÚNG RBAC backend: require_admin (users/config/schedules) ·
// các mục SỐ LIỆU nay phân quyền theo TỪNG chuyên viên ("grant" = tuỳ mục được cấp ở trên).
const CAPS: Cap[] = [
  { key: "view", label: "Xem dashboard, bảng giá, biểu đồ, bản tin", allow: { viewer: true, editor: true, admin: true } },
  { key: "profile", label: "Đổi mật khẩu & hồ sơ cá nhân", allow: { viewer: true, editor: true, admin: true, member: true } },
  { key: "member_price", label: "Tự nhập giá mủ nước / mủ chén của đơn vị mình (hôm nay + 7 ngày)", allow: { member: true, admin: true } },
  { key: "scan", label: "Quét giá đa sàn & bảng tính giá các sàn (auto_data)", allow: { viewer: false, editor: "grant", admin: true } },
  { key: "data", label: "Nhập / sửa số liệu theo mục (Báo giá · mủ nguyên liệu · Physical · Tồn kho)", allow: { viewer: false, editor: "grant", admin: true } },
  { key: "master", label: "Giá sàn Tập đoàn & Đơn vị thành viên", allow: { viewer: false, editor: "grant", admin: true } },
  { key: "bulletin", label: "Soạn / sửa / xuất bản tin (PDF)", allow: { viewer: false, editor: "grant", admin: true } },
  { key: "users", label: "Quản trị người dùng (tạo / sửa / khoá / xoá tài khoản)", allow: { viewer: false, editor: false, admin: true } },
  { key: "config", label: "Cấu hình hệ thống (AI / LLM, nguồn dữ liệu)", allow: { viewer: false, editor: false, admin: true } },
  { key: "schedule", label: "Lịch chạy tự động (scheduler)", allow: { viewer: false, editor: false, admin: true } },
];

const yes = <CheckOutlined style={{ color: "#16a34a", fontSize: 15 }} aria-label="Được phép" />;
const grant = <Tag color="blue" style={{ margin: 0 }}>Tuỳ cấp</Tag>;
const no = <CloseOutlined style={{ color: "#cbd5e1", fontSize: 14 }} aria-label="Không được" />;

/** Bảng phân quyền trực quan (capability × 3 vai trò) — khớp RBAC backend. Đặt dưới bảng người dùng. */
export default function PermissionMatrix() {
  const columns = [
    { title: "Chức năng", dataIndex: "label", key: "label" },
    ...ROLES.map((r) => ({
      title: <Tag color={r.color} style={{ margin: 0 }}>{r.label}</Tag>,
      key: r.value,
      align: "center" as const,
      width: 160,
      render: (_: unknown, c: Cap) => {
        const a = c.allow[r.value];
        return a === "grant" ? grant : a ? yes : no;
      },
    })),
  ];

  return (
    <div style={{ marginTop: 24 }}>
      <h3 style={{ margin: "0 0 2px", display: "flex", alignItems: "center", gap: 8, fontSize: 18 }}>
        <SafetyCertificateOutlined />Bảng phân quyền
      </h3>
      <p style={{ color: "var(--muted)", fontSize: 13, margin: "0 0 10px" }}>
        Quyền hệ thống áp dụng cho từng vai trò — enforce ở cả giao diện lẫn API (không chỉ ẩn menu).{" "}
        <Tag color="blue" style={{ margin: 0 }}>Tuỳ cấp</Tag> = chuyên viên chỉ thấy/nhập mục được cấp quyền khi tạo/sửa tài khoản ở trên.
        Mỗi mục nhập liệu cấp được <b>2 mức</b>: <b>Xem</b> (chỉ đọc) hoặc <b>Sửa</b> (nhập/sửa/xoá).
      </p>
      <div className="card" style={{ padding: 0 }}>
        <Table rowKey="key" size="small" columns={columns} dataSource={CAPS}
          pagination={false} scroll={{ x: "max-content" }} />
      </div>
    </div>
  );
}
