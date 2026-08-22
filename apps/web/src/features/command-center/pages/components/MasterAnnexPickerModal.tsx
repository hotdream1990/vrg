import { Modal } from "antd";
import { useCallback, useEffect, useState } from "react";

import { dmy } from "../../../../lib/date";
import { type MasterContract, linkMasterAnnexes } from "../../../../lib/master-contract-client";
import { type ContractRow, listContracts } from "../../../../lib/sales-contract-client";

const PAGE_SIZE = 25;
const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

type Props = {
  master: MasterContract;
  onClose: () => void;
  onLinked: () => void;
};

/** Chọn HỢP ĐỒNG ĐÃ CÓ để gắn thành PHỤ LỤC của hợp đồng mẹ.
 *
 *  Vì sao cần: hàng nghìn hợp đồng đã nhập trước khi hệ thống có cấp hợp đồng mẹ — bắt sửa từng
 *  cái bằng form hợp đồng thì không ai dọn nổi. Danh sách chỉ bày hợp đồng **của đúng đơn vị** và
 *  **chưa thuộc hồ sơ nào** (`unlinked`), nên không thể lỡ tay kéo phụ lục của hồ sơ khác sang.
 */
export default function MasterAnnexPickerModal({ master, onClose, onLinked }: Props) {
  const [rows, setRows] = useState<ContractRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    // Lọc Ở SERVER theo đơn vị của hợp đồng mẹ + chưa gắn hồ sơ nào (đơn vị có tới vài trăm HĐ).
    listContracts({ company: master.company, unlinked: true, q: q.trim() || undefined,
                    page, page_size: PAGE_SIZE })
      .then((r) => { setRows(r.contracts); setTotal(r.total); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [master.company, q, page]);
  useEffect(() => { load(); }, [load]);

  const toggle = (id: number) =>
    setPicked((v) => (v.includes(id) ? v.filter((x) => x !== id) : [...v, id]));

  const submit = async () => {
    if (!picked.length) { setErr("Chọn ít nhất một hợp đồng."); return; }
    setBusy(true); setErr("");
    try {
      await linkMasterAnnexes(master.id as number, picked);
      onLinked(); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Modal open width="min(1000px, 94vw)" destroyOnHidden
      title={`Gắn phụ lục vào hợp đồng mẹ ${master.code}`}
      onCancel={onClose} onOk={submit} cancelText="Đóng"
      okText={picked.length ? `Gắn ${picked.length} hợp đồng` : "Gắn phụ lục"}
      okButtonProps={{ loading: busy, disabled: !picked.length }}>
      <div className="blt-toolbar" style={{ marginTop: 0 }}>
        <input className="blt-date-input" style={{ width: 240 }} placeholder="Tìm theo số hợp đồng"
          value={q} onChange={(e) => { setPage(1); setQ(e.target.value); }} />
        <span style={{ color: "var(--muted)", fontSize: 13 }}>
          {loading ? "Đang tải…" : `${total.toLocaleString("vi-VN")} hợp đồng chưa gắn hồ sơ nào`}
        </span>
        {pages > 1 && (
          <>
            <button className="btn" disabled={page <= 1}
              onClick={() => setPage((v) => Math.max(1, v - 1))}>‹ Trước</button>
            <span style={{ fontSize: 13 }}>Trang {page} / {pages}</span>
            <button className="btn" disabled={page >= pages}
              onClick={() => setPage((v) => v + 1)}>Sau ›</button>
          </>
        )}
      </div>

      {/* Cảnh báo phải nằm TRƯỚC khi bấm: gắn vào là đổi khách hàng của hợp đồng đó, người dùng
          không thể đoán ra điều này từ chữ "gắn phụ lục". */}
      <p className="form-note" style={{ fontSize: 12, margin: "0 0 8px" }}>
        Hợp đồng được gắn sẽ thành <b>phụ lục</b> của hồ sơ này và <b>khách hàng đổi thành{" "}
        “{master.customer_name ?? "khách của hợp đồng mẹ"}”</b> (phụ lục thừa kế khách hàng của hợp
        đồng mẹ). Danh sách chỉ hiện hợp đồng của <b>{master.company}</b> chưa thuộc hồ sơ nào.
      </p>

      <div className="card table-scroll" style={{ padding: 0, maxHeight: 360 }}>
        <table className="mc-pick">
          <thead><tr>
            <th style={{ width: 36 }} />
            <th style={{ width: 180 }}>Số hợp đồng</th>
            <th style={{ width: 220 }}>Khách hàng hiện tại</th>
            <th style={{ width: 110 }}>Loại HĐ</th>
            <th style={{ width: 105 }}>Ngày ký</th>
            <th className="r" style={{ width: 95 }}>SL (tấn)</th>
            <th style={{ width: 134 }}>Trạng thái</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} onClick={() => toggle(r.id as number)} style={{ cursor: "pointer" }}>
                {/* Bấm thẳng vào ô tick: `onChange` đổi trạng thái RỒI click bubble lên <tr>
                    đổi lần nữa → net bằng 0, tick mãi không ăn. Chặn bubble để mỗi cú bấm chỉ
                    đổi đúng một lần, dù bấm vào ô tick hay vào dòng. */}
                <td><input type="checkbox" checked={picked.includes(r.id as number)}
                  onClick={(e) => e.stopPropagation()}
                  onChange={() => toggle(r.id as number)} /></td>
                <td style={{ fontWeight: 500 }}>{r.code}</td>
                <td>{r.customer_name ?? "—"}</td>
                <td>{r.contract_type === "long_term" ? "HĐ dài hạn"
                  : r.contract_type === "spot" ? "HĐ chuyến" : "—"}</td>
                <td style={{ whiteSpace: "nowrap" }}>{dmy(r.sign_date) || "—"}</td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>{t3(r.qty)}</td>
                <td style={{ fontSize: 12.5 }}>
                  {r.completed_at ? `Hoàn thành ${dmy(r.completed_at)}` : "Đang thực hiện"}
                </td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr><td colSpan={7} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Không còn hợp đồng nào của đơn vị này chưa gắn hồ sơ.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {picked.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 13 }}>
          Đã chọn <b>{picked.length}</b> hợp đồng
          {/* Các trang khác vẫn giữ lựa chọn — nói ra để người dùng biết mình đang gắn cả những
              dòng không còn nhìn thấy trên màn hình. */}
          {pages > 1 && <span style={{ color: "var(--muted)" }}> (gồm cả trang khác)</span>}
        </div>
      )}
      {err && <div className="blt-error" style={{ marginTop: 8 }}>{err}</div>}
    </Modal>
  );
}
