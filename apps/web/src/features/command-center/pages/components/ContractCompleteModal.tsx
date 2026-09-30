import { Modal } from "antd";
import { useState } from "react";

import {
  type ContractDetail, type ContractMeta, setContractCompletion,
} from "../../../../lib/sales-contract-client";
import DateInput from "../../sections/DateInput";

type Props = {
  d: ContractDetail;
  meta: ContractMeta;
  onClose: () => void;
  onDone: () => void;
};

const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
const today = () => new Date().toISOString().slice(0, 10);

/** Chốt HOÀN THÀNH hợp đồng: chọn ngày kết thúc, phần chênh còn lại rời khỏi "đã ký HĐ chưa giao".
 *
 *  Có màn riêng thay vì một nút bấm là xong, vì ngày chốt đi thẳng vào số liệu: khối "đã ký HĐ
 *  chưa giao" của mọi ngày TỪ ngày đó trở đi sẽ không còn phần chênh này. */
export default function ContractCompleteModal({ d, meta, onClose, onDone }: Props) {
  const c = d.contract;
  const [day, setDay] = useState(today());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  // HĐ giao 1 lần chưa có ngày giao: chốt hoàn thành = ghi nhận đã giao (chốt 27/08/2026).
  const needDelivery = c.delivery_type === "single" && !c.delivered_at;
  const [noDelivery, setNoDelivery] = useState(false);   // huỷ / không giao nữa
  const [giaoDay, setGiaoDay] = useState("");            // để trống = lấy đúng ngày hoàn thành
  const [channel, setChannel] = useState("");
  const [toCompany, setToCompany] = useState("");
  const peers = meta.internal_targets?.[c.company] ?? [];
  // Không giao trước ngày hiệu lực muộn nhất của các dòng — server chặn, chặn luôn trên lịch.
  const minGiao = c.lines.reduce((m, l) => (l.from_date && l.from_date > m ? l.from_date : m), "");

  const short = d.remaining_qty > 1e-9;
  // Giao thiếu thì nói "đạt x%" (số dương, dễ đọc); giao vượt mới nói "+x% so với hợp đồng".
  // Ghi "-66,7%" cho hợp đồng mới giao 1/3 là kiểu diễn đạt gây hiểu nhầm là giá trị âm.
  const ratio = c.qty > 0 ? (d.delivered_qty / c.qty) * 100 : 0;
  const pctText = c.qty <= 0 ? ""
    : d.over_qty > 1e-9 ? `+${(ratio - 100).toFixed(1)}% so với hợp đồng`
      : `đạt ${ratio.toFixed(1)}% sản lượng hợp đồng`;

  const submit = async () => {
    if (needDelivery && !noDelivery) {
      if (!channel) { setErr("Chọn Hình thức tiêu thụ, hoặc tích “hợp đồng huỷ / không giao nữa”."); return; }
      if (channel === "internal" && !toCompany) { setErr("Chọn đơn vị nhận hàng."); return; }
    }
    setBusy(true); setErr("");
    try {
      await setContractCompletion(c.id as number, day, needDelivery
        ? (noDelivery
          ? { no_delivery: true }
          : { delivered_at: giaoDay || day, channel, to_company: channel === "internal" ? toCompany : null })
        : undefined);
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

      {/* HĐ giao 1 lần chưa có ngày giao: chốt hoàn thành CHÍNH LÀ ghi nhận đã giao, nên hỏi luôn
          ngày giao + hình thức ở đây thay vì bắt đơn vị làm hai bước. Trước 27/08/2026 chốt suông
          là sản lượng rơi khỏi tiêu thụ mà không ai hay (Thanh Hoá mất 198,66 tấn vì đúng chỗ này). */}
      {needDelivery && (
        <div className="card" style={{ marginTop: 12, padding: 12 }}>
          <div style={{ fontSize: 13, marginBottom: 8 }}>
            <b>Hợp đồng giao 1 lần chưa có ngày giao.</b> Chốt hoàn thành nghĩa là{" "}
            <b>hàng đã giao</b> — điền nốt hai ô dưới đây để <b>{t3(c.qty)} tấn</b> vào tiêu thụ.
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13,
            marginBottom: noDelivery ? 0 : 10 }}>
            <input type="checkbox" checked={noDelivery}
              onChange={(e) => setNoDelivery(e.target.checked)} />
            Hợp đồng <b>huỷ / không giao nữa</b> — chốt mà không ghi lần giao
          </label>
          {!noDelivery && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
              gap: 10 }}>
              <label className="form-field">Ngày giao
                <DateInput value={giaoDay || day} onChange={setGiaoDay} minDate={minGiao || undefined} />
              </label>
              <label className="form-field">Hình thức tiêu thụ *
                <select className="blt-date-input" value={channel}
                  onChange={(e) => { setChannel(e.target.value); setToCompany(""); }}>
                  <option value="">— chọn hình thức —</option>
                  {Object.entries(meta.channels)
                    .filter(([k]) => k !== "internal" || peers.length > 0)
                    .map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              {channel === "internal" && (
                <label className="form-field">Đơn vị nhận *
                  <select className="blt-date-input" value={toCompany}
                    onChange={(e) => setToCompany(e.target.value)}>
                    <option value="">— chọn đơn vị —</option>
                    {peers.map((u) => <option key={u} value={u}>{u}</option>)}
                  </select>
                </label>
              )}
            </div>
          )}
          {noDelivery && (
            <div className="form-note" style={{ fontSize: 12, marginTop: 8 }}>
              Chốt xong, <b>{t3(c.qty)} tấn</b> này <b>không vào tiêu thụ</b> và rời khỏi mục
              “đã ký HĐ chưa giao”.
            </div>
          )}
        </div>
      )}

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
