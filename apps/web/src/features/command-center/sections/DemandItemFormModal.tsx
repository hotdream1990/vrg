import { SendOutlined } from "@ant-design/icons";
import {
  Alert, AutoComplete, Checkbox, Form, Input, InputNumber, Modal, Radio, Select, Space,
} from "antd";
import { useState, type CSSProperties, type ReactNode } from "react";

import type { DemandItemInput } from "../../../lib/market-demand-client";
import {
  CURRENCIES, DEFAULT_DELIVERY_PLACE, DEMAND_CONTRACT_NO_MAX, DEMAND_NOTE_MAX, DEMAND_STATUSES,
  QTY_UNITS, normalizeDemand, suggest, validateDemand,
} from "../../../lib/market-demand-meta";
import { formatViNumber, parseViNumber } from "../../../lib/number-format";
import DateInput from "./DateInput";

export type DemandFormMode = "create" | "edit" | "request";

type Props = {
  mode: DemandFormMode;
  initial: DemandItemInput;
  /** Ngày nhận đã ngoài cửa sổ sửa (chỉ xét ở chế độ sửa thường): khoá các ô NỘI DUNG. */
  contentLocked: boolean;
  /** Đơn vị được chọn (đã bỏ đơn vị chỉ xem). */
  units: string[];
  grades: string[];
  /** Nguồn gợi ý cho ô gõ tự do. */
  customers: string[];
  places: string[];
  /** Ngày server (YYYY-MM-DD). */
  today: string;
  /** Ném lỗi = giữ form và hiện lỗi; xong việc thì màn cha tự đóng form. */
  onSubmit: (v: DemandItemInput) => Promise<void>;
  onCancel: () => void;
};

const TITLE: Record<DemandFormMode, string> = {
  create: "Thêm nhu cầu", edit: "Sửa nhu cầu", request: "Đề nghị sửa nhu cầu",
};
const STATUS_OPTIONS = DEMAND_STATUSES.map(({ value, label }) => ({ value, label }));
const GRID: CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", columnGap: 16,
};
const FULL: CSSProperties = { width: "100%" };

// Ô số kiểu vi-VN (1.234,5) đọc qua parseViNumber — để "40,5" không bị hiểu thành 405.
const viFormatter = (v: number | undefined, info: { userTyping: boolean; input: string }) =>
  (info.userTyping ? info.input : formatViNumber(v ?? null));
// Ô trống phải trả "" thì InputNumber mới hiểu là xoá giá trị (kiểu khai báo chỉ nhận số).
const viParser = (s: string | undefined) => (parseViNumber(s) ?? "") as unknown as number;

function Field({ label, required, wide, children }: {
  label: string; required?: boolean; wide?: boolean; children: ReactNode;
}) {
  return (
    <Form.Item label={label} required={required}
      style={{ marginBottom: 12, gridColumn: wide ? "1 / -1" : undefined }}>
      {children}
    </Form.Item>
  );
}

const withCurrent = (list: string[], current: string) =>
  [...new Set([...list, ...(current ? [current] : [])])].map((x) => ({ value: x, label: x }));

