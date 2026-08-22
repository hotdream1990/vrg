import { FileProtectOutlined, PlusOutlined } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";

import {
  type Contract,
  type ContractFilters,
  type ContractMeta,
  type ContractRow,
  type ContractTotals,
  deleteContract,
  fetchContractMeta,
  listContracts,
} from "../../../lib/sales-contract-client";
import { dmy } from "../../../lib/date";
import { useEditWindow } from "../../../lib/edit-window";
import { useAuth } from "../../auth/AuthContext";
import CustomerPicker from "../sections/CustomerPicker";
import DateInput from "../sections/DateInput";
import ReadOnlyNotice from "../sections/ReadOnlyNotice";
import ContractDetailModal from "./components/ContractDetailModal";
import ContractFormModal from "./components/ContractFormModal";
import "../../bulletin/bulletin.css";

const PAGE_SIZE = 25;
const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });
/** Tiền quy VNĐ, hiện theo TRIỆU ĐỒNG. null = có dòng ngoại tệ thiếu tỷ giá → "—", KHÔNG hiện 0
 *  (0 sẽ bị đọc là bán không thu tiền). */
const money = (n: number | null) => (n == null ? "—" : t3(n / 1_000_000));
/** Đã giao đủ sản lượng hợp đồng (chưa chốt hoàn thành) — cùng luật với bộ lọc "Đã giao đủ". */
const fullyDelivered = (r: ContractRow) => !r.completed_at && r.remaining_qty <= 1e-9;
/** Số hợp đồng CHƯA vào được tổng tiền (thiếu đơn giá, hoặc bán ngoại tệ mà chưa có tỷ giá vì
 *  chưa tới ngày giao). Phải nói ra: tổng thiếu mà im lặng thì bị đọc là tổng đủ. */
const missingNote = (n: number) => (n === 0 ? null : (
  <div style={{ fontSize: 11, fontWeight: 400, color: "var(--warn, #d48806)" }}>
    chưa gồm {n.toLocaleString("vi-VN")} HĐ chưa quy đổi được
  </div>
));
/** Quá thời hạn hợp đồng mà vẫn còn hàng chưa giao (hợp đồng đã chốt hoàn thành thì thôi). */
const overdue = (r: ContractRow) =>
  r.remaining_qty > 0 && !r.completed_at && !!r.expiry_date
  && r.expiry_date < new Date().toISOString().slice(0, 10);

