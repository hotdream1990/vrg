import { Modal, Radio, Select, message } from "antd";
import { useState } from "react";

import {
  type Attachment, type SupportContext, createAnnouncement, createRequest,
} from "../../../lib/support-client";
import { AttachmentPicker } from "./SupportAttachments";
import "../support.css";

type Props = {
  ctx: SupportContext;
  onClose: () => void;
  /** `threadId` khác null = mở thẳng luồng vừa tạo (đơn vị gửi 1 luồng); null = gửi nhiều luồng. */
  onSent: (threadId: number | null) => void;
};

/** Soạn tin mới — một hộp thoại cho cả hai phía:
 *  - Tập đoàn: chọn phạm vi (tất cả · theo khu vực · chọn đơn vị) → mỗi đơn vị một luồng RIÊNG;
 *  - Lãnh đạo đơn vị: chọn đơn vị của mình rồi gửi yêu cầu hỗ trợ lên Tập đoàn. */
export default function SupportComposer({ ctx, onClose, onSent }: Props) {
  const isHq = ctx.side === "hq";
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<Attachment[]>([]);
  const [scope, setScope] = useState<"all" | "units" | "region">("all");
  const [units, setUnits] = useState<string[]>([]);
  const [region, setRegion] = useState<string | undefined>();
  const [company, setCompany] = useState<string>(ctx.units[0] ?? "");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!subject.trim()) { message.error("Nhập tiêu đề cho tin."); return; }
    if (isHq && scope === "units" && !units.length) { message.error("Chọn ít nhất một đơn vị nhận."); return; }
    if (isHq && scope === "region" && !region) { message.error("Chọn khu vực nhận."); return; }
    if (!isHq && !company) { message.error("Chọn đơn vị gửi."); return; }
    setBusy(true);
    try {
      if (isHq) {
        const r = await createAnnouncement({
          subject: subject.trim(), body, files, scope, units, region: region ?? null,
        });
        message.success(`Đã gửi tới ${r.threads} đơn vị.`);
        onSent(null);
      } else {
        const r = await createRequest({ company, subject: subject.trim(), body, files });
        message.success("Đã gửi yêu cầu tới Tập đoàn.");
        onSent(r.thread_id);
      }
    } catch (e) {
      message.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open width={720} onCancel={onClose} onOk={submit} confirmLoading={busy}
      okText={isHq ? "Gửi thông báo" : "Gửi yêu cầu"} cancelText="Huỷ"
      title={isHq ? "Soạn thông báo gửi đơn vị thành viên" : "Gửi yêu cầu hỗ trợ tới Tập đoàn"}>
      <div className="sp-compose">
        {isHq ? (
          <>
            <div>
              <div className="sp-label" style={{ marginBottom: 6 }}>Gửi tới</div>
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
            <p className="form-note" style={{ margin: 0 }}>
              Lưu ý: mỗi đơn vị nhận một tin RIÊNG — đơn vị không thấy danh sách nơi nhận,
              cũng không thấy phản hồi của đơn vị khác.
            </p>
          </>
        ) : (
          ctx.units.length > 1 && (
            <Select value={company} onChange={setCompany}
              options={ctx.units.map((u) => ({ value: u, label: u }))} />
          )
        )}

        <input className="sp-textarea" placeholder="Tiêu đề (hiện trong email gửi tới đơn vị)"
          value={subject} maxLength={200} onChange={(e) => setSubject(e.target.value)} />
        <textarea className="sp-textarea" rows={8} placeholder="Nội dung…"
          value={body} onChange={(e) => setBody(e.target.value)} />
        <AttachmentPicker value={files} onChange={setFiles} disabled={busy} />
        <div className="sp-label">Định dạng nhận: {ctx.accept_label}</div>
      </div>
    </Modal>
  );
}
