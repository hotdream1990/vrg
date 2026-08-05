import { Modal } from "antd";
import { useState } from "react";

import { type ContractDetail, setContractCompletion } from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";

type Props = {
  d: ContractDetail;
  onClose: () => void;
  onDone: () => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const today = () => new Date().toISOString().slice(0, 10);

/** Chốt HOÀN THÀNH hợp đồng: chọn ngày kết thúc, phần chênh còn lại rời khỏi "đã ký HĐ chưa giao".
 *
 *  Có màn riêng thay vì một nút bấm là xong, vì ngày chốt đi thẳng vào số liệu: khối "đã ký HĐ
 *  chưa giao" của mọi ngày TỪ ngày đó trở đi sẽ không còn phần chênh này. */
export default function ContractCompleteModal({ d, onClose, onDone }: Props) {
  const c = d.contract;
  const [day, setDay] = useState(today());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const short = d.remaining_qty > 1e-9;
  // Giao thiếu thì nói "đạt x%" (số dương, dễ đọc); giao vượt mới nói "+x% so với hợp đồng".
  // Ghi "-66,7%" cho hợp đồng mới giao 1/3 là kiểu diễn đạt gây hiểu nhầm là giá trị âm.
  const ratio = c.qty > 0 ? (d.delivered_qty / c.qty) * 100 : 0;
  const pctText = c.qty <= 0 ? ""
    : d.over_qty > 1e-9 ? `+${(ratio - 100).toFixed(1)}% so với hợp đồng`
      : `đạt ${ratio.toFixed(1)}% sản lượng hợp đồng`;

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await setContractCompletion(c.id as number, day);
      onDone(); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  return (
    <Modal open width="min(560px, 94vw)" title={`Hoàn thành hợp đồng ${c.code}`} onCancel={onClose}
      okText="Hoàn thành" cancelText="Đóng" onOk={submit} okButtonProps={{ loading: busy }}
      destroyOnHidden>
      <div style={{ fontSize: 13, lineHeight: 1.8 }}>
        <div>Sản lượng hợp đồng: <b>{t3(c.qty)}</b> tấn</div>
        <div>Đã giao: <b>{t3(d.delivered_qty)}</b> tấn
          {pctText && <span style={{ color: "var(--muted)" }}> ({pctText})</span>}
        </div>
        {short && <div>Còn phải giao: <b>{t3(d.remaining_qty)}</b> tấn</div>}
        {d.over_qty > 1e-9 && <div>Giao vượt: <b>{t3(d.over_qty)}</b> tấn</div>}
      </div>

      <label className="form-field" style={{ display: "block", marginTop: 12 }}>Ngày hoàn thành *
        <DateInput value={day} onChange={(v) => setDay(v)} />
      </label>

      <p className="form-note" style={{ fontSize: 12, marginTop: 10 }}>
        {short ? (
          <>Sau khi chốt, <b>{t3(d.remaining_qty)} tấn</b> chưa giao sẽ <b>rời khỏi</b> mục
            “đã ký HĐ chưa giao” kể từ ngày hoàn thành. Chỉ chốt khi hai bên đã kết thúc hợp đồng —
            còn giao tiếp thì để nguyên.</>
        ) : (
          <>Hợp đồng đã giao đủ. Chốt hoàn thành để đánh dấu kết thúc và khoá không cho sửa thêm.</>
        )}{" "}
        Bấm nhầm thì <b>Mở lại hợp đồng</b> ở màn chi tiết.
      </p>
      {d.pending_qty > 1e-9 && (
        <div className="chip warn" style={{ marginTop: 6 }}>
          Còn {t3(d.pending_qty)} tấn ở các đợt <b>chưa điền ngày giao</b> — điền ngày giao trước,
          nếu không sản lượng đó sẽ không vào tiêu thụ.
        </div>
      )}
      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