/** Quản lý hợp đồng → Hợp đồng & đợt giao: danh sách HỢP ĐỒNG + tiến độ giao. */
export default function SalesContractPage() {
  const { canEditCap, user } = useAuth();
  const isMember = user?.role === "member";
  const canEdit = isMember || canEditCap("sales_contract");
  // Cửa sổ sửa CHỈ áp cho lần giao, mốc là ngày giao (khớp `security.assert_edit_window` ở server).
  const { isEditable } = useEditWindow();
  const locked = (deliveredAt: string | null) => !!deliveredAt && !isEditable(deliveredAt);

  const [meta, setMeta] = useState<ContractMeta | null>(null);
  const [rows, setRows] = useState<ContractRow[]>([]);
  // Phân trang Ở SERVER: chỉ tải đúng trang đang xem (danh sách đã hơn 3.000 hợp đồng và dài thêm
  // mỗi ngày). `total` là tổng số hợp đồng khớp bộ lọc, không phải số dòng đang hiện.
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  // Dòng Tổng cộng do SERVER cộng trên TOÀN BỘ hợp đồng khớp lọc — cộng `rows` ở đây chỉ ra tổng
  // của 25 dòng đang hiện, người đọc sẽ tưởng là tổng của cả bộ lọc.
  const [totals, setTotals] = useState<ContractTotals | null>(null);
  const [f, setF] = useState<ContractFilters>({ status: "all" });
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState<{ initial: Contract | null } | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    listContracts({ ...f, page, page_size: PAGE_SIZE })
      .then((r) => { setRows(r.contracts); setTotal(r.total); setTotals(r.totals); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [f, page]);

  useEffect(() => { fetchContractMeta().then(setMeta).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { load(); }, [load]);
  // Đổi bộ lọc thì về trang 1 — nếu không, đang ở trang 7 mà lọc còn 2 trang sẽ ra bảng trống.
  const setFilter = (next: ContractFilters) => { setPage(1); setF(next); };

  const remove = async (r: ContractRow) => {
    if (!confirm(`Xoá hợp đồng ${r.code} của ${r.company}?`)) return;
    try { await deleteContract(r.id as number); load(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
  };

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><FileProtectOutlined style={{ marginRight: 8 }} />Hợp đồng &amp; đợt giao</h2>
          <p>
            Hợp đồng <b>giao nhiều lần</b> thì mở ra để thêm <b>đợt giao</b> — mỗi đợt gồm hoá đơn,
            ngày giao và chi tiết hàng. Giao xong hoặc kết thúc hợp đồng thì bấm{" "}
            <b>Hoàn thành hợp đồng</b> để phần chưa giao rời khỏi “đã ký HĐ chưa giao”.
          </p>
        </div>
        {canEdit && meta && (
          <div className="actions">
            <button className="btn btn-primary" onClick={() => setForm({ initial: null })}>
              <PlusOutlined /> Thêm hợp đồng
            </button>
          </div>
        )}
      </div>

      {!isMember && <ReadOnlyNotice cap="sales_contract" />}

      {meta && (
        <div className="blt-toolbar">
          {!isMember || meta.units.length > 1 ? (
            <label className="blt-date-label">Đơn vị
              <select className="blt-date-input" value={f.company ?? ""}
                onChange={(e) => setFilter({
                  // Đổi đơn vị thì bỏ luôn khách đã chọn — khách là của RIÊNG từng đơn vị, giữ
                  // lại sẽ ra danh sách rỗng mà người dùng không hiểu vì sao.
                  ...f, company: e.target.value || undefined, customer_ids: [],
                })}>
                <option value="">Tất cả</option>
                {meta.units.map((u) => <option key={u} value={u}>{u}</option>)}
              </select>
            </label>
          ) : null}
          <label className="blt-date-label">Khách hàng
            <CustomerPicker multiple width={320} value={f.customer_ids ?? []} company={f.company}
              onChange={(ids) => setFilter({ ...f, customer_ids: ids })} />
          </label>
          <label className="blt-date-label">Trạng thái
            <select className="blt-date-input" value={f.status ?? "all"}
              onChange={(e) => setFilter({ ...f, status: e.target.value as ContractFilters["status"] })}>
              <option value="all">Tất cả</option>
              <option value="open">Còn hàng chưa giao</option>
              <option value="done">Đã giao đủ</option>
              <option value="completed">Đã hoàn thành</option>
            </select>
          </label>
          {/* Hình thức nằm ở LẦN GIAO; hợp đồng giao nhiều lần được tính theo hình thức của
              các đợt (xem `parents_with_progress`). "Chưa khai" để rà lại hợp đồng cũ. */}
          <label className="blt-date-label">Hình thức
            <select className="blt-date-input" value={f.channels?.[0] ?? ""}
              onChange={(e) => setFilter({
                ...f, channels: e.target.value === "" ? [] : [e.target.value === "_none" ? "" : e.target.value],
              })}>
              <option value="">Tất cả</option>
              {Object.entries(meta.channels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              <option value="_none">— Chưa khai hình thức —</option>
            </select>
          </label>
          <label className="blt-date-label">Ngày ký từ
            <DateInput value={f.date_from ?? ""} onChange={(v) => setFilter({ ...f, date_from: v || undefined })} />
          </label>
          <label className="blt-date-label">đến
            <DateInput value={f.date_to ?? ""} onChange={(v) => setFilter({ ...f, date_to: v || undefined })} />
          </label>
          <input className="blt-date-input" style={{ width: 200 }} placeholder="Tìm theo số HĐ"
            value={f.q ?? ""} onChange={(e) => setFilter({ ...f, q: e.target.value || undefined })} />
          <span style={{ color: "var(--muted)", fontSize: 13 }}>
            {loading ? "Đang tải…" : `${total.toLocaleString("vi-VN")} hợp đồng`}
          </span>
        </div>
      )}

      {err && <div className="blt-error">{err}</div>}

      <div className="card table-scroll" style={{ padding: 0 }}>
        <table>
          <thead><tr>
            <th>Đơn vị</th><th>Số hợp đồng</th><th>Khách hàng</th><th>Loại giao</th>
            <th>Hình thức</th>
            <th>Ngày ký</th><th className="r">SL hợp đồng (tấn)</th><th className="r">Thành tiền (tr.đ)</th>
            <th className="r">TT đã giao (tr.đ)</th>
            <th className="r">Đã giao</th>
            <th className="r">Còn phải giao</th><th className="r">Đợt giao</th><th>Trạng thái</th>
            <th className="r" style={{ width: 160 }}>Thao tác</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.company}</td>
                <td style={{ fontWeight: 500 }}>{r.code}</td>
                <td>{r.customer_name ?? "—"}</td>
                <td>
                  <span className="chip" title={meta?.delivery_types[r.delivery_type]}>
                    {r.delivery_type === "multi" ? "Nhiều lần" : "1 lần"}
                  </span>
                </td>
                <td style={{ whiteSpace: "nowrap", fontSize: 12.5 }}>
                  {/* Gộp hình thức của mọi đợt giao; hợp đồng chưa giao lần nào thì chưa có. */}
                  {r.channels.length
                    ? r.channels.map((c) => (
                        <span key={c} className="chip" style={{ marginRight: 4 }}>
                          {meta?.channels[c] ?? c}
                        </span>))
                    : <span style={{ color: "var(--muted)" }}>—</span>}
                </td>
                <td>{dmy(r.sign_date) || "—"}</td>
                <td className="r">{t3(r.qty)}</td>
                {/* Thành tiền = tổng dòng chi tiết CỦA HỢP ĐỒNG (tiền đã ký). */}
                <td className="r">{r.revenue == null ? "—" : t3(r.revenue / 1_000_000)}</td>
                {/* TT đã giao = tiền của HÀNG THỰC GIAO. Đơn giá/sản lượng chốt lại ở từng đợt nên
                    lệch với tiền hợp đồng là bình thường — nêu rõ phần chênh để khỏi phải tự trừ. */}
                <td className="r">
                  {money(r.delivered_revenue)}
                  {r.revenue != null && r.delivered_revenue != null
                    && Math.abs(r.delivered_revenue - r.revenue) > 1000 && (
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      {r.delivered_revenue > r.revenue ? "+" : "−"}
                      {money(Math.abs(r.delivered_revenue - r.revenue))} so với HĐ
                    </div>
                  )}
                </td>
                <td className="r">
                  {t3(r.delivered_qty)}
                  {/* Thực giao được phép lệch so với hợp đồng — nêu rõ phần vượt để khỏi tưởng nhầm
                      là gõ sai số. */}
                  {r.over_qty > 0 && (
                    <div style={{ fontSize: 11, color: "var(--warn, #d48806)" }}>
                      vượt {t3(r.over_qty)}
                    </div>
                  )}
                </td>
                <td className="r">
                  {/* Còn phải giao = SL hợp đồng − đã giao. Còn hàng là trạng thái BÌNH THƯỜNG của
                      hợp đồng mới ký — chỉ tô cảnh báo khi đã QUÁ THỜI HẠN. */}
                  <span className={overdue(r) ? "chip warn" : "chip"}>{t3(r.remaining_qty)}</span>
                  {r.pending_qty > 0 && (
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>
                      chờ giao {t3(r.pending_qty)}
                    </div>
                  )}
                </td>
                <td className="r">{r.delivery_type === "multi" ? r.children : "—"}</td>
                <td style={{ whiteSpace: "nowrap", fontSize: 12.5 }}>
                  {/* Giao hết hàng rồi mà vẫn ghi "đang thực hiện" thì người đọc tưởng còn nợ hàng.
                      Hợp đồng vẫn CHƯA chốt hoàn thành (chốt là khoá sửa) nên tách thành 3 trạng
                      thái, đúng bằng 3 lựa chọn ở bộ lọc phía trên. */}
                  {r.completed_at
                    ? <span className="chip">Hoàn thành {dmy(r.completed_at)}</span>
                    : fullyDelivered(r)
                      ? <span className="chip info" title={"Đã giao đủ sản lượng hợp đồng"
                          + (r.delivered_at ? ` (ngày ${dmy(r.delivered_at)})` : "")
                          + " — mở hợp đồng bấm “Hoàn thành hợp đồng” để chốt."}>Đã giao đủ</span>
                      : <span style={{ color: "var(--muted)" }}>Đang thực hiện</span>}
                </td>
                <td className="r" style={{ whiteSpace: "nowrap" }}>
                  <button className="btn" onClick={() => setOpenId(r.id as number)}>Xem</button>{" "}
                  {/* HĐ giao-1-lần ĐÃ GIAO là một lần giao → quá cửa sổ sửa thì chỉ còn xem.
                      HĐ giao-nhiều-lần không bị khoá: còn phải thêm đợt giao suốt vòng đời. */}
                  {/* Hợp đồng đã chốt hoàn thành thì khoá — mở lại ở màn chi tiết mới sửa được. */}
                  {canEdit && (locked(r.delivered_at)
                    ? <span style={{ color: "var(--muted)", fontSize: 11 }}>(chỉ xem)</span>
                    : r.completed_at
                      ? <span style={{ color: "var(--muted)", fontSize: 11 }}>(đã chốt)</span>
                      : <>
                          <button className="btn" onClick={() => setForm({ initial: r })}>Sửa</button>{" "}
                          <button className="btn" onClick={() => remove(r)}>Xoá</button>
                        </>)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr><td colSpan={14} style={{ textAlign: "center", color: "var(--muted)", padding: 20 }}>
                Chưa có hợp đồng nào khớp bộ lọc.
              </td></tr>
            )}
          </tbody>
          {/* TỔNG CỘNG của CẢ BỘ LỌC (server cộng), không phải của trang đang xem — nói rõ trên
              nhãn vì bảng có phân trang, người đọc rất dễ hiểu là tổng của 25 dòng đang thấy. */}
          {totals && rows.length > 0 && (
            <tfoot>
              <tr style={{ fontWeight: 600 }}>
                <td colSpan={6}>
                  Tổng cộng
                  <span style={{ fontWeight: 400, color: "var(--muted)", fontSize: 12 }}>
                    {" "}· {total.toLocaleString("vi-VN")} hợp đồng khớp bộ lọc
                    {total > PAGE_SIZE && " (không chỉ trang này)"}
                  </span>
                </td>
                <td className="r">{t3(totals.qty)}</td>
                <td className="r">{money(totals.revenue)}{missingNote(totals.revenue_missing)}</td>
                <td className="r">
                  {money(totals.delivered_revenue)}
                  {missingNote(totals.delivered_revenue_missing)}
                </td>
                <td className="r">{t3(totals.delivered_qty)}</td>
                <td className="r">{t3(totals.remaining_qty)}</td>
                <td className="r">{totals.children.toLocaleString("vi-VN")}</td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Thanh trang — server chỉ trả đúng trang đang xem nên đây là cách duy nhất để xem tiếp. */}
      {total > PAGE_SIZE && (
        <div className="blt-toolbar" style={{ justifyContent: "flex-end", gap: 10 }}>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>
            Dòng {((page - 1) * PAGE_SIZE + 1).toLocaleString("vi-VN")}–
            {Math.min(page * PAGE_SIZE, total).toLocaleString("vi-VN")} / {total.toLocaleString("vi-VN")}
          </span>
          <button className="btn" disabled={page <= 1 || loading} onClick={() => setPage(1)}>« Đầu</button>
          <button className="btn" disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}>‹ Trước</button>
          <span style={{ fontSize: 13 }}>Trang {page} / {Math.ceil(total / PAGE_SIZE)}</span>
          <button className="btn" disabled={page >= Math.ceil(total / PAGE_SIZE) || loading}
            onClick={() => setPage((p) => p + 1)}>Sau ›</button>
          <button className="btn" disabled={page >= Math.ceil(total / PAGE_SIZE) || loading}
            onClick={() => setPage(Math.ceil(total / PAGE_SIZE))}>Cuối »</button>
        </div>
      )}

      {meta && openId != null && (
        <ContractDetailModal contractId={openId} meta={meta} canEdit={canEdit}
          onClose={() => setOpenId(null)} onChanged={load} />
      )}
      {meta && form && (
        <ContractFormModal meta={meta} initial={form.initial}
          onClose={() => setForm(null)} onSaved={load} />
      )}
    </div>
  );
}
