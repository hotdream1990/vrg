/* Mảnh giao diện dùng chung của card "Tiến độ bán hàng năm": thanh % (to · mini trong bảng) và dòng
   phương trình nhỏ "a + b = c". % luôn hiện SỐ THẬT kể cả khi vượt 100% (thanh thì đầy ở 100%).
   Không có vạch tiến độ thời gian: đây là số CẢ NĂM dự kiến / cam kết, không phải lũy kế tới hôm nay. */

import { Progress } from "antd";

import { fmtPct } from "./dashboard-format";

const clampPct = (pct: number) => Math.min(Math.max(pct, 0), 100);

/** Thanh to + số % (bố cục như một dòng của card Chỉ tiêu năm). */
export function PctProgress({ pct }: { pct: number }) {
  return (
    <div className="ud-target-body">
      <div className="ud-target-bar">
        <Progress percent={clampPct(pct)} showInfo={false} status="normal" strokeColor="var(--accent)" />
      </div>
      <span className="ud-target-pct">{fmtPct(pct)}</span>
    </div>
  );
}

/** Ô % trong bảng: thanh mini + số; chưa có số → "—" (không vẽ thanh 0). */
export function MiniPct({ pct }: { pct: number | null | undefined }) {
  if (pct == null) return <span className="ud-muted">—</span>;
  return (
    <span className="ud-pct-cell">
      <span className="ud-mini-bar"><span style={{ width: `${clampPct(pct)}%` }} /></span>
      <span className="ud-pct-text">{fmtPct(pct)}</span>
    </span>
  );
}

export type EqTerm = { label: string; value: string };

type MiniEquationProps = {
  /** Số hạng cộng lại; số hạng CUỐI là tổng (in đậm, đứng sau dấu "="). */
  terms: EqTerm[];
  unit: string;
  /** Chữ dẫn trước phương trình, vd "Cả phạm vi" khi khác gốc với dòng % phía trên. */
  lead?: string;
};

export function MiniEquation({ terms, unit, lead }: MiniEquationProps) {
  const last = terms.length - 1;
  return (
    <div className="ud-mini-eq">
      {lead && <span className="ud-mini-eq-lead">{lead}</span>}
      {/* Dấu +/= đi LIỀN số hạng sau nó: phương trình 4 số hạng xuống dòng thì không để "=" treo
          cuối dòng trên, tổng rơi xuống dòng dưới. */}
      {terms.map((t, i) => (
        <span key={t.label} className="ud-mini-eq-item">
          {i > 0 && <span className="ud-eq-op" aria-hidden>{i === last ? "=" : "+"}</span>}
          <span className={`ud-mini-eq-term${i === last ? " is-total" : ""}`}>
            <span>{t.label}</span>
            <b>{t.value}</b>
          </span>
        </span>
      ))}
      <span className="ud-mini-eq-unit">{unit}</span>
    </div>
  );
}
