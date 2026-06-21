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
      <label className="blt-date-label">Từ ngày:
        <input type="date" className="blt-date-input" value={from} onChange={(e) => onFrom(e.target.value)} />
      </label>
      <label className="blt-date-label">Đến ngày:
        <input type="date" className="blt-date-input" value={to} onChange={(e) => onTo(e.target.value)} />
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
