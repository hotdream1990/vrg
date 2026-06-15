import { topbar } from "../../data/sample-data";

/** Thanh trên cùng: thương hiệu + trạng thái live + người dùng. */
export default function TopBar() {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="logo">B</div>
        <div>
          <h1>{topbar.brandTitle}</h1>
          <small>{topbar.brandSub}</small>
        </div>
      </div>
      <div className="topbar-right">
        {topbar.pills.map((p) => (
          <span key={p.text} className="pill" style={p.kind === "rag" ? { color: "#86efac" } : undefined}>
            {p.kind === "live" && <span className="dot" />}
            {p.text}
          </span>
        ))}
        <div className="avatar">{topbar.avatar}</div>
      </div>
    </header>
  );
}
