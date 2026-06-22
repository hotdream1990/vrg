import { IdcardOutlined } from "@ant-design/icons";
import { App, Button, Card, Form, Input, Tag } from "antd";
import { useState } from "react";

import { changePassword, updateProfile } from "../../../lib/auth-client";
import { useAuth } from "../../auth/AuthContext";
import "../../bulletin/bulletin.css";

/** Hồ sơ cá nhân: cập nhật họ tên + đổi mật khẩu của chính user đang đăng nhập. */
export default function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const { message } = App.useApp();
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPw, setSavingPw] = useState(false);
  const [pwForm] = Form.useForm();

  const onSaveProfile = async (v: { full_name?: string }) => {
    setSavingProfile(true);
    try {
      await updateProfile(v.full_name?.trim() || null);
      await refreshUser();
      message.success("Đã cập nhật hồ sơ");
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
    finally { setSavingProfile(false); }
  };

  const onChangePw = async (v: { old_password: string; new_password: string }) => {
    setSavingPw(true);
    try {
      await changePassword(v.old_password, v.new_password);
      pwForm.resetFields();
      message.success("Đã đổi mật khẩu");
    } catch (e) { message.error(e instanceof Error ? e.message : "Lỗi"); }
    finally { setSavingPw(false); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><IdcardOutlined style={{ marginRight: 8 }} />Hồ sơ cá nhân</h2>
          <p>Cập nhật họ tên hiển thị và đổi mật khẩu đăng nhập của bạn.</p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(320px,1fr))", gap: 16, maxWidth: 880 }}>
        <Card title="Thông tin cá nhân">
          <Form layout="vertical" initialValues={{ full_name: user?.full_name ?? "" }} onFinish={onSaveProfile}>
            <Form.Item label="Tên đăng nhập">
              <Input value={user?.username} disabled addonAfter={<Tag color="green">{user?.role}</Tag>} />
            </Form.Item>
            <Form.Item label="Họ và tên" name="full_name">
              <Input placeholder="Nhập họ và tên" maxLength={120} />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={savingProfile}>Lưu thông tin</Button>
          </Form>
        </Card>

        <Card title="Đổi mật khẩu">
          <Form form={pwForm} layout="vertical" onFinish={onChangePw}>
            <Form.Item label="Mật khẩu hiện tại" name="old_password" rules={[{ required: true, message: "Nhập mật khẩu hiện tại" }]}>
              <Input.Password placeholder="••••••" autoComplete="current-password" />
            </Form.Item>
            <Form.Item label="Mật khẩu mới" name="new_password"
              rules={[{ required: true, message: "Nhập mật khẩu mới" }, { min: 6, message: "Tối thiểu 6 ký tự" }]}>
              <Input.Password placeholder="Tối thiểu 6 ký tự" autoComplete="new-password" />
            </Form.Item>
            <Form.Item label="Xác nhận mật khẩu mới" name="confirm" dependencies={["new_password"]}
              rules={[
                { required: true, message: "Nhập lại mật khẩu mới" },
                ({ getFieldValue }) => ({
                  validator: (_, value) =>
                    !value || getFieldValue("new_password") === value
                      ? Promise.resolve() : Promise.reject(new Error("Mật khẩu xác nhận không khớp")),
                }),
              ]}>
              <Input.Password placeholder="Nhập lại mật khẩu mới" autoComplete="new-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={savingPw}>Đổi mật khẩu</Button>
          </Form>
        </Card>
      </div>
    </div>
  );
}
