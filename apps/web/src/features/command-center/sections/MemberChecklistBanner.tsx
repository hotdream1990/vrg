/* Bảng nhắc "ĐƠN VỊ CÒN THIẾU GÌ" — hiện trên MỌI màn của tài khoản đơn vị thành viên.
   Đặt ở khung layout chứ không ở từng trang: đơn vị vào bất kỳ màn nào cũng thấy ngay mình còn
   nợ số liệu ngày nào, thay vì phải tự đi soi từng biểu. Chỉ nhắc phần CÒN SỬA ĐƯỢC (server lọc
   theo cửa sổ nhập liệu) — nhắc ngày đã khoá thì người dùng bỏ qua cả bảng. Riêng nhóm THIẾU TỶ
   GIÁ và nhóm Ô CẦN KIỂM TRA rà cả năm và hiện cả bản ghi đã khoá (chữ xám): đó là doanh thu bị
   hụt / số nhầm đơn vị tính, đơn vị phải biết để nhờ Ban TTKD sửa hộ.

   Nhóm "ô cần kiểm tra" là cảnh báo vốn CHỈ chạy trong form lúc đang nhập — lưu xong đóng form là
   không ai thấy nữa. Server rà lại số đã lưu (`member_data_check`) rồi đưa lên đây. */

import { CheckCircleFilled, DownOutlined, UpOutlined, WarningFilled } from "@ant-design/icons";
import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { dmy } from "../../../lib/date";
import { DATA_SAVED_EVENT } from "../../../lib/http";
import { type DataCheck, type MemberChecklist, type MissingFxDelivery, type UnitChecklist, fetchMyChecklist } from "../../../lib/member-client";

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

/** Một lần giao thiếu tỷ giá. Cam = còn trong cửa sổ sửa, bấm vào mở màn hợp đồng; xám = đã khoá. */
function FxChip({ d, onPick }: { d: MissingFxDelivery; onPick: () => void }) {
  const label = `${d.contract_code}${d.code && d.code !== d.contract_code ? ` · ${d.code}` : ""} — ${t3(d.qty)} t ${d.ccy}, giao ${dmy(d.delivered_at)}`;
  if (!d.editable) {
    return (
      <span className="chip" style={{ background: "var(--panel-2, #eef1ef)", color: "var(--muted)", marginRight: 6 }}
        title="Quá hạn sửa — báo Ban TTKD điền tỷ giá hộ">
        {label}
      </span>
    );
  }
  return (
    <button className="chip warn" onClick={onPick}
      style={{ border: 0, cursor: "pointer", marginRight: 6 }}
      title="Bấm để mở màn Hợp đồng & đợt giao và điền tỷ giá">
      {label}
    </button>
  );
}

/** Màn để sửa ô đang bị soát — cùng đường dẫn với các nhóm nhắc khác của bảng việc. */
const CHECK_PATH: Record<DataCheck["kind"], string> = {
  purchase: "/bao-cao-thu-mua",
  stock: "/bao-cao-ton-kho",
  contract: "/hop-dong",
};

/** Một ô cần soát lại: chỉ đường tới ô (ngày · bảng · dòng · cột) + lý do, y hệt câu trong form.
 *  Hiện CẢ LÝ DO chứ không chỉ tên ô: "kiểm tra lại đơn vị tính" mới là phần khiến người ta mở ra
 *  xem, còn tên ô đứng một mình thì không ai biết nó sai chỗ nào. */
function CheckRow({ c, onPick }: { c: DataCheck; onPick: () => void }) {
  const label = `${dmy(c.as_of)} · ${c.where}`;
  return (
    <li style={{ marginBottom: 2 }}>
      {c.editable ? (
        <button className="chip warn" onClick={onPick}
          style={{ border: 0, cursor: "pointer", marginRight: 6 }}
          title="Bấm để mở đúng phiếu và sửa ô này">
          {label}
        </button>
      ) : (
        <span className="chip" style={{ background: "var(--panel-2, #eef1ef)", color: "var(--muted)", marginRight: 6 }}
          title="Quá hạn sửa — báo Ban TTKD sửa hộ">
          {label}
        </span>
      )}
      <span style={{ color: "var(--muted)" }}>{c.message}</span>
    </li>
  );
}

