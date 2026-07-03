import DateInput from "./DateInput";

/** Thanh lọc khoảng ngày dùng chung cho các trang Quản lý số liệu. */
export default function DateRangeBar({
  from, to, onFrom, onTo, onReload, info, children,
}: {
  from: string; to: string;
  onFrom: (v: string) => void; onTo: (v: string) => void;
  onReload?: () => void; info?: string; children?: React.ReactNode;
}) {
  return (
    <div className="blt-toolbar">
      <label className="blt-date-label">Từ ngày:{" "}
        <DateInput value={from} onChange={onFrom} allowClear />
      </label>
      <label className="blt-date-label">Đến ngày:{" "}
        <DateInput value={to} onChange={onTo} allowClear />
      </label>
      {(from || to) && (
        <button className="btn" onClick={() => { onFrom(""); onTo(""); }}>Xoá lọc (30 ngày)</button>
      )}
      {onReload && <button className="btn" onClick={onReload}>↻ Tải lại</button>}
      {children}
      {info && <span style={{ color: "var(--muted)", fontSize: 13 }}>{info}</span>}
    </div>
  );
}
