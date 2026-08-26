import { WarningFilled } from "@ant-design/icons";
import { Modal } from "antd";
import { useEffect, useState } from "react";

import {
  type LockSummary, confirmLock, fetchLockSummary,
} from "../../../lib/data-lock-client";

type Props = {
  company: string;
  roundId: number;
  /** Chỉ XEM lại số đã chốt (Ban TTKD / đơn vị đã xác nhận) — ẩn nút xác nhận. */
  readOnly?: boolean;
  onClose: () => void;
  onConfirmed?: () => void;
};

const dmy = (iso?: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const n3 = (v: unknown, unit = "") =>
  (typeof v === "number" && Number.isFinite(v)
    ? `${v.toLocaleString("vi-VN", { maximumFractionDigits: 3 })}${unit ? ` ${unit}` : ""}`
    : "—");

/** Dòng "còn thiếu ngày nào" — chỉ liệt kê vài ngày GẦN NHẤT, phần còn lại đếm.
 *  Kỳ chốt đầu tiên tính từ 01/01 nên đơn vị nhập thưa có thể thiếu vài trăm ngày; đổ hết ra thì
 *  bảng xác nhận dài mấy màn hình và không ai đọc. */
function MissingLine({ label, days, total, since, periodFrom }: {
  label: string; days: string[]; total: number; since?: string; periodFrom?: string;
}) {
  if (!total) return null;
  const rest = total - days.length;
  return (
    <div>
      {label}: <b>{total}</b> ngày
      {/* Mốc rà muộn hơn đầu kỳ (biểu Tồn kho mới thu thập từ 24/07/2026) thì phải nói ra, không
          thì người đọc tưởng những ngày trước đó đã nộp đủ. */}
      {since && periodFrom && since > periodFrom && <> (chỉ tính từ {dmy(since)})</>}
      {days.length > 0 && <> — gần nhất: {days.map(dmy).join(" · ")}</>}
      {rest > 0 && <> … và {rest} ngày khác</>}
    </div>
  );
}

/** Một ô chỉ tiêu trong bảng xác nhận. */
function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="kpi">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

function Block({ title, hint, children }: {
  title: string; hint?: string; children: React.ReactNode;
}) {
  return (
    <div style={{ marginTop: 14 }}>
      <h4 style={{ margin: "0 0 6px" }}>{title}</h4>
      {hint && <div style={{ fontSize: 11.5, color: "var(--muted)", marginBottom: 6 }}>{hint}</div>}
      <div className="kpi-row ct-kpi">{children}</div>
    </div>
  );
}

/**
 * Bảng SỐ LIỆU SẼ CHỐT + nút xác nhận.
 *
 * Vì sao phải bày số ra trước khi bấm: xác nhận xong là đơn vị hết tự sửa, muốn đổi phải nhờ Ban
 * TTKD. Bấm "đồng ý" mà không thấy mình đang chốt cái gì thì chữ ký đó vô nghĩa (yêu cầu
 * 25/08/2026). Số ở đây lấy đúng chỉ tiêu của *Báo cáo tổng hợp* — không tự cộng một bộ khác.
 */
export default function DataLockConfirmModal({ company, roundId, readOnly, onClose, onConfirmed }: Props) {
  const [data, setData] = useState<LockSummary | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchLockSummary(company, roundId)
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setErr(e instanceof Error ? e.message : "Lỗi tải số liệu"); });
    return () => { alive = false; };
  }, [company, roundId]);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await confirmLock(roundId, company);
      onConfirmed?.(); onClose();
    } catch (e) { setErr(e instanceof Error ? e.message : "Lỗi"); }
    finally { setBusy(false); }
  };

  const p = data?.purchase ?? {};
  const c = data?.consumption ?? {};
  const s = data?.stock ?? {};

  return (
    <Modal open width="min(1000px, 94vw)" destroyOnHidden
      title={`Số liệu chốt đến hết ngày ${dmy(data?.lock_date)} — ${company}`}
      onCancel={onClose} onOk={submit}
      okText="Xác nhận chốt số liệu" cancelText="Đóng"
      okButtonProps={{ loading: busy, danger: true, style: readOnly ? { display: "none" } : undefined }}>
      {!data && !err && <div style={{ padding: 24 }}>Đang tải số liệu…</div>}
      {data && (
        <>
          <div style={{ fontSize: 13 }}>
            Kỳ chốt: <b>{dmy(data.date_from)} – {dmy(data.lock_date)}</b>
            {data.prev_lock_date && <> (nối tiếp lần chốt trước ngày <b>{dmy(data.prev_lock_date)}</b>)</>}
            . Đã nhập <b>{data.days_entered.consumption}</b> ngày biểu Tồn kho
            {data.has_purchase_plan && <>, <b>{data.days_entered.purchase}</b> ngày biểu Thu mua</>}.
          </div>

          {data.missing_total > 0 && (
            <div className="blt-error" style={{ marginTop: 10, fontSize: 12.5 }}>
              <b><WarningFilled /> Còn {data.missing_total} ngày chưa nộp trong kỳ này</b>
              <div style={{ marginTop: 4 }}>
                <MissingLine label="Thu mua" days={data.missing.purchase}
                  total={data.missing_counts.purchase}
                  since={data.missing_from?.purchase} periodFrom={data.date_from} />
                <MissingLine label="Tồn kho" days={data.missing.consumption}
                  total={data.missing_counts.consumption}
                  since={data.missing_from?.consumption} periodFrom={data.date_from} />
              </div>
              <div style={{ marginTop: 4 }}>
                Nên nhập bù trước khi chốt — <b>chốt xong đơn vị không tự nhập được nữa</b>.
              </div>
            </div>
          )}

          {data.has_purchase_plan && (
            <Block title="Thu mua (cộng dồn trong kỳ)"
              hint="Cộng các ngày đơn vị đã nhập ở biểu Thu mua.">
              <Kpi label="Mủ nước (tấn)" value={n3(p.latex_wet)} />
              <Kpi label="Mủ chén (tấn)" value={n3(p.coagulum)} />
              <Kpi label="Thành phẩm (tấn)" value={n3(p.finished_qty)} />
              <Kpi label="Tổng thu mua (tấn)" value={n3(p.total_purchase)} />
              <Kpi label="Giá BQ mủ nước (đ/độ)" value={n3(p.price_latex_avg)} />
              <Kpi label="Giá BQ mủ chén (đ/độ)" value={n3(p.price_cup_avg)} />
              <Kpi label="% kế hoạch năm" value={n3(p.pct_plan, "%")} />
              <Kpi label="Ngày không thu mua" value={n3(p.no_purchase_days)} />
            </Block>
          )}

          <Block title="Tiêu thụ (cộng dồn trong kỳ)"
            hint={"Đơn vị KHÔNG nhập tay: số này tính từ các LẦN GIAO của hợp đồng. Chốt xong, "
              + "các lần giao có ngày giao trong kỳ này không sửa được nữa."}>
            <Kpi label="Tổng tiêu thụ (tấn)" value={n3(c.total_consumption)} />
            <Kpi label="Xuất khẩu (tấn)" value={n3(c.export_total)} />
            <Kpi label="Trong nước (tấn)" value={n3(c.domestic_total)} />
            <Kpi label="Nội bộ (tấn)" value={n3(c.internal_total)} />
            <Kpi label="HĐ dài hạn (tấn)" value={n3(c.lt_total)} />
            <Kpi label="HĐ chuyến (tấn)" value={n3(c.spot_total)} />
            <Kpi label="Doanh thu (tỷ đồng)" value={n3(c.revenue_ty)} />
            <Kpi label="Giá bán BQ (tr.đ/tấn)" value={n3(c.avg_sell_price)} />
          </Block>

          <Block title="Tồn kho tại ngày chốt"
            hint={`Lấy từ biểu Tồn kho đơn vị nhập theo ngày. Là số THỜI ĐIỂM — lấy lần nhập tồn `
              + `gần nhất${s.stock_as_of ? ` (ngày ${dmy(String(s.stock_as_of))})` : ""}, không cộng dồn.`}>
            <Kpi label="Tồn thành phẩm (tấn)" value={n3(s.stock_finished)} />
            <Kpi label="Chưa nhập kho (tấn)" value={n3(s.stock_not_warehoused)} />
            <Kpi label="Đã nhập kho (tấn)" value={n3(s.stock_warehoused)} />
            <Kpi label="Tồn nguyên liệu (tấn)" value={n3(s.stock_material)} />
            <Kpi label="Đã ký HĐ chưa giao (tấn)" value={n3(s.stock_finished_hd)} />
          </Block>

          {!readOnly && (
            <div className="form-note" style={{ marginTop: 14, fontSize: 12.5 }}>
              Bấm <b>Xác nhận chốt số liệu</b> nghĩa là đơn vị xác nhận các con số trên đã đúng đến
              hết ngày <b>{dmy(data.lock_date)}</b>. Sau khi chốt, <b>đơn vị không sửa được số liệu
              của những ngày này nữa</b> — cần điều chỉnh thì báo Ban TTKD để chuyên viên sửa hộ.
            </div>
          )}
          {data.round?.note && (
            <div style={{ marginTop: 10, fontSize: 12.5 }}>
              <b>Lời nhắn của Ban TTKD:</b> {data.round.note}
            </div>
          )}
        </>
      )}
      {err && <div className="blt-error" style={{ marginTop: 10 }}>{err}</div>}
    </Modal>
  );
}
