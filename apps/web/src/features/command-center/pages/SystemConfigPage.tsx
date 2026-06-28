import { SettingOutlined } from "@ant-design/icons";
import { App, Button, Form, Input, Select, Space, Tabs, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import { type ConfigGroup, type ConfigItem, fetchConfig, saveConfig } from "../../../lib/api-client";
import "../../bulletin/bulletin.css";

/** Ô nhập tương ứng loại cấu hình: options → dropdown, secret → mật khẩu, còn lại → text. */
function fieldInput(c: ConfigItem) {
  if (c.options) {
    return <Select placeholder={c.placeholder} allowClear
      options={c.options.map((o) => ({ value: o, label: o }))} />;
  }
  if (c.secret) {
    return <Input.Password autoComplete="new-password"
      placeholder={c.is_set ? "•••••• (đã đặt) — nhập để thay đổi" : c.placeholder} />;
  }
  return <Input placeholder={c.placeholder} />;
}

/** Quản trị → Cấu hình hệ thống (chỉ admin), chia theo tab (Marketscreener · AI · …).
 *  Secret được server mask; để trống = giữ nguyên giá trị hiện tại. */
export default function SystemConfigPage() {
  const { message } = App.useApp();
  const [items, setItems] = useState<ConfigItem[]>([]);
  const [groups, setGroups] = useState<ConfigGroup[]>([]);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  // Nhà cung cấp LLM đang chọn → chỉ hiện key + model đúng provider đó.
  const provider = (Form.useWatch("LLM_PROVIDER", form) as string | undefined) || "openai";

  const load = useCallback(async () => {
    const r = await fetchConfig();
    setItems(r.config);
    setGroups(r.groups);
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

  const tabItems = groups.map((g) => ({
    key: g.id,
    label: g.label,
    forceRender: true, // giữ field của mọi tab trong form, đổi tab không mất dữ liệu
    children: (
      <div style={{ paddingTop: 8 }}>
        {items
          .filter((c) => c.group === g.id && (!c.provider || c.provider === provider))
          .map((c) => (
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
            {fieldInput(c)}
          </Form.Item>
        ))}
      </div>
    ),
  }));

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SettingOutlined style={{ marginRight: 8 }} />Cấu hình hệ thống</h2>
          <p>Tài khoản nguồn dữ liệu, proxy &amp; AI cho hệ thống. Mật khẩu/khóa được ẩn —
            để trống nghĩa là giữ nguyên giá trị hiện tại.</p>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 640 }}>
        <Form form={form} layout="vertical" requiredMark={false}>
          <Tabs items={tabItems} />
          <Button type="primary" loading={saving} onClick={onSave} style={{ marginTop: 8 }}>
            Lưu cấu hình
          </Button>
        </Form>
      </div>
    </div>
  );
}