function UnitRow({ u, today, editableFrom, go }: {
  u: UnitChecklist; today: string; editableFrom: string;
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
  if (u.completed_no_delivery?.length) {
    // Không kết luận là sai (hợp đồng huỷ cũng rơi vào đây) — chỉ nói rõ hệ quả để đơn vị tự soát.
    const tons = u.completed_no_delivery.reduce((s2, c) => s2 + (c.qty || 0), 0);
    items.push(
      <div key="cnd" style={{ marginBottom: 4 }}>
        <b>{u.completed_no_delivery.length} hợp đồng đã chốt hoàn thành nhưng chưa ghi lần giao nào</b>{" "}
        ({u.completed_no_delivery.slice(0, 3).map((c) => `${c.code} — ${t3(c.qty)} t`).join(" · ")}
        {u.completed_no_delivery.length > 3 ? " …" : ""}) — tổng <b>{t3(tons)} tấn</b> này{" "}
        <b>không vào tiêu thụ</b>. Hàng đã giao thật thì mở hợp đồng, bấm{" "}
        <b>Mở lại hợp đồng</b>, điền <b>Ngày giao</b> + <b>Hình thức tiêu thụ</b> rồi chốt lại;
        hợp đồng huỷ thì bỏ qua.{" "}
        <button className="chip info" style={{ border: 0, cursor: "pointer" }}
          onClick={() => go("/hop-dong")}>Mở hợp đồng</button>
      </div>,
    );
  }
  if (u.missing_fx.length) {
    // Tiền, không phải số liệu nhập thiếu → nói rõ hệ quả (doanh thu chưa tính) và rà cả năm.
    const fixable = u.missing_fx.filter((d) => d.editable).length;
    items.push(
      <div key="fx" style={{ marginBottom: 4 }}>
        <b>{u.missing_fx.length} lần giao bán ngoại tệ thiếu tỷ giá</b> (rà từ đầu năm {u.year}) —
        doanh thu & giá bán bình quân <b>chưa tính phần này</b>:{" "}
        {u.missing_fx.slice(0, 3).map((d) => (
          <FxChip key={d.id} d={d} onPick={() => go("/hop-dong")} />
        ))}
        {u.missing_fx.length > 3 ? <span style={{ color: "var(--muted)" }}>…</span> : null}
        {fixable < u.missing_fx.length ? (
          <div style={{ color: "var(--muted)", marginTop: 2 }}>
            {u.missing_fx.length - fixable} lần giao đã quá hạn sửa (chữ xám) — báo Ban TTKD điền hộ.
          </div>
        ) : null}
      </div>,
    );
  }
  if (u.data_checks.length) {
    // Số ĐÃ NHẬP nhưng đáng ngờ — khác hẳn các nhóm trên (số còn thiếu), nên nói rõ hệ quả: sai
    // đơn vị tính là báo cáo tổng hợp sai theo, mà nhìn con số tổng thì không thấy sai từ đâu.
    const fixable = u.data_checks.filter((c) => c.editable).length;
    items.push(
      <div key="chk" style={{ marginBottom: 4 }}>
        <b>{u.data_checks.length} ô số liệu cần kiểm tra lại</b> (rà từ đầu năm {u.year}) — số đã
        nhập nhiều khả năng <b>nhầm đơn vị tính</b>, để nguyên thì báo cáo tổng hợp sai theo:
        <ul style={{ margin: "2px 0 0", paddingLeft: 18 }}>
          {u.data_checks.slice(0, 5).map((c, i) => (
            <CheckRow key={`${c.as_of}-${c.where}-${i}`} c={c}
              onPick={() => go(CHECK_PATH[c.kind], c.kind === "contract" ? undefined : c.as_of, u.company)} />
          ))}
        </ul>
        {u.data_checks.length > 5 ? (
          <div style={{ color: "var(--muted)" }}>…và {u.data_checks.length - 5} ô nữa.</div>
        ) : null}
        {fixable < u.data_checks.length ? (
          <div style={{ color: "var(--muted)", marginTop: 2 }}>
            {u.data_checks.length - fixable} ô đã quá hạn sửa (chữ xám) — báo Ban TTKD sửa hộ.
          </div>
        ) : null}
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
          Đơn vị chưa nhập đủ số liệu trong {data.alert_days} ngày gần nhất, hoặc có ô đã nhập
          cần kiểm tra lại (phần <b>thiếu tỷ giá</b> và <b>ô cần kiểm tra</b> rà cả năm). Ô{" "}
          <b>màu cam</b> bấm vào là sửa được ngay; ô <b>xám</b> đã quá hạn sửa — báo Ban TTKD
          nhập hộ.
        </span>
        <span className="dsn-toggle">{open ? <>Thu gọn <UpOutlined /></> : <>Xem chi tiết <DownOutlined /></>}</span>
      </button>
      {open && data.units.map((u) => (
        <UnitRow key={u.company} u={u} today={data.today} editableFrom={data.editable_from} go={go} />
      ))}
    </div>
  );
}
