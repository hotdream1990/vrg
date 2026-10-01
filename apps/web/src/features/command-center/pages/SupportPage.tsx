import { CustomerServiceOutlined, PlusOutlined, ReloadOutlined, ScheduleOutlined } from "@ant-design/icons";
import { Empty, Input, Pagination, Segmented, Select, Spin, Tag } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  type BatchRow, type SupportContext, type ThreadKind, type ThreadRow,
  fetchBatches, fetchSupportContext, fetchThreads,
} from "../../../lib/support-client";
import { AudienceTags } from "../sections/SupportAudience";
import SupportComposer from "../sections/SupportComposer";
import { KIND_COLOR, KIND_LABEL, stampVN } from "../sections/support-format";
import "../../bulletin/bulletin.css";
import "../support.css";

const PAGE_SIZE = 20;

/** Hộp thư của phía Tập đoàn: 2 khay riêng — đơn vị gửi lên và Tập đoàn đã gửi xuống. */
const HQ_BOXES = [
  { value: "request", label: "Đơn vị gửi lên" },
  { value: "sent", label: "Đã gửi đơn vị" },
] as const;
type HqBox = (typeof HQ_BOXES)[number]["value"];

const STATUS_OPTIONS = [
  { value: "", label: "Tất cả trạng thái" },
  { value: "open", label: "Đang mở" },
  { value: "closed", label: "Đã đóng" },
];

/** Hỗ trợ & Thông báo — hộp thư hai chiều Tập đoàn ↔ đơn vị thành viên (lãnh đạo · chuyên viên).
 *
 *  Một component cho cả hai phía: `context.side` (server quyết định) đổi khay hiển thị và nút soạn.
 *  Phía đơn vị không bao giờ nhận được luồng của đơn vị khác — lọc nằm ở server, không ở đây. */
