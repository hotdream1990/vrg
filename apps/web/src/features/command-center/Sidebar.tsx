import { useLocation, useNavigate } from "react-router-dom";

import { type NavItem, nav } from "../../data/sample-data";

/** Điều hướng trái theo route. Mục có hash = cuộn trong trang Dashboard (mockup). */
export default function Sidebar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const go = (it: NavItem) => {
    navigate(it.hash ? { pathname: it.to, hash: it.hash } : { pathname: it.to });
    // Đã ở đúng trang + có hash → cuộn ngay (hash không đổi sẽ không trigger effect).
    if (it.hash && pathname === it.to) {
      document.querySelector(it.hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  // Chỉ các route đã implement mới sáng active; mục hash là phím tắt cuộn, không active.
  const isActive = (it: NavItem) => pathname === it.to && !it.hash;

  return (
    <aside className="sidebar">
      {nav.map((group) => (
        <div key={group.section}>
          <div className="nav-section">{group.section}</div>
          {group.items.map((it) => (
            <div
              key={it.label}
              className={`nav-item${isActive(it) ? " active" : ""}`}
              onClick={() => go(it)}
            >
              <span className="nav-icon">{it.icon}</span> {it.label}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
