/* Bảng nhắc "ĐƠN VỊ CÒN THIẾU GÌ" — hiện trên MỌI màn của tài khoản đơn vị thành viên.
   Đặt ở khung layout chứ không ở từng trang: đơn vị vào bất kỳ màn nào cũng thấy ngay mình còn
   nợ số liệu ngày nào, thay vì phải tự đi soi từng biểu. Chỉ nhắc phần CÒN SỬA ĐƯỢC (server lọc
   theo cửa sổ nhập liệu) — nhắc ngày đã khoá thì người dùng bỏ qua cả bảng. */

import { CheckCircleFilled, DownOutlined, UpOutlined, WarningFilled } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { dmy } from "../../../lib/date";
import { DATA_SAVED_EVENT } from "../../../lib/http";
import { type MemberChecklist, type UnitChecklist, fetchMyChecklist } from "../../../lib/member-client";

const COLLAPSE_KEY = "vrg_checklist_collapsed";
const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Nhãn ngày ngắn gọn — "hôm nay" đọc nhanh hơn ngày tháng khi đang nhắc việc. */
const dayLabel = (d: string, today: string) => (d === today ? "hôm nay" : dmy(d));

function DayChips({ days, today, onPick }: { days: string[]; today: string; onPick: (d: string) => void }) {
  return (
    <>
      {days.map((d) => (
        <button key={d} className="chip warn" onClick={() => onPick(d)}
          style={{ border: 0, cursor: "pointer", marginRight: 6 }}
          title="Bấm để mở phiếu nhập của ngày này">
          {dayLabel(d, today)}
        </button>
      ))}
    </>
  );
}

function UnitRow({ u, today, go }: {
  u: UnitChecklist; today: string; go: (path: string, day?: string, company?: string) => void;
}) {
  const items: JSX.Element[] = [];
  if (u.purchase_missing.length) {
    items.push(
      <div key="p" style={{ marginBottom: 4 }}>
        <b>Thu mua</b> — chưa nhập {u.purchase_missing.length} ngày:{" "}
        <DayChips days={u.purchase_missing} today={today}
          onPick={(d) => go("/bao-cao-thu-mua", d, u.company)} />
      </div>,
    );
  }
  if (u.stock_missing.length) {
    items.push(
      <div key="s" style={{ marginBottom: 4 }}>
        <b>Tồn kho</b> — chưa nhập {u.stock_missing.length} ngày:{" "}
        <DayChips days={u.stock_missing} today={today}
          onPick={(d) => go("/bao-cao-ton-kho", d, u.company)} />
      </div>,
    );
  }
  if (u.year_plan_missing) {
    items.push(
      <div key="y" style={{ marginBottom: 4 }}>
        <b>Kế hoạch năm {u.year}</b> — chưa khai.{" "}
        <button className="chip info" style={{ border: 0, cursor: "pointer" }}
          onClick={() => go("/ke-hoach-nam")}>Khai ngay</button>
      </div>,
    );
  }
  if (u.pending_batches.length) {
    items.push(
      <div key="b" style={{ marginBottom: 4 }}>
        <b>{u.pending_batches.length} đợt giao</b> chưa điền ngày giao (
        {u.pending_batches.slice(0, 3).map((b) => `${b.contract_code} · ${b.code} — ${t3(b.qty)} t, ${b.days} ngày`).join(" · ")}
        {u.pending_batches.length > 3 ? " …" : ""}) — sản lượng này <b>chưa vào tiêu thụ</b>.{" "}
        <button className="chip info" style={{ border: 0, cursor: "pointer" }}
          onClick={() => go("/hop-dong")}>Mở hợp đồng</button>
      </div>,
    );
  }
  if (!items.length) return null;
  return (
    <div style={{ padding: "8px 16px", borderTop: "1px solid var(--line)", fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{u.company}</div>
      {items}
    </div>
  );
}

/** Hộp nhắc việc của đơn vị — tự tải lại mỗi lần đổi màn (nhập xong quay ra là thấy trừ đi ngay). */
export default function MemberChecklistBanner() {
  const nav = useNavigate();
  const { pathname } = useLocation();
  const [data, setData] = useState<MemberChecklist | null>(null);
  const [open, setOpen] = useState(sessionStorage.getItem(COLLAPSE_KEY) !== "1");

  const load = useCallback(() => {
    fetchMyChecklist().then(setData).catch(() => setData(null));
  }, []);
  useEffect(() => { load(); }, [load, pathname]);

  // Nhập xong là bảng nhắc phải trừ ngay việc đó — đứng nguyên tại trang mà vẫn thấy "còn thiếu"
  // thì người dùng tưởng lưu hụt và nhập lại lần nữa.
  useEffect(() => {
    window.addEventListener(DATA_SAVED_EVENT, load);
    return () => window.removeEventListener(DATA_SAVED_EVENT, load);
  }, [load]);

  const toggle = () => setOpen((v) => {
    sessionStorage.setItem(COLLAPSE_KEY, v ? "1" : "0");
    return !v;
  });

  // Mở phiếu nhập ĐÚNG ngày còn thiếu: trang nhập đọc 2 tham số này rồi bật form ngay.
  const go = (path: string, day?: string, company?: string) => {
    const q = day ? `?ngay=${day}&don-vi=${encodeURIComponent(company ?? "")}` : "";
    nav(`${path}${q}`);
  };

  if (!data) return null;

  if (!data.total_missing) {
    return (
      <div className="dsn dsn-auto" style={{ margin: "12px 24px 0" }}>
        <div className="dsn-head" style={{ cursor: "default" }}>
          <span className="dsn-badge"><CheckCircleFilled /> Đã nhập đủ</span>
          <span className="dsn-tagline">
            Không thiếu số liệu nào trong {data.window_days} ngày còn sửa được.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="dsn dsn-manual" style={{ margin: "12px 24px 0" }}>
      <button className="dsn-head" onClick={toggle}>
        <span className="dsn-badge"><WarningFilled /> Còn thiếu {data.total_missing} việc</span>
        <span className="dsn-tagline">
          Đơn vị chưa nhập đủ số liệu trong {data.window_days} ngày gần nhất — quá hạn này sẽ
          không sửa được nữa.
        </span>
        <span className="dsn-toggle">{open ? <>Thu gọn <UpOutlined /></> : <>Xem chi tiết <DownOutlined /></>}</span>
      </button>
      {open && data.units.map((u) => <UnitRow key={u.company} u={u} today={data.today} go={go} />)}
    </div>
  );
}
