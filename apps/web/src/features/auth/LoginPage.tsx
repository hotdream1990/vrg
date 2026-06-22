import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { VRG } from "../../theme";
import { useAuth } from "./AuthContext";

/** Trang đăng nhập admin VRG. */
export default function LoginPage() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const from = (loc.state as { from?: string } | null)?.from ?? "/";
  if (user) return <Navigate to={from} replace />;

  const onFinish = async (v: { username: string; password: string }) => {
    setLoading(true); setErr("");
    try { await login(v.username, v.password); nav(from, { replace: true }); }
    catch (e) { setErr(e instanceof Error ? e.message : "Đăng nhập thất bại"); }
    finally { setLoading(false); }
  };

  return (
    <div style={{
      minHeight: "100vh", display: "grid", placeItems: "center", padding: 16,
      background: "#eef3ef",
    }}>
      <Card style={{ width: 380, maxWidth: "100%", boxShadow: "0 8px 30px #0b3a1f1a" }}
        styles={{ body: { padding: 28 } }}>
        <div style={{ textAlign: "center", marginBottom: 20 }}>
          <div style={{
            width: 64, height: 64, borderRadius: "50%", margin: "0 auto 12px", background: "#fff",
            display: "grid", placeItems: "center", overflow: "hidden", boxShadow: `0 0 0 3px ${VRG.primary}22`,
          }}>
            <img src="/logo-vrg.png" alt="VRG" style={{ width: 52, height: 52, objectFit: "contain" }} />
          </div>
          <Typography.Title level={4} style={{ margin: 0 }}>VRG Command Center</Typography.Title>
          <Typography.Text type="secondary">Hệ thống quản trị giá cao su nội bộ</Typography.Text>
        </div>

        {err && <Alert type="error" showIcon message={err} style={{ marginBottom: 16 }} />}

        <Form layout="vertical" onFinish={onFinish} requiredMark={false} disabled={loading}>
          <Form.Item name="username" label="Tài khoản"
            rules={[{ required: true, message: "Nhập tài khoản" }]}>
            <Input prefix={<UserOutlined />} placeholder="admin" autoFocus size="large" />
          </Form.Item>
          <Form.Item name="password" label="Mật khẩu"
            rules={[{ required: true, message: "Nhập mật khẩu" }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="••••••" size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={loading}>
            Đăng nhập
          </Button>
        </Form>
      </Card>
    </div>
  );
}
