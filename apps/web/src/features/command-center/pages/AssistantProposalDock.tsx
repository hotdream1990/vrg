/* Khung "Phương án giá sàn (nháp trong phiên)" cạnh màn chat Trợ lý AI.
   Màn rộng: cột phải, thu gọn được thành thanh mỏng. Màn hẹp: ngăn kéo (Drawer).
   Chỉ là nháp của phiên chat — không ghi biểu giá sàn; muốn giữ thì "Lưu bản nháp". */

import {
  CalculatorOutlined, CloseOutlined, DoubleLeftOutlined, DoubleRightOutlined, EyeOutlined, SaveOutlined, TableOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Popconfirm, Space, Tooltip } from "antd";
import { useEffect, useState } from "react";

import { type Proposal, previewProposalHtml } from "../../../lib/floor-proposal-client";
import { dmy } from "../../../lib/date";
import { useAuth } from "../../auth/AuthContext";
import FloorProposalPanel from "./components/FloorProposalPanel";
import type { ProposalApplier } from "./components/useProposalApply";
import SaveDraftModal from "./components/SaveDraftModal";
import ToTrinhPreview from "./components/ToTrinhPreview";

const TITLE = "Phương án giá sàn (nháp trong phiên)";
const DRAWER_MAX = 680;

type Props = {
  proposal: Proposal;
  applier: ProposalApplier;         // hàng đợi áp thay đổi của màn chat (chat chờ nó rảnh mới gửi)
  onClose: () => void;              // bỏ phương án của phiên
  locked: boolean;                  // Trợ lý đang xử lý → tạm khoá sửa tay
  mode: "side" | "drawer";
  width: number;                    // bề rộng cột phải (mode side)
  drawerOpen: boolean;
  onDrawerClose: () => void;
  revealKey: number;                // tăng khi Trợ lý vừa đổi phương án → tự mở lại cột nếu đang thu gọn
};

