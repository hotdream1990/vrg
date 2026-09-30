import { SettingOutlined } from "@ant-design/icons";
import { App, Button, Form, Input, Select, Space, Tabs, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  type ConfigGroup,
  type ConfigItem,
  fetchConfig,
  fetchLlmModels,
  saveConfig,
  sendTestEmail,
} from "../../../lib/api-client";
import "../../bulletin/bulletin.css";
import ScadaFactoryPanel from "./smart-factory/ScadaFactoryPanel";

/** Tab không thuộc app_config — tự lưu trong màn của nó nên ẩn nút "Lưu cấu hình". */
const SCADA_TAB = "scada";

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

/** Quản trị → Cấu hình hệ thống (chỉ admin), chia theo tab (AI / LLM · …).
 *  Secret được server mask; để trống = giữ nguyên giá trị hiện tại. */
export default function SystemConfigPage() {
  const { message } = App.useApp();
  const [items, setItems] = useState<ConfigItem[]>([]);
  const [groups, setGroups] = useState<ConfigGroup[]>([]);
  const [saving, setSaving] = useState(false);
  const [openaiModels, setOpenaiModels] = useState<string[]>([]);
  const [testTo, setTestTo] = useState("");     // địa chỉ nhận thư kiểm tra SMTP
  const [testing, setTesting] = useState(false);
  const [form] = Form.useForm();
  // Tab đang mở nằm trên URL (?tab=scada) → link từ màn Giám sát chỉ số mở thẳng đúng tab.
  const [params, setParams] = useSearchParams();
  const activeTab = params.get("tab") || groups[0]?.id;
  const onTab = (key: string) => setParams({ tab: key }, { replace: true });
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

  /** Gửi thử email: báo NGUYÊN VĂN lý do lỗi từ máy chủ mail — đoán mò cấu hình SMTP rất mất thời gian. */
  const onTestEmail = async () => {
    setTesting(true);
    try {
      const r = await sendTestEmail(testTo.trim());
      if (r.ok) message.success(r.detail);
      else message.error(r.detail);
    } catch (e) {
      message.error(`Gửi thử thất bại: ${e}`);
    } finally {
      setTesting(false);
    }
  };

  /** Khối "Gửi thử" đặt cuối tab Email — lưu cấu hình xong bấm thử ngay tại chỗ. */
  const emailTester = (
    <div style={{ borderTop: "1px solid var(--line)", paddingTop: 12, marginTop: 4 }}>
      <div style={{ marginBottom: 8, fontSize: 13 }}>
        Gửi một thư kiểm tra để chắc chắn cấu hình chạy được (lưu cấu hình trước khi gửi thử).
      </div>
      <Space.Compact style={{ width: "100%" }}>
        <Input placeholder="Địa chỉ email nhận thư kiểm tra" value={testTo}
          onChange={(e) => setTestTo(e.target.value)} />
        <Button onClick={onTestEmail} loading={testing} disabled={!testTo.trim()}>Gửi thử</Button>
      </Space.Compact>
    </div>
  );

  const tabItems = groups.map((g) => ({
    key: g.id,
    label: g.label,
    forceRender: true, // giữ field của mọi tab trong form, đổi tab không mất dữ liệu
    children: (
      <div className="config-grid">
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
        {g.id === "email" && <div className="config-wide">{emailTester}</div>}
      </div>
    ),
  }));
  tabItems.push({ key: SCADA_TAB, label: "SCADA nhà máy", forceRender: false,
    children: <ScadaFactoryPanel /> });

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><SettingOutlined style={{ marginRight: 8 }} />Cấu hình hệ thống</h2>
          <p>Tài khoản nguồn dữ liệu &amp; AI cho hệ thống. Mật khẩu/khóa được ẩn —
            để trống nghĩa là giữ nguyên giá trị hiện tại.</p>
        </div>
      </div>

      <div className="card">
        <Form form={form} layout="vertical" requiredMark={false}>
          <Tabs items={tabItems} activeKey={activeTab} onChange={onTab} />
          {activeTab !== SCADA_TAB && (
            <Button type="primary" loading={saving} onClick={onSave} style={{ marginTop: 8 }}>
              Lưu cấu hình
            </Button>
          )}
        </Form>
      </div>
    </div>
  );
}
