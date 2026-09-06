import { DatePicker, Modal, Radio, Select, message } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { useState } from "react";

import {
  type Attachment, type Reminder, type SupportContext,
  createReminder, updateReminder,
} from "../../../lib/support-client";
import { AttachmentPicker } from "./SupportAttachments";
import { REPEAT_LABEL } from "./support-format";
import "../support.css";

const REPEAT_OPTIONS = Object.entries(REPEAT_LABEL).map(([value, label]) => ({ value, label }));

type Props = {
  ctx: SupportContext;
  reminder: Reminder | null;   // null = tạo mới
  onClose: () => void;
  onSaved: () => void;
};

/** Form tạo/sửa lịch nhắc. Mốc nhắc chọn tới PHÚT (giờ Việt Nam) — hệ thống rà 5 phút một lần. */
export default function ReminderFormModal({ ctx, reminder, onClose, onSaved }: Props) {
  const [title, setTitle] = useState(reminder?.title ?? "");
  const [body, setBody] = useState(reminder?.body ?? "");
  const [files, setFiles] = useState<Attachment[]>(reminder?.files ?? []);
  const [scope, setScope] = useState<"all" | "units" | "region">(reminder?.scope ?? "all");
  const [units, setUnits] = useState<string[]>(reminder?.units ?? []);
  const [region, setRegion] = useState<string | undefined>(reminder?.region ?? undefined);
  const [repeat, setRepeat] = useState(reminder?.repeat_rule ?? "once");
  const [nextAt, setNextAt] = useState<Dayjs | null>(
    reminder ? dayjs(reminder.next_at) : dayjs().add(1, "hour").startOf("hour"),
  );
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!title.trim()) { message.error("Nhập nội dung nhắc."); return; }
    if (!nextAt) { message.error("Chọn thời điểm nhắc."); return; }
    if (scope === "units" && !units.length) { message.error("Chọn ít nhất một đơn vị."); return; }
    if (scope === "region" && !region) { message.error("Chọn khu vực."); return; }
    const payload = {
      title: title.trim(), body, files, scope, units, region: region ?? null,
      repeat_rule: repeat as Reminder["repeat_rule"],
      next_at: nextAt.toISOString(), enabled: reminder?.enabled ?? true,
    };
    setBusy(true);
    try {
      if (reminder) await updateReminder(reminder.id, payload);
      else await createReminder(payload);
      message.success(reminder ? "Đã cập nhật lịch nhắc." : "Đã tạo lịch nhắc.");
      onSaved();
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open width={680} onCancel={onClose} onOk={submit} confirmLoading={busy}
      okText={reminder ? "Lưu" : "Tạo lịch nhắc"} cancelText="Huỷ"
      title={reminder ? "Sửa lịch nhắc" : "Tạo lịch nhắc"}>
      <div className="sp-compose">
        <input className="sp-textarea" placeholder="Nội dung nhắc (dùng làm tiêu đề tin + tiêu đề email)"
          value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
        <textarea className="sp-textarea" rows={5} placeholder="Diễn giải thêm (không bắt buộc)…"
          value={body} onChange={(e) => setBody(e.target.value)} />

        <div>
          <div className="sp-label" style={{ marginBottom: 6 }}>Nhắc tới</div>
          <Radio.Group value={scope} onChange={(e) => setScope(e.target.value)}>
            <Radio.Button value="all">Tất cả đơn vị</Radio.Button>
            <Radio.Button value="region">Theo khu vực</Radio.Button>
            <Radio.Button value="units">Chọn đơn vị</Radio.Button>
          </Radio.Group>
        </div>
        {scope === "region" && (
          <Select placeholder="Chọn khu vực" value={region} onChange={setRegion}
            options={ctx.regions.map((r) => ({ value: r, label: r }))} />
        )}
        {scope === "units" && (
          <Select mode="multiple" allowClear placeholder="Chọn một hoặc nhiều đơn vị"
            value={units} onChange={setUnits}
            options={ctx.units.map((u) => ({ value: u, label: u }))} />
        )}

        <div className="sp-row">
          <label className="sp-label">Thời điểm nhắc:&nbsp;
            <DatePicker showTime format="HH:mm DD/MM/YYYY" value={nextAt} onChange={setNextAt} />
          </label>
          <label className="sp-label">Lặp lại:&nbsp;
            <Select style={{ minWidth: 150 }} value={repeat} options={REPEAT_OPTIONS}
              onChange={(v) => setRepeat(v)} />
          </label>
        </div>

        <AttachmentPicker value={files} onChange={setFiles} disabled={busy} />
        <p className="form-note" style={{ margin: 0 }}>
          Hệ thống rà lịch 5 phút một lần nên tin có thể tới muộn vài phút so với mốc đã chọn.
          Máy chủ tắt qua giờ hẹn thì lịch được gửi bù một lần khi chạy lại.
        </p>
      </div>
    </Modal>
  );
}
