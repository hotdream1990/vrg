/* Khung chung của mỗi khối trên Dashboard đơn vị: tiêu đề + trạng thái tải RIÊNG của khối
   (đang tải / lỗi / trống) + cảnh báo server gửi kèm (gộp một hộp, không lặp). */

import { Alert } from "antd";
import type { ReactNode } from "react";

import type { BlockState } from "./use-dashboard-block";

type Props<T> = {
  title: ReactNode;
  sub?: ReactNode;
  extra?: ReactNode;
  state: BlockState<T>;
  warnings?: (data: T) => string[];
  children: (data: T) => ReactNode;
  id?: string;
};

/** Gộp cảnh báo trùng — nhiều khối có thể nhắc cùng một câu (vd đơn vị chưa nộp). */
export function BlockWarnings({ warnings }: { warnings: string[] }) {
  const list = [...new Set(warnings.filter(Boolean))];
  if (!list.length) return null;
  return (
    <Alert
      type="warning" showIcon className="ud-alert"
      title={list.length === 1 ? list[0]
        : <ul className="ud-warn-list">{list.map((w) => <li key={w}>{w}</li>)}</ul>}
    />
  );
}

export default function DashboardCard<T>({ title, sub, extra, state, warnings, children, id }: Props<T>) {
  const { data, loading, error } = state;
  return (
    <section className="card ud-section" id={id}>
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {sub && <div className="sub ud-sub">{sub}</div>}
        </div>
        {extra}
      </div>
      {loading ? (
        <div className="scan-empty">Đang tải…</div>
      ) : error ? (
        <div className="scan-empty ud-error">Chưa tải được: {error}</div>
      ) : !data ? (
        <div className="scan-empty">Chọn phạm vi và kỳ hợp lệ để xem số liệu.</div>
      ) : (
        <>
          {warnings && <BlockWarnings warnings={warnings(data)} />}
          {children(data)}
        </>
      )}
    </section>
  );
}
