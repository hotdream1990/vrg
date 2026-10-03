/* Thanh bước Nháp → Dự thảo → Tờ trình → Áp dụng + nút chuyển bước. Tới: từng nấc. Trả về: thẳng bước
   bất kỳ phía trước kèm lý do (vd lãnh đạo không duyệt tờ trình → về Nháp sửa số). Lý do lần trả về gần
   nhất hiện ngay trên thanh bước; đủ lịch sử trong mục gập. Áp dụng có trong quy trình nhưng chưa làm. */

import { ArrowRightOutlined, RollbackOutlined } from "@ant-design/icons";
import { Alert, Button, Collapse, Steps, Tooltip } from "antd";
import { useState } from "react";

import { APPLY_READY, STAGES, STAGE_LABEL, type Stage, type StageMove } from "../../../../lib/floor-draft-flow-client";
import { stampVN } from "../../../../lib/date";
import ReturnStageModal from "./ReturnStageModal";

const DESC: Record<Stage, string> = {
  nhap: "Soạn, chỉnh số phương án",
  du_thao: "Chốt số · chép hình dự thảo",
  to_trinh: "Soạn nội dung · AI · xuất Word/PDF",
  ap_dung: "Ghi giá sàn chính thức — sắp có",
};
const NEXT: Partial<Record<Stage, string>> = { nhap: "Chốt dự thảo", du_thao: "Lập tờ trình", to_trinh: "Áp dụng" };
export const APPLY_HINT = "Bước Áp dụng chưa triển khai: sau khi Tổng Giám đốc duyệt, giá sàn chính thức vẫn nhập ở "
  + "màn Giá sàn Tập đoàn.";

const isBack = (m: StageMove) => STAGES.indexOf(m.to) < STAGES.indexOf(m.from);

type Props = {
  stage: Stage;
  history: StageMove[];
  canEdit: boolean;
  busy: boolean;
  onMove: (to: Stage, note?: string) => Promise<void>;
};

export default function FloorDraftSteps({ stage, history, canEdit, busy, onMove }: Props) {
  const [returning, setReturning] = useState(false);
  const i = STAGES.indexOf(stage);
  const next = i < STAGES.length - 1 ? STAGES[i + 1] : null;
  const nextBlocked = next === "ap_dung" && !APPLY_READY;
  const last = history[history.length - 1];
  const returned = last && isBack(last) && last.to === stage ? last : null;

  const doReturn = async (to: Stage, note: string) => {
    await onMove(to, note);
    setReturning(false);
  };

  return (
    <div className="card fd-steps">
      <Steps size="small" current={i} items={STAGES.map((s) => ({
        title: STAGE_LABEL[s], content: DESC[s],
        status: s === "ap_dung" && !APPLY_READY ? "wait" : undefined,
        disabled: true,
      }))} />
      {returned && (
        <Alert type="warning" showIcon
          title={`Đã trả về từ bước ${STAGE_LABEL[returned.from]} — ${returned.by ?? "—"} lúc ${stampVN(returned.at)}`}
          description={returned.note ? `Lý do: ${returned.note}` : "Không ghi lý do."} />
      )}
      {canEdit && (
        <div className="fd-steps-actions">
          {i > 0 && (
            <Button icon={<RollbackOutlined />} disabled={busy} onClick={() => setReturning(true)}>
              Trả về bước trước…
            </Button>
          )}
          {next && NEXT[stage] && (
            <Tooltip title={nextBlocked ? APPLY_HINT : undefined}>
              <Button type="primary" icon={<ArrowRightOutlined />} iconPlacement="end" loading={busy}
                disabled={nextBlocked} onClick={() => onMove(next)}>
                {NEXT[stage]}{nextBlocked ? " (chưa triển khai)" : ""}
              </Button>
            </Tooltip>
          )}
        </div>
      )}
      {history.length > 0 && (
        <Collapse size="small" ghost items={[{
          key: "h", label: `Lịch sử chuyển bước (${history.length})`,
          children: (
            <div style={{ display: "grid", gap: 4, fontSize: 12.5 }}>
              {[...history].reverse().map((m, k) => (
                <div key={`${m.at}-${k}`}>
                  <span style={{ color: "var(--muted)" }}>{stampVN(m.at)} · {m.by ?? "—"}:</span>{" "}
                  {isBack(m) ? "Trả về" : "Chuyển"} {STAGE_LABEL[m.from]} → <b>{STAGE_LABEL[m.to]}</b>
                  {m.note && <span> — {m.note}</span>}
                </div>
              ))}
            </div>
          ),
        }]} />
      )}
      <ReturnStageModal open={returning} stage={stage} busy={busy} onOk={doReturn} onCancel={() => setReturning(false)} />
    </div>
  );
}
