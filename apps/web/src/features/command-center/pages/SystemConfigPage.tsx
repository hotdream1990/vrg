import { SettingOutlined } from "@ant-design/icons";
import { App, Button, Form, Input, Space, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import { type ConfigItem, fetchConfig, saveConfig } from "../../../lib/api-client";
import "../../bulletin/bulletin.css";

/** Quản trị → Cấu hình hệ thống (chỉ admin). Tài khoản marketscreener + proxy cho crawler.
 *  Secret được server mask; để trống = giữ nguyên giá trị hiện tại. */
export default function SystemConfigPage() {
  const { message } = App.useApp();
  const [items, setItems] = useState<ConfigItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const load = useCallback(async () => {
    const r = await fetchConfig();
    setItems(r.config);
    const init: Record<string, string> = {};
    r.config.forEach((c) => { if (!c.secret && c.display) init[c.key] = c.display; });
    form.setFieldsValue(init);
  }, [form]);

  useEffect(() => { load(); }, [load]);

  const onSave = async () => {
    const values = form.getFieldsValue();
    const updates: Record<string, string> = {};
    for (const [k, v] of Object.entries(values)) {
      if (v != null && String(v).trim() !== "") updates[k] = String(v).trim();
    }
    if (Object.keys(updates).length === 0) {
      message.info("Chưa có thay đổi nào để lưu.");
      return;
    }
    setSaving(true);
    try {
      await saveConfig(updates);
      message.success("Đã lưu cấu hình.");
      form.resetFields();
      await load();
    } catch (e) {
      message.error(`Lưu thất bại: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SettingOutlined style={{ marginRight: 8 }} />Cấu hình hệ thống</h2>
          <p>Tài khoản nguồn dữ liệu &amp; proxy cho crawler marketscreener. Mật khẩu được ẩn —
            để trống nghĩa là giữ nguyên giá trị hiện tại.</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 640 }}>
        <Form form={form} layout="vertical" requiredMark={false}>
          {items.map((c) => (
            <Form.Item
              key={c.key}
              name={c.key}
              label={
                <Space>
                  {c.label}
                  {c.is_set ? <Tag color="green">Đã đặt</Tag> : <Tag>Chưa đặt</Tag>}
                </Space>
              }
              extra={c.secret ? "Để trống = giữ giá trị hiện tại." : undefined}
            >
              {c.secret ? (
                <Input.Password
                  placeholder={c.is_set ? "•••••• (đã đặt) — nhập để thay đổi" : c.placeholder}
                  autoComplete="new-password"
                />
              ) : (
                <Input placeholder={c.placeholder} />
              )}
            </Form.Item>
          ))}
          <Button type="primary" loading={saving} onClick={onSave}>Lưu cấu hình</Button>
        </Form>
      </div>
    </div>
  );
}
