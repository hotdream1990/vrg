/* Khối gập/mở của màn Báo cáo tuần — nhớ trạng thái theo từng khối trong localStorage
   (bọc try/catch: trình duyệt chặn bộ nhớ thì vẫn chạy, chỉ không nhớ). */

import { DownOutlined, RightOutlined } from "@ant-design/icons";
import { type ReactNode, useState } from "react";

const PREFIX = "vrg.weekly.collapse.";

function readOpen(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(PREFIX + key);
    return v === null ? fallback : v === "1";
  } catch {
    return fallback;
  }
}

function writeOpen(key: string, open: boolean) {
  try { localStorage.setItem(PREFIX + key, open ? "1" : "0"); } catch { /* bộ nhớ bị chặn */ }
}

type Props = {
  storageKey: string;
  title: ReactNode;
  icon?: ReactNode;
  /** Nút/nhãn phụ bên phải tiêu đề (không làm gập khi bấm). */
  extra?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
};

export default function WeeklyCollapsible({ storageKey, title, icon, extra, defaultOpen = true, children }: Props) {
  const [open, setOpen] = useState(() => readOpen(storageKey, defaultOpen));
  const toggle = () => setOpen((o) => { writeOpen(storageKey, !o); return !o; });
  return (
    <div className="card wk-collapse">
      <div className="wk-collapse-head">
        <button type="button" className="wk-collapse-toggle" onClick={toggle} aria-expanded={open}>
          {open ? <DownOutlined /> : <RightOutlined />}
          {icon}
          <span>{title}</span>
        </button>
        {extra && <div className="wk-collapse-extra">{extra}</div>}
      </div>
      {open && <div className="wk-collapse-body">{children}</div>}
    </div>
  );
}
