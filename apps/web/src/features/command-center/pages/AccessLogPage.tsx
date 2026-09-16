import { FileExcelOutlined, HistoryOutlined, ReloadOutlined } from "@ant-design/icons";
import { Select, Tabs } from "antd";
import { useEffect, useState } from "react";

import {
  type AccessFilters,
  type AccessMeta,
  downloadAccessXlsx,
  fetchAccessMeta,
} from "../../../lib/access-log-client";
import { daysAgoISO, todayISO } from "../../../lib/date";
import AccessDetailTable from "../sections/AccessDetailTable";
import AccessSummaryTable from "../sections/AccessSummaryTable";
import DateInput from "../sections/DateInput";
import "../../bulletin/bulletin.css";

const EMPTY_META: AccessMeta = { events: [], roles: [], users: [], units: [] };

/** Quản trị → Lịch sử truy cập: ai đăng nhập lúc nào · vào những trang nào.
 *  Khác "Nhật ký hoạt động" (chỉ ghi THAY ĐỔI số liệu) — màn này trả lời câu "có dùng hay không". */
export default function AccessLogPage() {
  const [meta, setMeta] = useState<AccessMeta>(EMPTY_META);
  const [filters, setFilters] = useState<AccessFilters>({
    date_from: daysAgoISO(30), date_to: todayISO(),
  });
  const [tab, setTab] = useState("summary");
  const [page, setPage] = useState(1);
  const [exporting, setExporting] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => { fetchAccessMeta().then(setMeta).catch((e) => setErr(e.message)); }, []);

  /** Đổi bộ lọc → luôn quay về trang 1 (kết quả cũ ở trang N không còn ý nghĩa). */
  const setFilter = (patch: Partial<AccessFilters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };
  const reload = () => setFilters((f) => ({ ...f }));   // đổi tham chiếu → bảng đang mở tự tải lại

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><HistoryOutlined style={{ marginRight: 8 }} />Lịch sử truy cập</h2>
          <p>Theo dõi <b>ai đăng nhập lúc nào · vào những trang nào</b> — để biết tài khoản đã cấp
            có thực sự được dùng hay không.</p>
          <p style={{ marginTop: 4 }}>Chỉ ghi <b>trang đã mở</b>, không ghi nội dung đang xem. Lịch
            sử tính từ ngày tính năng được bật, lưu 400 ngày.</p>
          <p style={{ marginTop: 4 }}>Bảng <b>Theo tài khoản</b> liệt kê cả tài khoản <b>chưa truy
            cập lần nào</b>, và không tính những lượt quản trị “đăng nhập hộ” — xem đủ ở tab
            <b> Chi tiết</b>.</p>
        </div>
      </div>
      {err && <div className="blt-error">{err}</div>}

      <div className="card" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label className="blt-date-label">Từ ngày:
          <DateInput value={filters.date_from ?? ""} onChange={(v) => setFilter({ date_from: v })}
            style={{ marginLeft: 8 }} />
        </label>
        <label className="blt-date-label">Đến ngày:
          <DateInput value={filters.date_to ?? ""} onChange={(v) => setFilter({ date_to: v })}
            style={{ marginLeft: 8 }} />
        </label>
        <Select allowClear showSearch placeholder="Tài khoản" style={{ minWidth: 200 }}
          value={filters.username} onChange={(v) => setFilter({ username: v })}
          options={meta.users.map((u) => ({ value: u, label: u }))} />
        <Select allowClear placeholder="Vai trò" style={{ minWidth: 220 }}
          value={filters.role} onChange={(v) => setFilter({ role: v })}
          options={meta.roles.map((r) => ({ value: r.key, label: r.label }))} />
        <Select allowClear showSearch placeholder="Đơn vị" style={{ minWidth: 220 }}
          value={filters.company} onChange={(v) => setFilter({ company: v })}
          options={meta.units.map((u) => ({ value: u, label: u }))}
          filterOption={(i, o) => String(o?.label ?? "").toLowerCase().includes(i.toLowerCase())} />
        {tab === "detail" && (
          <Select allowClear placeholder="Sự kiện" style={{ minWidth: 170 }}
            value={filters.event} onChange={(v) => setFilter({ event: v })}
            options={meta.events.map((e) => ({ value: e.key, label: e.label }))} />
        )}
        <input className="blt-date-input" placeholder="Tìm: tài khoản · trang · IP…"
          style={{ minWidth: 220 }} defaultValue={filters.q ?? ""}
          onKeyDown={(e) => { if (e.key === "Enter") setFilter({ q: e.currentTarget.value.trim() }); }}
          onBlur={(e) => setFilter({ q: e.currentTarget.value.trim() })} />
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button className="btn" onClick={reload}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <ReloadOutlined /> Tải lại
          </button>
          <button className="btn btn-primary" disabled={exporting}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            onClick={() => {
              setExporting(true); setErr("");
              downloadAccessXlsx(filters)
                .catch((e) => setErr(e instanceof Error ? e.message : "Lỗi xuất Excel"))
                .finally(() => setExporting(false));
            }}>
            {exporting ? <span className="spinner" /> : <FileExcelOutlined />} Xuất Excel
          </button>
        </div>
      </div>

      <div className="card">
        {/* Chỉ dựng bảng của tab ĐANG mở: AntD giữ nguyên pane đã mở trong DOM, để mặc định thì
            mỗi lần đổi bộ lọc cả hai bảng cùng gọi API dù chỉ một cái đang hiện. */}
        <Tabs activeKey={tab} onChange={setTab} items={[
          {
            key: "summary", label: "Theo tài khoản",
            children: tab === "summary"
              ? <AccessSummaryTable filters={filters} onError={setErr} /> : null,
          },
          {
            key: "detail", label: "Chi tiết lượt truy cập",
            children: tab === "detail"
              ? <AccessDetailTable filters={filters} page={page} onPage={setPage} onError={setErr} />
              : null,
          },
        ]} />
      </div>
    </div>
  );
}
