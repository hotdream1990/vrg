import { EditOutlined } from "@ant-design/icons";
import { Modal } from "antd";
import { useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type Contract, type ContractMeta, setContractSource,
} from "../../../../lib/sales-contract-client";

type Props = {
  c: Contract;
  meta: ContractMeta;
  onSaved: () => void;
};

/** Nút «Sửa nguồn» của một lần giao — chỉ đổi đúng ô Nguồn tiêu thụ, kể cả lần giao ĐÃ KHOÁ (quá
 *  cửa sổ sửa / đã chốt số liệu), mở có hạn (`meta.source_self_edit_until`). Hết hạn thì không hiện
 *  nút, đơn vị quay về «Đề nghị sửa». Nút hiện ở mọi lần giao đã có ngày giao, không dò xem lần
 *  giao có khoá hay không: web chỉ biết cửa sổ sửa, còn mốc chốt số liệu chỉ server biết. */
export default function SourceQuickEdit({ c, meta, onSaved }: Props) {
  const until = meta.source_self_edit_until;
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState(c.source ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!until || !c.delivered_at || c.id == null) return null;

  const save = async () => {
    if (!source) { setErr("Chọn Nguồn tiêu thụ."); return; }
    setBusy(true); setErr("");
    try {
      await setContractSource(c.id as number, source);
      setOpen(false);
      onSaved();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <>
      <button className="btn" onClick={() => { setSource(c.source ?? ""); setErr(""); setOpen(true); }}>
        <EditOutlined /> Sửa nguồn
      </button>
      <Modal open={open} title={`Sửa nguồn tiêu thụ — ${c.parent_id ? "đợt giao" : "hợp đồng"} ${c.code}`}
        okText="Lưu" cancelText="Huỷ" confirmLoading={busy} onOk={save}
        onCancel={() => setOpen(false)} destroyOnHidden>
        {err && <div className="blt-error">{err}</div>}
        <label className="form-field">Nguồn tiêu thụ *
          <select className="blt-date-input" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">— chọn nguồn tiêu thụ —</option>
            {Object.entries(meta.sources ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        <p className="form-note" style={{ marginTop: 10 }}>
          Hộp này chỉ đổi nguồn tiêu thụ của lần giao ngày {dmy(c.delivered_at)}, kể cả khi lần giao
          đã khoá (quá hạn sửa hoặc đã chốt số liệu). Đơn vị tự đổi được đến hết ngày {dmy(until)};
          sau đó lần giao đã khoá phải gửi “Đề nghị sửa”.
        </p>
      </Modal>
    </>
  );
}