/** Form một phiếu nhu cầu: thêm mới · sửa · soạn đề nghị sửa (mở khoá mọi ô, Ban duyệt mới ghi). */
export default function DemandItemFormModal({
  mode, initial, contentLocked, units, grades, customers, places, today, onSubmit, onCancel,
}: Props) {
  const [v, setV] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = <K extends keyof DemandItemInput>(k: K) => (val: DemandItemInput[K]) => {
    setV((p) => ({ ...p, [k]: val }));
    setErr("");   // người dùng đang sửa → bỏ câu báo lỗi cũ
  };
  const setDate = (k: "delivery_from" | "delivery_to" | "contract_date") =>
    (iso: string) => set(k)(iso || null);
  const lock = mode === "edit" && contentLocked;
  const unitOptions = withCurrent(units, v.company);

  const submit = async () => {
    const problem = validateDemand(v, today);
    if (problem) { setErr(problem); return; }
    setBusy(true); setErr("");
    try {
      await onSubmit(normalizeDemand(v));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Lưu không thành công, vui lòng thử lại.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open width="min(780px, 94vw)" destroyOnHidden mask={{ closable: false }}
      title={TITLE[mode]} onCancel={busy ? undefined : onCancel} onOk={submit}
      okText={mode === "request" ? <><SendOutlined /> Gửi đề nghị sửa</> : "Lưu"}
      cancelText="Huỷ" okButtonProps={{ loading: busy }}>
      {mode === "request" && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          title="Bạn đang soạn đề nghị sửa — số liệu chỉ thay đổi sau khi Ban duyệt." />
      )}
      {lock && (
        <p className="form-note" style={{ margin: "0 0 12px" }}>
          Ngày nhận đã ngoài thời hạn sửa — chỉ cập nhật được tình trạng, số hợp đồng, ngày ký và ghi
          chú. Muốn sửa nội dung khác, bấm «Đề nghị sửa».
        </p>
      )}
      <div style={GRID}>
        <Form layout="vertical" component={false}>
          {unitOptions.length > 1 && (
            <Field label="Đơn vị" required wide>
              <Select showSearch placeholder="Chọn đơn vị" value={v.company || undefined}
                options={unitOptions} disabled={lock} onChange={set("company")} />
            </Field>
          )}
          <Field label="Ngày nhận" required>
            <DateInput value={v.as_of} onChange={set("as_of")} noFuture readOnly={lock} style={FULL} />
          </Field>
          <Field label="Khách hàng" required>
            {/* antd AutoComplete khi khoá KHÔNG đổi sang nền xám (trông như vẫn gõ được) → dùng Input khoá. */}
            {lock ? <Input value={v.customer} disabled /> : (
              <AutoComplete value={v.customer} options={suggest(customers, v.customer)}
                placeholder="Tên công ty / khách hàng" onChange={set("customer")} />
            )}
          </Field>
          <Field label="Chủng loại" required>
            <Select showSearch placeholder="Chọn chủng loại" value={v.grade || undefined}
              options={withCurrent(grades, v.grade)} disabled={lock} onChange={set("grade")} />
          </Field>
          <Field label="Số lượng">
            <Space.Compact block>
              <InputNumber<number> min={0} controls={false} style={FULL} value={v.qty} disabled={lock}
                formatter={viFormatter} parser={viParser} onChange={set("qty")} />
              <Select value={v.qty_unit} options={QTY_UNITS} style={{ width: 120 }} disabled={lock}
                onChange={set("qty_unit")} />
            </Space.Compact>
          </Field>
          <Field label="Đơn giá" wide>
            <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <Space.Compact style={{ flex: "1 1 280px" }}>
                <InputNumber<number> min={0} controls={false} style={FULL} value={v.price} disabled={lock}
                  formatter={viFormatter} parser={viParser} onChange={set("price")} />
                <Select value={v.currency} options={CURRENCIES} style={{ width: 160 }} disabled={lock}
                  onChange={set("currency")} />
              </Space.Compact>
              <Checkbox checked={v.price_provisional} disabled={lock}
                onChange={(e) => set("price_provisional")(e.target.checked)}>
                Giá tạm tính
              </Checkbox>
            </div>
            {v.currency === "VND" && !lock && (
              <div className="form-note" style={{ fontSize: 13, marginTop: 4 }}>
                Đơn giá tính bằng TRIỆU đồng/tấn — ví dụ 40 = 40 triệu
              </div>
            )}
          </Field>
          <Field label="Giao tại">
            {lock ? <Input value={v.delivery_place} disabled /> : (
              <AutoComplete value={v.delivery_place} placeholder="Tại kho, cảng…"
                options={suggest([DEFAULT_DELIVERY_PLACE, ...places], v.delivery_place)}
                onChange={set("delivery_place")} />
            )}
          </Field>
          <Field label="Giao từ ngày – đến ngày">
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <DateInput value={v.delivery_from ?? ""} onChange={setDate("delivery_from")} allowClear
                maxDate={v.delivery_to ?? undefined} placeholder="Từ ngày" readOnly={lock} style={FULL} />
              <span>–</span>
              <DateInput value={v.delivery_to ?? ""} onChange={setDate("delivery_to")} allowClear
                minDate={v.delivery_from ?? undefined} placeholder="Đến ngày" readOnly={lock} style={FULL} />
            </div>
          </Field>
          <Field label="Tình trạng" required wide>
            <Radio.Group optionType="button" buttonStyle="solid" value={v.status} options={STATUS_OPTIONS}
              onChange={(e) => set("status")(e.target.value)} />
          </Field>
          {v.status === "signed" && (
            <>
              <Field label="Số hợp đồng" required>
                <Input value={v.contract_no} maxLength={DEMAND_CONTRACT_NO_MAX}
                  onChange={(e) => set("contract_no")(e.target.value)} />
              </Field>
              <Field label="Ngày ký hợp đồng" required>
                <DateInput value={v.contract_date ?? ""} onChange={setDate("contract_date")} noFuture style={FULL} />
              </Field>
            </>
          )}
          <Field label="Ghi chú" wide>
            <Input.TextArea rows={3} value={v.note} maxLength={DEMAND_NOTE_MAX} showCount
              onChange={(e) => set("note")(e.target.value)} />
          </Field>
        </Form>
      </div>
      {err && <Alert type="error" showIcon title={err} style={{ marginTop: 8 }} />}
    </Modal>
  );
}
