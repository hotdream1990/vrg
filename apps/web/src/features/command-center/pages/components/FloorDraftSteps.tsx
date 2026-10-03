/* Thanh bước Nháp → Dự thảo → Tờ trình → Áp dụng + nút chuyển bước (một nấc, tới/lui).
   Áp dụng có trong quy trình nhưng chưa làm: hiện mờ, nút khoá kèm lời giải thích. */

import { ArrowLeftOutlined, ArrowRightOutlined } from "@ant-design/icons";
import { App, Button, Steps, Tooltip } from "antd";

import { APPLY_READY, STAGES, STAGE_LABEL, type Stage } from "../../../../lib/floor-draft-flow-client";

const DESC: Record<Stage, string> = {
  nhap: "Soạn, chỉnh số phương án",
  du_thao: "Chốt số · chép hình dự thảo",
  to_trinh: "Soạn nội dung · AI · xuất Word/PDF",
  ap_dung: "Ghi giá sàn chính thức — sắp có",
};
const NEXT: Partial<Record<Stage, string>> = { nhap: "Chốt dự thảo", du_thao: "Lập tờ trình", to_trinh: "Áp dụng" };
const BACK_NOTE: Partial<Record<Stage, string>> = {
  du_thao: "Về bước Nháp để sửa số. Hình dự thảo sẽ dựng lại theo số mới; tỷ giá đã nhập vẫn giữ.",
  to_trinh: "Về bước Dự thảo. Nội dung tờ trình đã soạn được giữ nguyên để dùng lại.",
};
export const APPLY_HINT = "Bước Áp dụng chưa triển khai: sau khi Tổng Giám đốc duyệt, giá sàn chính thức vẫn nhập ở "
  + "màn Giá sàn Tập đoàn.";

type Props = { stage: Stage; canEdit: boolean; busy: boolean; onMove: (to: Stage) => void };

export default function FloorDraftSteps({ stage, canEdit, busy, onMove }: Props) {
  const { modal } = App.useApp();
  const i = STAGES.indexOf(stage);
  const prev = i > 0 ? STAGES[i - 1] : null;
  const next = i < STAGES.length - 1 ? STAGES[i + 1] : null;
  const nextBlocked = next === "ap_dung" && !APPLY_READY;

  const back = () => prev && modal.confirm({
    title: `Trả về bước ${STAGE_LABEL[prev]}?`, content: BACK_NOTE[stage], okText: "Trả về", cancelText: "Huỷ",
    onOk: () => onMove(prev),
  });

  return (
    <div className="card fd-steps">
      <Steps size="small" current={i} items={STAGES.map((s) => ({
        title: STAGE_LABEL[s], content: DESC[s],
        status: s === "ap_dung" && !APPLY_READY ? "wait" : undefined,
        disabled: true,
      }))} />
      {canEdit && (
        <div className="fd-steps-actions">
          {prev && <Button icon={<ArrowLeftOutlined />} disabled={busy} onClick={back}>Trả về {STAGE_LABEL[prev]}</Button>}
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
    </div>
  );
}
