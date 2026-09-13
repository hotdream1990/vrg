/* Các khối gập hỗ trợ viết báo cáo, đặt ngay dưới thanh đầu:
   Nguồn tham khảo · Tài liệu đính kèm · Chỉ số tài chính & tỷ giá · Tin vietnambiz trong kỳ. */

import {
  FundOutlined, LinkOutlined, PaperClipOutlined, ReadOutlined, SettingOutlined,
} from "@ant-design/icons";
import { useState } from "react";

import type { WeeklyReport } from "../../../../lib/weekly-report-client";
import type { WeeklySource, WeeklySourceMeta } from "../../../../lib/weekly-sources-client";
import WeeklyAttachmentsCard from "./WeeklyAttachmentsCard";
import WeeklyCollapsible from "./WeeklyCollapsible";
import WeeklyIndicatorsCard from "./WeeklyIndicatorsCard";
import WeeklyNewsCard from "./WeeklyNewsCard";
import WeeklySourcesCard from "./WeeklySourcesCard";
import WeeklySourcesManager from "./WeeklySourcesManager";

type Props = {
  report: WeeklyReport;
  canEdit: boolean;
  sources: WeeklySource[];
  meta: WeeklySourceMeta;
  sourcesError: string;
  reloadSources: () => Promise<void>;
};

export default function WeeklyInputsPanel({ report: r, canEdit, sources, meta, sourcesError, reloadSources }: Props) {
  const [managing, setManaging] = useState(false);
  // Kỳ đã được máy chủ xác nhận (sau khi lưu) — chỉ số/tin nạp lại theo kỳ này, không theo lúc đang gõ.
  const span = r.span_weeks ?? 1;

  return (
    <div className="wk-inputs">
      <WeeklyCollapsible storageKey="sources" defaultOpen={false} icon={<LinkOutlined />}
        title={`Nguồn tham khảo (${sources.filter((s) => s.enabled).length})`}
        extra={canEdit ? (
          <button className="btn btn-sm" onClick={() => setManaging(true)}><SettingOutlined /> Quản lý nguồn</button>
        ) : undefined}>
        <WeeklySourcesCard sources={sources} meta={meta} error={sourcesError} />
      </WeeklyCollapsible>

      <WeeklyCollapsible storageKey="attachments" icon={<PaperClipOutlined />} title="Tài liệu đính kèm">
        <WeeklyAttachmentsCard weekKey={r.week_key} canEdit={canEdit} />
      </WeeklyCollapsible>

      <WeeklyCollapsible storageKey="indicators" icon={<FundOutlined />} title="Chỉ số tài chính & tỷ giá trong kỳ">
        <WeeklyIndicatorsCard weekKey={r.week_key} span={span} weeks={r.weeks ?? []} fxRows={r.fx_rows ?? []} />
      </WeeklyCollapsible>

      <WeeklyCollapsible storageKey="news"icon={<ReadOutlined />} title="Tin vietnambiz trong kỳ">
        <WeeklyNewsCard weekKey={r.week_key} span={span} />
      </WeeklyCollapsible>

      {managing && (
        <WeeklySourcesManager sources={sources} meta={meta} onClose={() => setManaging(false)} onChanged={reloadSources} />
      )}
    </div>
  );
}
