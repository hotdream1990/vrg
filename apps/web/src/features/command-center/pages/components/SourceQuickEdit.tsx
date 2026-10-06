import { EditOutlined } from "@ant-design/icons";
import { Modal } from "antd";
import { useState } from "react";

import { dmy } from "../../../../lib/date";
import {
  type Contract, type ContractMeta, setContractSource,
} from "../../../../lib/sales-contract-client";
import LineSourcePicker from "./LineSourcePicker";
import { effectiveLineSource } from "./line-source";

type Props = {
  c: Contract;
  meta: ContractMeta;
  onSaved: () => void;
};

/** Nút «Sửa nguồn» của một lần giao — chỉ đổi NGUỒN TIÊU THỤ của từng dòng chủng loại, kể cả lần
 *  giao ĐÃ KHOÁ (quá cửa sổ sửa / đã chốt số liệu), mở có hạn (`meta.source_self_edit_until`). Hết
 *  hạn thì không hiện nút, đơn vị quay về «Đề nghị sửa». Nút hiện ở mọi lần giao đã có ngày giao,
 *  không dò xem lần giao có khoá hay không: web chỉ biết cửa sổ sửa, còn mốc chốt số liệu chỉ
 *  server biết. */
export default function SourceQuickEdit({ c, meta, onSaved }: Props) {
  const until = meta.source_self_edit_until;
  const [open, setOpen] = useState(false);
  // Giá trị đầu = nguồn đang tính của từng dòng (dòng cũ chưa khai nguồn riêng → nguồn của lần
  // giao → khai thác), đúng như server đang đếm — người sửa thấy hiện trạng rồi mới đổi.
  const initial = () => c.lines.map((ln) => effectiveLineSource(ln, c.source));
  const [values, setValues] = useState<string[]>(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!until || !c.delivered_at || c.id == null) return null;

  const save = async () => {
    const missing = c.lines.map((ln, i) => (values[i] ? "" : `Dòng ${i + 1} (${ln.grade})`))
      .filter(Boolean);
    if (missing.length) { setErr(`Chọn nguồn tiêu thụ cho: ${missing.join(", ")}.`); return; }
    setBusy(true); setErr("");
    try {
      // Theo ĐÚNG thứ tự `c.lines` — server so số phần tử, lệch (hợp đồng vừa bị sửa) là báo lỗi.
      await setContractSource(c.id as number, values);
      setOpen(false);
      onSaved();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <>
      <button className="btn" onClick={() => { setValues(initial()); setErr(""); setOpen(true); }}>
        <EditOutlined /> Sửa nguồn
      </button>
      <Modal open={open} title={`Sửa nguồn tiêu thụ — ${c.parent_id ? "đợt giao" : "hợp đồng"} ${c.code}`}
        okText="Lưu" cancelText="Huỷ" confirmLoading={busy} onOk={save}
        onCancel={() => setOpen(false)} destroyOnHidden>
        {err && <div className="blt-error" style={{ marginBottom: 8 }}>{err}</div>}
        <LineSourcePicker lines={c.lines} labels={meta.sources ?? {}} value={values}
          onChange={setValues} />
        <p className="form-note" style={{ marginTop: 10 }}>
          Hộp này chỉ đổi nguồn tiêu thụ của từng dòng chủng loại trong lần giao ngày{" "}
          {dmy(c.delivered_at)}, kể cả khi lần giao đã khoá (quá hạn sửa hoặc đã chốt số liệu). Đơn
          vị tự đổi được đến hết ngày {dmy(until)}; sau đó lần giao đã khoá phải gửi “Đề nghị sửa”.
        </p>
      </Modal>
    </>
  );
}
