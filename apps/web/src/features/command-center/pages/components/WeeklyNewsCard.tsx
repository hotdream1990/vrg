/* Tin vietnambiz trong kỳ ("Giá cao su hôm nay …") — ngày đăng · tiêu đề (mở tab mới).
   Lỗi mạng chỉ báo trong card, không chặn màn báo cáo. */

import { LinkOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { type PeriodArticle, getWeeklyNews } from "../../../../lib/weekly-report-inputs-client";
import { safeHref, viDate } from "./WeeklyFormat";

type Props = { weekKey: string; span: number };

export default function WeeklyNewsCard({ weekKey, span }: Props) {
  const [items, setItems] = useState<PeriodArticle[] | null>(null);
  const [err, setErr] = useState("");

  // `span` trong deps: máy chủ đọc số tuần gộp từ bản đã lưu → đổi kỳ xong (đã lưu) thì nạp lại.
  useEffect(() => {
    let alive = true;
    setItems(null); setErr("");
    getWeeklyNews(weekKey)
      .then((r) => { if (alive) setItems(r.articles ?? []); })
      .catch((e) => { if (alive) { setItems([]); setErr(e instanceof Error ? e.message : "Lỗi"); } });
    return () => { alive = false; };
  }, [weekKey, span]);

  if (items === null) return <div className="wk-muted"><span className="spinner" /> Đang lấy tin trong kỳ…</div>;
  return (
    <div>
      {err && <div className="blt-error">Không lấy được tin vietnambiz: {err}</div>}
      {!err && items.length === 0 && <div className="scan-empty">Không có bài "Giá cao su hôm nay" trong kỳ.</div>}
      <ul className="wk-news">
        {[...items].sort((a, b) => (a.published ?? "").localeCompare(b.published ?? "")).map((a) => (
          <li key={a.url}>
            <span className="wk-news-date">{viDate(a.published)}</span>
            {safeHref(a.url)
              ? <a href={safeHref(a.url) ?? undefined} target="_blank" rel="noopener noreferrer">{a.title} <LinkOutlined /></a>
              : <span>{a.title}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
