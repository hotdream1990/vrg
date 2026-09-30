/* Form thêm/sửa cấu hình kết nối SCADA của một nhà máy (chỉ admin).
   Mật khẩu không bao giờ trả về từ server: khi sửa, để trống = giữ mật khẩu cũ — trừ khi đổi máy chủ,
   cổng hoặc tài khoản (phải nhập lại). Tag điện là 4 ô cố định R0..R3 để không thể đảo thứ tự. */

import { Alert, Form, Input, InputNumber, Modal, Switch } from "antd";
import { useState } from "react";

import {
  type ScadaFactory, createScadaFactory, updateScadaFactory,
} from "../../../../lib/smart-factory-client";
import {
  DEFAULT_ENERGY_TAGS, ENERGY_SLOTS, type ScadaFormValues, identRule, initialValues, passwordRule,
  tagItemProps, toInput,
} from "./scada-form-rules";
import { errText } from "./smart-factory-format";

type Props = {
  factory: ScadaFactory | null;   // null = thêm mới
  onClose: () => void;
  onSaved: (f: ScadaFactory) => void;
};

const required = (msg: string) => ({ required: true, whitespace: true, message: msg });

export default function ScadaFactoryFormModal({ factory, onClose, onSaved }: Props) {
  const [form] = Form.useForm<ScadaFormValues>();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const editing = factory != null;

  const submit = async (v: ScadaFormValues) => {
    setBusy(true);
    setErr("");
    try {
      const input = toInput(v);
      const r = editing ? await updateScadaFactory(factory.id, input) : await createScadaFactory(input);
      onSaved(r.factory);
    } catch (e) {
      setErr(errText(e, "Lưu không thành công, vui lòng thử lại."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open width="min(760px, 94vw)" destroyOnHidden mask={{ closable: false }}
      title={editing ? `Sửa kết nối: ${factory.name}` : "Thêm nhà máy"}
      onCancel={busy ? undefined : onClose} onOk={() => form.submit()}
      okText="Lưu" cancelText="Huỷ" okButtonProps={{ loading: busy }}
    >
      <p className="form-note" style={{ margin: "0 0 12px" }}>
        Nên dùng tài khoản SQL chỉ có quyền đọc. Máy chủ VRG phải truy cập được SQL Server của nhà máy
        (IP/NAT hoặc VPN).
      </p>
      {err && <Alert type="error" showIcon className="sf-alert" title={err} />}

      <Form<ScadaFormValues>
        form={form} layout="vertical" initialValues={initialValues(factory)} onFinish={submit}
        onValuesChange={() => err && setErr("")} autoComplete="off"
      >
        <div className="sf-form-group">Kết nối</div>
        <div className="sf-form-grid">
          <Form.Item className="sf-wide" label="Tên nhà máy" name="name"
            rules={[required("Nhập tên nhà máy"), { max: 200, message: "Tối đa 200 ký tự" }]}>
            <Input placeholder="vd: Nhà máy Phú Riềng" maxLength={200} />
          </Form.Item>
          <Form.Item label="Máy chủ (IP / hostname)" name="host"
            rules={[required("Nhập địa chỉ máy chủ SQL Server"), { max: 255, message: "Tối đa 255 ký tự" }]}>
            <Input placeholder="vd: 10.0.0.5" className="sf-code" />
          </Form.Item>
          <Form.Item label="Cổng" name="port" rules={[{ required: true, message: "Nhập cổng" }]}>
            <InputNumber<number> min={1} max={65535} precision={0} controls={false} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item label="Tài khoản" name="username" rules={[required("Nhập tài khoản SQL")]}>
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item label="Mật khẩu" name="password" required={!editing}
            dependencies={["host", "port", "username"]} rules={[passwordRule(factory)]}>
            <Input.Password autoComplete="new-password"
              placeholder={editing && factory.password_set ? "•••••• (đã đặt) — bỏ trống để giữ nguyên" : undefined} />
          </Form.Item>
          <Form.Item label="CSDL (database)" name="database" rules={[required("Nhập tên CSDL"), identRule]}>
            <Input className="sf-code" placeholder="Runtime" />
          </Form.Item>
          <Form.Item label="Linked server" name="linked_server" rules={[required("Nhập linked server"), identRule]}>
            <Input className="sf-code" placeholder="INSQL" />
          </Form.Item>
        </div>

        <div className="sf-form-group">Tag điện năng</div>
        <p className="form-note" style={{ margin: "0 0 10px" }}>
          Điền 4 tag thanh ghi đúng ô: kWh = (R0×2⁴⁸ + R1×2³² + R2×65.536 + R3) / 1000. SCADA đã có sẵn
          số kWh thì chỉ điền ô R0. Không đọc điện thì để trống cả 4 ô.
        </p>
        <div className="sf-form-grid sf-energy-grid">
          {ENERGY_SLOTS.map((slot, i) => (
            <Form.Item key={slot.key} label={slot.label} {...tagItemProps(slot.key)}>
              <Input className="sf-code" placeholder={DEFAULT_ENERGY_TAGS[i]} allowClear />
            </Form.Item>
          ))}
        </div>
        <div className="sf-form-group">Tag nước · số bành</div>
        <div className="sf-form-grid">
          <Form.Item label="Tag nước" {...tagItemProps("water")}>
            <Input className="sf-code" placeholder="Water_TotalVolume" allowClear />
          </Form.Item>
          <Form.Item label="Tag số bành" {...tagItemProps("bales")}
            extra={<span className="form-note">Tên tag bộ đếm số bành trong Historian — bỏ trống nếu chưa có</span>}>
            <Input className="sf-code" allowClear />
          </Form.Item>
        </div>
        <Form.Item label="Bật đọc số liệu" name="enabled" valuePropName="checked">
          <Switch checkedChildren="Bật" unCheckedChildren="Tắt" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
