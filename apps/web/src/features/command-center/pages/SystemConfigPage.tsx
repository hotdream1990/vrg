import { SettingOutlined } from "@ant-design/icons";
import { Alert, App, Button, Form, Input, Select, Space, Tabs, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";

import {
  type ConfigGroup,
  type ConfigItem,
  type MsTestResult,
  fetchConfig,
  fetchLlmModels,
  saveConfig,
  testMarketscreener,
} from "../../../lib/api-client";
import "../../bulletin/bulletin.css";

/** Ô nhập tương ứng loại cấu hình: có options → dropdown chọn, secret → mật khẩu, còn lại → text. */
function fieldInput(c: ConfigItem, options: string[] | null) {
  if (options && options.length) {
    return <Select showSearch placeholder={c.placeholder} allowClear
      options={options.map((o) => ({ value: o, label: o }))} />;
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
  const [openaiModels, setOpenaiModels] = useState<string[]>([]);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<MsTestResult | null>(null);
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
  useEffect(() => {
    fetchLlmModels().then((r) => setOpenaiModels(r.openai)).catch(() => setOpenaiModels([]));
  }, []);

  // Model OpenAI: dropdown nạp động từ tài khoản; các field khác dùng options tĩnh.
  const optionsFor = (c: ConfigItem) => (c.key === "OPENAI_MODEL" ? openaiModels : c.options);

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

  const onTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      setTestResult(await testMarketscreener());
    } catch (e) {
      setTestResult({ ok: false, stage: "error", message: String(e) });
    } finally {
      setTesting(false);
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
            {fieldInput(c, optionsFor(c))}
          </Form.Item>
        ))}
        {g.id === "marketscreener" && (
          <div style={{ marginTop: 4 }}>
            <Button loading={testing} onClick={onTest}>Chạy thử đăng nhập</Button>
            <span style={{ marginLeft: 10, color: "var(--muted)", fontSize: 12 }}>
              Dùng cấu hình đã lưu · thử 1 lần · ~30–60s
            </span>
            {testResult && (
              <>
                <Alert style={{ marginTop: 12 }} showIcon
                  type={testResult.ok ? "success" : "error"}
                  message={testResult.ok ? "Đăng nhập được ✓" : "Chưa đăng nhập được"}
                  description={testResult.message} />
                {testResult.screenshot && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 6 }}>
                      Ảnh chụp trang đăng nhập (headless) — để anh xem tận mắt:
                    </div>
                    <img alt="Trang đăng nhập marketscreener"
                      src={`data:image/jpeg;base64,${testResult.screenshot}`}
                      style={{ width: "100%", borderRadius: 8, border: "1px solid #e5e7eb" }} />
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    ),
  }));

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SettingOutlined style={{ marginRight: 8 }} />Cấu hình hệ thống</h2>
          <p>Tài khoản nguồn dữ liệu &amp; AI cho hệ thống. Mật khẩu/khóa được ẩn —
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
