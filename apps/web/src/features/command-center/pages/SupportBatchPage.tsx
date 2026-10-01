import { ArrowLeftOutlined, NotificationOutlined } from "@ant-design/icons";
import { Empty, Pagination, Spin, Tag } from "antd";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { type ThreadRow, fetchThreads } from "../../../lib/support-client";
import { AudienceTags } from "../sections/SupportAudience";
import { stampVN } from "../sections/support-format";
import "../../bulletin/bulletin.css";
import "../support.css";

const PAGE_SIZE = 20;

/** Một ĐỢT GỬI của Tập đoàn: liệt kê từng đơn vị nhận để vào xem/trả lời riêng từng đơn vị.
 *
 *  Chỉ phía Tập đoàn tới được màn này (đơn vị không có `batch_id` để mở, và server cũng chỉ trả
 *  luồng trong phạm vi của tài khoản). */
export default function SupportBatchPage() {
  const { batchId = "" } = useParams();
  const nav = useNavigate();
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{ rows: ThreadRow[]; total: number }>({ rows: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setLoading(true); setErr("");
    fetchThreads({ batch_id: batchId, page, page_size: PAGE_SIZE })
      .then((r) => setData({ rows: r.rows, total: r.total }))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [batchId, page]);
  useEffect(() => { load(); }, [load]);

  const first = data.rows[0];
  const subject = first?.subject ?? "Đợt gửi thông báo";

  return (
    <div className="main">
      <div className="page-title">
        <div>
          <h2><NotificationOutlined style={{ marginRight: 8 }} />{subject}</h2>
          <p>Danh sách đơn vị đã nhận thông báo này — mỗi đơn vị một luồng trao đổi riêng.</p>
          {first && <p>Gửi tới: <AudienceTags audience={first.audience} /></p>}
        </div>
        <div className="actions">
          <button className="btn" onClick={() => nav("/ho-tro")}><ArrowLeftOutlined /> Hộp thư</button>
        </div>
      </div>

      {err && <div className="blt-error">{err}</div>}

      <div className="card">
        {loading ? <div className="blt-loading"><Spin /> Đang tải…</div>
          : !data.rows.length ? <Empty description="Không có đơn vị nào trong đợt gửi này." />
          : (
            <div className="sp-list">
              {data.rows.map((t) => (
                <button key={t.id} type="button" className={`sp-item${t.unread ? " unread" : ""}`}
                  onClick={() => nav(`/ho-tro/${t.id}`)}>
                  <div className="sp-item-main">
                    <div className="sp-item-title">{t.company}</div>
                    <div className="sp-item-meta">
                      <span>{t.message_count} tin</span>
                      {t.status === "closed" && <Tag>Đã đóng</Tag>}
                      {t.last_side === "unit" && <Tag color="gold">Đơn vị đã phản hồi</Tag>}
                    </div>
                    {t.last_body && <div className="sp-item-excerpt">{t.last_body}</div>}
                  </div>
                  <div className="sp-item-side">{stampVN(t.last_at)}</div>
                </button>
              ))}
            </div>
          )}
      </div>

      {data.total > PAGE_SIZE && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
          <Pagination current={page} total={data.total} pageSize={PAGE_SIZE} showSizeChanger={false}
            onChange={setPage} showTotal={(t) => `${t} đơn vị`} />
        </div>
      )}
    </div>
  );
}
