import { CheckOutlined, CloseOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Table, Tag } from "antd";

import { ROLES } from "../../../lib/roles";

type Cap = { key: string; label: string; allow: Record<string, boolean> };

// Ma trận phản ánh ĐÚNG RBAC backend: require_admin (users/config/schedules) ·
// require_editor = admin+editor (ghi số liệu, quét, bản tin) · mọi vai trò (xem, hồ sơ).
const CAPS: Cap[] = [
  { key: "view", label: "Xem dashboard, bảng giá, biểu đồ, bản tin", allow: { viewer: true, editor: true, admin: true } },
  { key: "profile", label: "Đổi mật khẩu & hồ sơ cá nhân", allow: { viewer: true, editor: true, admin: true } },
  { key: "scan", label: "Quét giá đa sàn & nạp lịch sử (backfill)", allow: { viewer: false, editor: true, admin: true } },
  { key: "data", label: "Nhập / sửa / xoá số liệu (giá, tỷ giá, Physical, mủ nguyên liệu, tồn kho)", allow: { viewer: false, editor: true, admin: true } },
  { key: "master", label: "Quản lý giá sàn Tập đoàn & đơn vị thành viên", allow: { viewer: false, editor: true, admin: true } },
  { key: "bulletin", label: "Soạn / sửa / xuất bản tin (PDF · PPTX)", allow: { viewer: false, editor: true, admin: true } },
  { key: "users", label: "Quản trị người dùng (tạo / sửa / khoá / xoá tài khoản)", allow: { viewer: false, editor: false, admin: true } },
  { key: "config", label: "Cấu hình hệ thống (AI / LLM, nguồn dữ liệu)", allow: { viewer: false, editor: false, admin: true } },
  { key: "schedule", label: "Lịch chạy tự động (scheduler)", allow: { viewer: false, editor: false, admin: true } },
];

const yes = <CheckOutlined style={{ color: "#16a34a", fontSize: 15 }} aria-label="Được phép" />;
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
      render: (_: unknown, c: Cap) => (c.allow[r.value] ? yes : no),
    })),
  ];

  return (
    <div style={{ marginTop: 24 }}>
      <h3 style={{ margin: "0 0 2px", display: "flex", alignItems: "center", gap: 8, fontSize: 18 }}>
        <SafetyCertificateOutlined />Bảng phân quyền
      </h3>
      <p style={{ color: "var(--muted)", fontSize: 13, margin: "0 0 10px" }}>
        Quyền hệ thống áp dụng cho từng vai trò — enforce ở cả giao diện lẫn API (không chỉ ẩn menu).
      </p>
      <div className="card" style={{ padding: 0 }}>
        <Table rowKey="key" size="small" columns={columns} dataSource={CAPS}
          pagination={false} scroll={{ x: "max-content" }} />
      </div>
    </div>
  );
}