export default function SupportPage() {
  const nav = useNavigate();
  const [ctx, setCtx] = useState<SupportContext | null>(null);
  const [box, setBox] = useState<HqBox>("request");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [company, setCompany] = useState("");
  const [page, setPage] = useState(1);
  const [threads, setThreads] = useState<{ rows: ThreadRow[]; total: number }>({ rows: [], total: 0 });
  const [batches, setBatches] = useState<{ rows: BatchRow[]; total: number }>({ rows: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [composing, setComposing] = useState(false);

  const isHq = ctx?.side === "hq";
  const sentBox = isHq && box === "sent";

  useEffect(() => {
    fetchSupportContext().then(setCtx).catch((e) => setErr(e.message));
  }, []);

  const load = useCallback(() => {
    if (!ctx) return;
    setLoading(true); setErr("");
    const done = () => setLoading(false);
    if (sentBox) {
      fetchBatches({ status, q, page }).then((r) => setBatches({ rows: r.rows, total: r.total }))
        .catch((e) => setErr(e.message)).finally(done);
      return;
    }
    fetchThreads({
      kind: (isHq ? "request" : "") as ThreadKind | "",
      status, q, company, page, page_size: PAGE_SIZE,
    }).then((r) => setThreads({ rows: r.rows, total: r.total }))
      .catch((e) => setErr(e.message)).finally(done);
  }, [ctx, isHq, sentBox, status, q, company, page]);
  useEffect(() => { load(); }, [load]);

  /** Đổi bộ lọc là quay về trang 1 — kết quả cũ ở trang N không còn ý nghĩa. */
  const filter = <T,>(setter: (v: T) => void) => (v: T) => { setter(v); setPage(1); };

  const composeLabel = isHq ? "Soạn thông báo" : "Gửi yêu cầu hỗ trợ";
  const subtitle = isHq
    ? "Hộp thư với các đơn vị thành viên (lãnh đạo đơn vị và chuyên viên nhập liệu). Thông báo gửi cho nhiều đơn vị được tách thành từng luồng riêng — các đơn vị không thấy nội dung và phản hồi của nhau."
    : "Trao đổi trực tiếp với Tập đoàn: gửi yêu cầu hỗ trợ, nhận thông báo và nhắc lịch. Chỉ đơn vị của bạn đọc được các trao đổi này.";

  const total = sentBox ? batches.total : threads.total;

  const listBody = useMemo(() => {
    if (loading) return <div className="blt-loading"><Spin /> Đang tải hộp thư…</div>;
    if (sentBox) {
      if (!batches.rows.length) return <Empty description="Chưa gửi thông báo nào." />;
      return (
        <div className="sp-list">
          {batches.rows.map((b) => (
            <button key={b.group_key} type="button"
              className={`sp-item${b.unread_count ? " unread" : ""}`}
              onClick={() => nav(b.batch_id ? `/ho-tro/dot/${b.batch_id}` : `/ho-tro/${b.sample_id}`)}>
              <div className="sp-item-main">
                <div className="sp-item-title">{b.subject}</div>
                <div className="sp-item-meta">
                  <Tag color={KIND_COLOR[b.kind]}>{KIND_LABEL[b.kind]}</Tag>
                  <span>{b.unit_count} đơn vị nhận</span>
                  <span><AudienceTags audience={b.audience} /></span>
                  {b.unread_count > 0 && <span>{b.unread_count} phản hồi chưa đọc</span>}
                  <span>Người gửi: {b.created_by === "system" ? "Hệ thống (tự động)" : b.created_by ?? "—"}</span>
                </div>
              </div>
              <div className="sp-item-side">{stampVN(b.last_at)}</div>
            </button>
          ))}
        </div>
      );
    }
    if (!threads.rows.length) {
      return <Empty description={isHq ? "Chưa có yêu cầu nào từ đơn vị." : "Chưa có tin nào."} />;
    }
    return (
      <div className="sp-list">
        {threads.rows.map((t) => (
          <button key={t.id} type="button" className={`sp-item${t.unread ? " unread" : ""}`}
            onClick={() => nav(`/ho-tro/${t.id}`)}>
            <div className="sp-item-main">
              <div className="sp-item-title">{t.subject}</div>
              <div className="sp-item-meta">
                <Tag color={KIND_COLOR[t.kind]}>
                  {KIND_LABEL[t.kind]}
                </Tag>
                {isHq && <span>{t.company}</span>}
                {t.status === "closed" && <Tag>Đã đóng</Tag>}
                <span>{t.message_count} tin</span>
              </div>
              {t.last_body && <div className="sp-item-excerpt">{t.last_body}</div>}
            </div>
            <div className="sp-item-side">{stampVN(t.last_at)}</div>
          </button>
        ))}
      </div>
    );
  }, [loading, sentBox, batches.rows, threads.rows, isHq, nav]);

  if (!ctx) {
    return (
      <div className="main">
        {err ? <div className="blt-error">{err}</div> : <div className="blt-loading"><Spin /> Đang tải…</div>}
      </div>
    );
  }

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><CustomerServiceOutlined style={{ marginRight: 8 }} />Hỗ trợ & Thông báo</h2>
          <p>{subtitle}</p>
        </div>
        <div className="actions">
          {isHq && (
            <button className="btn" onClick={() => nav("/ho-tro/nhac-lich")}>
              <ScheduleOutlined /> Nhắc lịch
            </button>
          )}
          <button className="btn" onClick={load}><ReloadOutlined /> Tải lại</button>
          {ctx.can_write && (
            <button className="btn btn-primary" onClick={() => setComposing(true)}>
              <PlusOutlined /> {composeLabel}
            </button>
          )}
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card sp-row">
        {isHq && (
          <Segmented value={box} options={[...HQ_BOXES]}
            onChange={(v) => filter<HqBox>(setBox)(v as HqBox)} />
        )}
        <Select style={{ minWidth: 170 }} value={status} options={STATUS_OPTIONS}
          onChange={filter(setStatus)} />
        {isHq && !sentBox && (
          <Select showSearch allowClear style={{ minWidth: 240 }} placeholder="Lọc theo đơn vị"
            value={company || undefined} onChange={(v) => filter(setCompany)(v ?? "")}
            options={ctx.units.map((u) => ({ value: u, label: u }))} />
        )}
        <Input.Search allowClear style={{ maxWidth: 320 }} placeholder="Tìm theo tiêu đề…"
          onSearch={filter(setQ)} />
      </div>

      <div className="card">{listBody}</div>

      {total > PAGE_SIZE && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <Pagination current={page} total={total} pageSize={PAGE_SIZE} showSizeChanger={false}
            onChange={setPage} showTotal={(t) => `${t} mục`} />
        </div>
      )}

      {composing && (
        <SupportComposer ctx={ctx} onClose={() => setComposing(false)}
          onSent={(threadId) => {
            setComposing(false);
            if (threadId) nav(`/ho-tro/${threadId}`); else { setPage(1); load(); }
          }} />
      )}
    </div>
  );
}