export default function AssistantProposalDock(
  { proposal, applier, onClose, locked, mode, width, drawerOpen, onDrawerClose, revealKey }: Props,
) {
  const { canEditCap } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [preview, setPreview] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const canSave = canEditCap("floor_suggest");

  useEffect(() => { setCollapsed(false); }, [revealKey]);

  // Ngăn kéo (portal, cùng z-index) sẽ phủ lên khung xem trước → đóng ngăn kéo trước khi mở.
  const openPreview = () => {
    if (mode === "drawer") onDrawerClose();
    setPreview(true);
  };

  // Chờ các lần sửa ô đang gửi xong → phương án mới nhất (xem trước / lưu đúng bản đang thấy).
  const latestProposal = async () => (await applier.whenIdle()) ?? proposal;

  // Trợ lý đang trả lời → khoá xem trước/lưu/đóng: bản AI sắp về sẽ khác bản đang nhìn.
  const saveBtn = canSave && (
    <Button type="primary" size="small" icon={<SaveOutlined />} disabled={locked} onClick={() => setSaveOpen(true)}>
      Lưu bản nháp
    </Button>
  );

  const body = (
    <>
      <div className="form-note" style={{ fontSize: 12, marginBottom: 8 }}>
        Chỉ là bản nháp trong phiên chat — chưa ghi vào biểu giá sàn.
      </div>
      <Space wrap size={6} style={{ marginBottom: 10 }}>
        <Button size="small" icon={<EyeOutlined />} disabled={locked} onClick={openPreview}>Xem trước tờ trình</Button>
        {saveBtn}
        <Popconfirm title="Đóng phương án?" okText="Đóng" cancelText="Huỷ"
          description="Phương án trong phiên sẽ bị bỏ. Bản nháp đã lưu không bị ảnh hưởng." onConfirm={onClose}>
          <Button size="small" icon={<CloseOutlined />} disabled={locked}>Đóng phương án</Button>
        </Popconfirm>
      </Space>
      <FloorProposalPanel proposal={proposal} applier={applier} locked={locked} />
    </>
  );

  const overlays = (
    <>
      {preview && (
        <ToTrinhPreview
          title={`Xem trước Tờ trình giá sàn — phương án ngày ${dmy(proposal.as_of)} (chưa lưu)`}
          load={async () => previewProposalHtml({ proposal: await latestProposal() })}
          extraActions={canSave && (
            <Button icon={<SaveOutlined />} disabled={locked} onClick={() => setSaveOpen(true)}>Lưu bản nháp</Button>
          )}
          onClose={() => setPreview(false)}
        />
      )}
      <SaveDraftModal open={saveOpen} resolveProposal={latestProposal} source="assistant"
        onClose={() => setSaveOpen(false)} />
    </>
  );

  if (mode === "drawer") {
    const size = Math.min(DRAWER_MAX, typeof window !== "undefined" ? window.innerWidth : DRAWER_MAX);
    return (
      <>
        <Drawer open={drawerOpen} onClose={onDrawerClose} size={size} title={TITLE}>{body}</Drawer>
        {overlays}
      </>
    );
  }

  if (collapsed) {
    return (
      <aside style={{ width: 40, flexShrink: 0, borderLeft: "1px solid var(--line)", display: "flex",
        flexDirection: "column", alignItems: "center", gap: 10, paddingTop: 4 }}>
        <Tooltip title="Mở phương án giá sàn" placement="left">
          <Button type="text" size="small" icon={<DoubleLeftOutlined />} onClick={() => setCollapsed(false)} />
        </Tooltip>
        <span onClick={() => setCollapsed(false)}
          style={{ writingMode: "vertical-rl", fontSize: 12.5, color: "var(--muted)", cursor: "pointer" }}>
          Phương án giá sàn
        </span>
        {overlays}
      </aside>
    );
  }

  return (
    <aside style={{ width, flexShrink: 0, minHeight: 0, overflowY: "auto", borderLeft: "1px solid var(--line)",
      paddingLeft: 14, paddingRight: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <b style={{ flex: 1, fontSize: 14.5 }}>{TITLE}</b>
        <Tooltip title="Thu gọn" placement="left">
          <Button type="text" size="small" icon={<DoubleRightOutlined />} onClick={() => setCollapsed(true)} />
        </Tooltip>
      </div>
      {body}
      {overlays}
    </aside>
  );
}

/** Nút ở khu công tắc: "Lập phương án giá sàn" (tự lập, không cần hỏi AI) · màn hẹp thì thêm
 *  "Xem phương án" mở ngăn kéo. Đã có phương án thì hỏi lại trước khi lập đè. */
export function ProposalStartButtons({ hasProposal, creating, disabled, narrow, onCreate, onOpenDrawer }: {
  hasProposal: boolean;
  creating: boolean;
  disabled: boolean;              // Trợ lý đang trả lời — lập mới lúc này sẽ bị bản AI đè
  narrow: boolean;
  onCreate: () => void;
  onOpenDrawer: () => void;
}) {
  const createBtn = (
    <Button type="link" size="small" icon={<CalculatorOutlined />} loading={creating} disabled={disabled}
      style={{ paddingInline: 0 }}
      onClick={hasProposal ? undefined : onCreate}>
      {hasProposal ? "Lập lại phương án" : "Lập phương án giá sàn"}
    </Button>
  );
  return (
    <>
      {hasProposal ? (
        <Popconfirm title="Lập phương án mới?" okText="Lập mới" cancelText="Huỷ" onConfirm={onCreate} disabled={disabled}
          description="Phương án đang sửa trong phiên sẽ bị thay (bản nháp đã lưu không bị ảnh hưởng).">
          {createBtn}
        </Popconfirm>
      ) : (
        <Tooltip title="Tự lập phương án giá sàn nháp để sửa tay — không cần hỏi Trợ lý.">{createBtn}</Tooltip>
      )}
      {hasProposal && narrow && (
        <Button size="small" icon={<TableOutlined />} onClick={onOpenDrawer}>Xem phương án</Button>
      )}
    </>
  );
}
