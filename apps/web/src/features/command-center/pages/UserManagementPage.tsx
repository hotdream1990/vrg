import { PlusOutlined, SafetyOutlined } from "@ant-design/icons";
import { Alert, App, Button, Checkbox, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  type AppUser,
  createUser,
  deleteUser,
  listUsers,
  resetPassword,
  updateUser,
} from "../../../lib/user-client";
import { DATA_CAPS } from "../../../lib/permissions";
import { ROLE_COLOR, ROLE_LABEL, ROLES } from "../../../lib/roles";

const CAP_LABEL: Record<string, string> = Object.fromEntries(DATA_CAPS.map((c) => [c.key, c.label]));
import { useAuth } from "../../auth/AuthContext";
import PermissionMatrix from "../sections/PermissionMatrix";
import "../../bulletin/bulletin.css";

/** Quản trị → Người dùng: liệt kê + tạo/sửa/xoá tài khoản, đặt lại mật khẩu (chỉ admin). */
export default function UserManagementPage() {
  const { user: me } = useAuth();
  const { message } = App.useApp();
  const [users, setUsers] = useState<AppUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<AppUser | null>(null); // null = tạo mới
  const [pwUser, setPwUser] = useState<AppUser | null>(null);
  const [form] = Form.useForm();
  const [pwForm] = Form.useForm();
  const creating = editing === null;

  const load = useCallback(() => {
    setLoading(true);
    listUsers().then(setUsers).catch((e) => message.error(e.message)).finally(() => setLoading(false));
  }, [message]);
  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ role: "editor", is_active: true, permissions: [] });
    setOpen(true);
  };
  const openEdit = (u: AppUser) => {
    setEditing(u);
    form.resetFields();
    form.setFieldsValue({ full_name: u.full_name ?? "", role: u.role, is_active: u.is_active,
      permissions: u.permissions ?? [] });
    setOpen(true);
  };

  const submit = async (v: Record<string, unknown>) => {
    // Quyền theo mục chỉ áp cho editor (admin=toàn quyền, viewer=không có).
    const perms = v.role === "editor" ? ((v.permissions as string[]) ?? []) : [];
    try {
      if (creating) {
        await createUser({ username: (v.username as string).trim(), password: v.password as string,
          full_name: (v.full_name as string)?.trim() || undefined, role: v.role as string, permissions: perms });
        message.success("Đã tạo tài khoản");
      } else if (editing) {
        await updateUser(editing.username, { full_name: (v.full_name as string)?.trim() || null,
          role: v.role as string, is_active: v.is_active as boolean, permissions: perms });
        message.success("Đã cập nhật");
      }
      setOpen(false); load();
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
  };

  const submitPw = async (v: { new_password: string }) => {
    if (!pwUser) return;
    try {
      await resetPassword(pwUser.username, v.new_password);
      message.success(`Đã đặt lại mật khẩu cho ${pwUser.username}`);
      setPwUser(null); pwForm.resetFields();
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
  };

  const remove = async (u: AppUser) => {
    try { await deleteUser(u.username); message.success("Đã xoá"); load(); }
    catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
  };

  const columns = [
    { title: "Tên đăng nhập", dataIndex: "username", render: (v: string) =>
      <b>{v}{v === me?.username && <Tag color="blue" style={{ marginLeft: 6 }}>bạn</Tag>}</b> },
    { title: "Họ và tên", dataIndex: "full_name", render: (v: string | null) => v || <i style={{ color: "#999" }}>—</i> },
    { title: "Vai trò", dataIndex: "role", render: (v: string) =>
      <Tag color={ROLE_COLOR[v] ?? "default"}>{ROLE_LABEL[v] ?? v}</Tag> },
    { title: "Quyền số liệu", key: "perms", render: (_: unknown, u: AppUser) => {
      if (u.role === "admin") return <Tag color="green">Toàn quyền</Tag>;
      if (u.role !== "editor") return <span style={{ color: "#999" }}>—</span>;
      if (!u.permissions?.length) return <Tag>Chưa cấp quyền</Tag>;
      return <Space size={[4, 4]} wrap>{u.permissions.map((p) =>
        <Tag key={p} color="blue">{CAP_LABEL[p] ?? p}</Tag>)}</Space>;
    } },
    { title: "Trạng thái", dataIndex: "is_active", render: (v: boolean) =>
      <Tag color={v ? "success" : "error"}>{v ? "Đang dùng" : "Đã khoá"}</Tag> },
    { title: "Thao tác", key: "act", render: (_: unknown, u: AppUser) => (
      <Space size="small" wrap>
        <Button size="small" onClick={() => openEdit(u)}>Sửa</Button>
        <Button size="small" onClick={() => { setPwUser(u); pwForm.resetFields(); }}>Đặt lại MK</Button>
        <Popconfirm title={`Xoá tài khoản "${u.username}"?`} okText="Xoá" cancelText="Huỷ"
          okButtonProps={{ danger: true }} onConfirm={() => remove(u)} disabled={u.username === me?.username}>
          <Button size="small" danger disabled={u.username === me?.username}>Xoá</Button>
        </Popconfirm>
      </Space>
    ) },
  ];

  // Chặn non-admin gõ thẳng URL (menu đã ẩn; backend cũng trả 403).
  if (me?.role !== "admin") {
    return (
      <div className="main">
        <div className="page-title"><div><h2>Quản trị người dùng</h2></div></div>
        <div className="card" style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
          Bạn không có quyền truy cập mục Quản trị người dùng.
        </div>
      </div>
    );
  }

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SafetyOutlined style={{ marginRight: 8 }} />Quản trị người dùng</h2>
          <p>Tạo & phân quyền tài khoản: <b>Quản trị viên</b> (toàn quyền) · <b>Chuyên viên nhập liệu</b> (nhập/sửa số liệu) · <b>Người xem</b> (chỉ xem).</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>Thêm tài khoản</Button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <Table rowKey="username" size="middle" loading={loading} columns={columns}
          dataSource={users} pagination={false} scroll={{ x: "max-content" }} />
      </div>

      <PermissionMatrix />

      <Modal title={creating ? "Thêm tài khoản" : `Sửa: ${editing?.username}`} open={open} forceRender
        onCancel={() => setOpen(false)} onOk={() => form.submit()} okText="Lưu" cancelText="Huỷ">
        <Form form={form} layout="vertical" onFinish={submit}>
          {creating && (
            <>
              <Form.Item label="Tên đăng nhập" name="username"
                rules={[{ required: true, message: "Nhập tên đăng nhập" }, { min: 3, message: "Tối thiểu 3 ký tự" }]}>
                <Input placeholder="vd: nhanvien1" autoComplete="off" />
              </Form.Item>
              <Form.Item label="Mật khẩu" name="password"
                rules={[{ required: true, message: "Nhập mật khẩu" }, { min: 6, message: "Tối thiểu 6 ký tự" }]}>
                <Input.Password placeholder="Tối thiểu 6 ký tự" autoComplete="new-password" />
              </Form.Item>
            </>
          )}
          <Form.Item label="Họ và tên" name="full_name"><Input placeholder="Họ và tên" maxLength={120} /></Form.Item>
          <Form.Item label="Vai trò" name="role"><Select options={ROLES} /></Form.Item>
          <Form.Item noStyle shouldUpdate={(p, c) => p.role !== c.role}>
            {({ getFieldValue }) => {
              const role = getFieldValue("role");
              if (role === "admin")
                return <Alert type="success" showIcon style={{ marginBottom: 16 }}
                  message="Quản trị viên có toàn quyền — không cần chọn mục." />;
              if (role === "viewer")
                return <Alert type="info" showIcon style={{ marginBottom: 16 }}
                  message="Người xem không truy cập các mục quản lý số liệu (chỉ xem dashboard/bản tin)." />;
              return (
                <Form.Item label="Quyền theo mục (chuyên viên nhập liệu)" name="permissions"
                  tooltip="Chỉ những mục được tích mới hiện menu và cho phép nhập/sửa.">
                  <Checkbox.Group style={{ width: "100%" }}>
                    <Space direction="vertical" size={4}>
                      {DATA_CAPS.map((c) => (
                        <Checkbox key={c.key} value={c.key}>
                          {c.label}{c.hint && <span style={{ color: "#999", fontSize: 12 }}> — {c.hint}</span>}
                        </Checkbox>
                      ))}
                    </Space>
                  </Checkbox.Group>
                </Form.Item>
              );
            }}
          </Form.Item>
          {!creating && (
            <Form.Item label="Trạng thái" name="is_active">
              <Select options={[{ value: true, label: "Đang dùng" }, { value: false, label: "Đã khoá" }]} />
            </Form.Item>
          )}
        </Form>
      </Modal>

      <Modal title={`Đặt lại mật khẩu: ${pwUser?.username}`} open={pwUser !== null} forceRender
        onCancel={() => setPwUser(null)} onOk={() => pwForm.submit()} okText="Đặt lại" cancelText="Huỷ">
        <Form form={pwForm} layout="vertical" onFinish={submitPw}>
          <Form.Item label="Mật khẩu mới" name="new_password"
            rules={[{ required: true, message: "Nhập mật khẩu mới" }, { min: 6, message: "Tối thiểu 6 ký tự" }]}>
            <Input.Password placeholder="Tối thiểu 6 ký tự" autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
