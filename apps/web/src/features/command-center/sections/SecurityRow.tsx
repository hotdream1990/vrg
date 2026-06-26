import { security } from "../../../data/sample-data-panels";

/** Thành trì bảo mật (minh hoạ). */
export default function SecurityRow() {
  return (
    <div className="card">
      <div className="card-head"><h3 className="title-demo">Thành trì Bảo mật</h3><span className="chip demo">Minh hoạ</span></div>
      <div className="sec-grid">
        {security.map((s) => (
          <div className="sec-card" key={s.h4}>
            <div className="ico">{s.ico}</div>
            <h4>{s.h4}</h4>
            <p>{s.p}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
