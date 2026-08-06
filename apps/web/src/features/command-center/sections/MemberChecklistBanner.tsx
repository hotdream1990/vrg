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
import { useAuth } from "../../auth/AuthContext";

const COLLAPSE_KEY = "vrg_checklist_collapsed";
const t3 = (n: number) => n.toLocaleString("vi-VN", { maximumFractionDigits: 3 });

/** Nhãn ngày ngắn gọn — "hôm nay" đọc nhanh hơn ngày tháng khi đang nhắc việc. */
const dayLabel = (d: string, today: string) => (d === today ? "hôm nay" : dmy(d));

/** Ngày cũ hơn `editableFrom` thì đơn vị KHÔNG tự sửa được nữa — vẫn phải hiện (để biết mình còn
 *  nợ) nhưng để dạng chữ xám, không bấm được: mời bấm rồi chặn ở form là hứa hão. */
function DayChips({ days, today, editableFrom, onPick }: {
  days: string[]; today: string; editableFrom: string; onPick: (d: string) => void;
}) {
  return (
    <>
      {days.map((d) => (d >= editableFrom ? (
        <button key={d} className="chip warn" onClick={() => onPick(d)}
          style={{ border: 0, cursor: "pointer", marginRight: 6 }}
          title="Bấm để mở phiếu nhập của ngày này">
          {dayLabel(d, today)}
        </button>
      ) : (
        <span key={d} className="chip" style={{ background: "var(--panel-2, #eef1ef)", color: "var(--muted)", marginRight: 6 }}
          title="Quá hạn sửa — báo Ban TTKD nhập hộ">
          {dayLabel(d, today)}
        </span>
      )))}
    </>
  );
}

function UnitRow({ u, today, editableFrom, canOpenPlan, go }: {
  u: UnitChecklist; today: string; editableFrom: string; canOpenPlan: boolean;
  go: (path: string, day?: string, company?: string) => void;
}) {
  const items: JSX.Element[] = [];
  if (u.purchase_missing.length) {
    items.push(
      <div key="p" style={{ marginBottom: 4 }}>
        <b>Thu mua</b> — chưa nhập {u.purchase_missing.length} ngày:{" "}
        <DayChips days={u.purchase_missing} today={today} editableFrom={editableFrom}
          onPick={(d) => go("/bao-cao-thu-mua", d, u.company)} />
      </div>,
    );
  }
  if (u.stock_missing.length) {
    items.push(
      <div key="s" style={{ marginBottom: 4 }}>
        <b>Tồn kho</b> — chưa nhập {u.stock_missing.length} ngày:{" "}
        <DayChips days={u.stock_missing} today={today} editableFrom={editableFrom}
          onPick={(d) => go("/bao-cao-ton-kho", d, u.company)} />
      </div>,
    );
  }
  if (u.year_plan_missing) {
    items.push(
      <div key="y" style={{ marginBottom: 4 }}>
        <b>Kế hoạch năm {u.year}</b> — chưa khai.{" "}
        {/* Màn Kế hoạch năm chỉ mở cho đơn vị ĐÃ có số kế hoạch (chính con số đó là công tắc bật
            màn Thu mua) → đơn vị chưa khai lần nào bấm vào sẽ bị đá về. Nói thẳng thay vì mời bấm. */}
        {canOpenPlan ? (
          <button className="chip info" style={{ border: 0, cursor: "pointer" }}
            onClick={() => go("/ke-hoach-nam")}>Khai ngay</button>
        ) : (
          <span style={{ color: "var(--muted)" }}>Đơn vị chưa từng khai nên chưa mở màn này —
            báo Ban TTKD khai hộ.</span>
        )}
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
  const { user } = useAuth();
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

  // Admin đặt số ngày rà = 0 → tắt hẳn cảnh báo, không chiếm chỗ trên đầu mọi màn.
  if (!data || !data.enabled) return null;

  if (!data.total_missing) {
    return (
      <div className="dsn dsn-auto" style={{ margin: "12px 24px 0" }}>
        <div className="dsn-head" style={{ cursor: "default" }}>
          <span className="dsn-badge"><CheckCircleFilled /> Đã nhập đủ</span>
          <span className="dsn-tagline">
            Không thiếu số liệu nào trong {data.alert_days} ngày gần nhất.
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
          Đơn vị chưa nhập đủ số liệu trong {data.alert_days} ngày gần nhất. Ngày để{" "}
          <b>màu cam</b> bấm vào là nhập được ngay; ngày <b>xám</b> đã quá hạn sửa — báo Ban TTKD
          nhập hộ.
        </span>
        <span className="dsn-toggle">{open ? <>Thu gọn <UpOutlined /></> : <>Xem chi tiết <DownOutlined /></>}</span>
      </button>
      {open && data.units.map((u) => (
        <UnitRow key={u.company} u={u} today={data.today} editableFrom={data.editable_from}
          canOpenPlan={user?.member_has_purchase_plan ?? false} go={go} />
      ))}
    </div>
  );
}
