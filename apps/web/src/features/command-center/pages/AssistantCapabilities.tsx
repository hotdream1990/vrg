/* Bảng "Trợ lý làm được gì?" — nút + ngăn kéo liệt kê nhóm dữ liệu Trợ lý chạm tới được,
   trạng thái từng nhóm (luôn bật · đang bật · đã tắt · thiếu quyền) và những việc chưa làm được.
   Tách khỏi AssistantPage vì đây là khối tự chứa, chỉ cần dữ liệu gói kỹ năng truyền vào. */

import {
  CheckCircleOutlined, LockOutlined, MinusCircleOutlined, QuestionCircleOutlined, StopOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Alert, Button, Drawer, Spin, Tag, Tooltip } from "antd";
import { useState } from "react";

import { type SkillPack, type SkillTool } from "../../../lib/assistant-client";

/** Tên màn hình tương ứng mã quyền — hiện mã thô (`unit_daily`) cho người dùng là vô nghĩa. */
const CAP_LABELS: Record<string, string> = {
  unit_daily: "Báo cáo tiêu thụ - tồn kho",
  sales_contract: "Hợp đồng bán hàng",
};

/** Mệnh đề đầu của mô tả thường đủ làm tiêu đề — cắt ở dấu ngăn câu đầu tiên. */
const TOOL_LABEL_CUTS = [" — ", " – ", ": ", " ("];
const TOOL_LABEL_MAX = 56;

function fallbackToolLabel(desc: string): string {
  const text = desc.trim();
  const cuts = TOOL_LABEL_CUTS.map((sep) => text.indexOf(sep)).filter((i) => i > 0);
  const cut = cuts.length > 0 ? Math.min(...cuts) : text.length;
  if (cut <= TOOL_LABEL_MAX) return text.slice(0, cut);
  return `${text.slice(0, TOOL_LABEL_MAX).trimEnd()}…`;
}

/** Nhãn hiển thị của công cụ: ưu tiên nhãn do BACKEND gửi (một nguồn duy nhất, không trôi khi
 *  đổi tên công cụ); backend chưa kịp đặt nhãn thì tự rút gọn mô tả. KHÔNG bao giờ hiện tên hàm. */
const toolLabel = (item: SkillTool) => item.label || fallbackToolLabel(item.desc);

/** Vì sao Trợ lý đang thấy / không thấy nhóm dữ liệu này — 4 trạng thái, mỗi cái một lý do rõ. */
function packState(pack: SkillPack, selected: string[]) {
  if (!pack.active) {
    if (pack.cap) {
      return {
        text: `Cần quyền "${CAP_LABELS[pack.cap] ?? pack.cap}"`,
        hint: `Mã quyền: ${pack.cap}. Liên hệ quản trị viên để được cấp.`,
        color: "warning" as string | undefined, icon: <LockOutlined />, dim: true,
      };
    }
    return {
      text: "Đã tắt trong Cấu hình hệ thống",
      hint: "Quản trị viên đã tắt nhóm dữ liệu này cho toàn hệ thống.",
      color: undefined as string | undefined, icon: <StopOutlined />, dim: true,
    };
  }
  if (pack.core) {
    return {
      text: "Luôn bật", hint: "Nhóm nền — không tắt được.",
      color: "green" as string | undefined, icon: <CheckCircleOutlined />, dim: false,
    };
  }
  if (selected.includes(pack.key)) {
    return {
      text: "Đang bật", hint: "Trợ lý đang được phép tra nhóm dữ liệu này.",
      color: "green" as string | undefined, icon: <CheckCircleOutlined />, dim: false,
    };
  }
  return {
    text: "Đã tắt trong phiên này",
    hint: "Trợ lý KHÔNG thấy nhóm số liệu này — bật lại ở phần Nâng cao.",
    color: undefined as string | undefined, icon: <MinusCircleOutlined />, dim: false,
  };
}

const PACK_CARD: React.CSSProperties = {
  border: "1px solid rgba(125,180,140,.32)", borderRadius: 10, padding: "10px 12px",
  marginBottom: 10, background: "rgba(125,180,140,.08)",
};

/** Một nhóm dữ liệu: tên · mô tả · số công cụ · trạng thái · danh sách việc tra được. */
function PackCapability({ pack, selected }: { pack: SkillPack; selected: string[] }) {
  const state = packState(pack, selected);
  const items = pack.items ?? [];

  return (
    <div style={{ ...PACK_CARD, opacity: state.dim ? 0.75 : 1 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <b style={{ fontSize: 14 }}>{pack.label}</b>
        <Tooltip title={state.hint}>
          <Tag color={state.color} icon={state.icon} style={{ marginInlineEnd: 0 }}>
            {state.text}
          </Tag>
        </Tooltip>
      </div>
      <div style={{ fontSize: 12.5, opacity: 0.7, marginTop: 4 }}>
        {pack.desc} · {pack.tools} công cụ
      </div>
      {items.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 7 }}>
          {items.map((item) => (
            <div key={item.name} style={{ paddingLeft: 10, borderLeft: "2px solid rgba(125,180,140,.45)" }}>
              <div style={{ fontSize: 13 }}>{toolLabel(item)}</div>
              <div style={{ fontSize: 12, opacity: 0.65, lineHeight: 1.45 }}>{item.desc}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const CAPABILITY_SECTION: React.CSSProperties = { fontSize: 13.5, fontWeight: 600, margin: "0 0 8px" };

/** Ruột bảng năng lực: đang tải · lỗi · hoặc 2 phần "tra cứu được" và "chưa làm được". */
function CapabilityBody({ packs, limits, selected, failed }: {
  packs: SkillPack[];
  limits: string[];
  selected: string[];
  failed: boolean;
}) {
  if (failed) {
    return (
      <Alert
        type="warning" showIcon
        message="Chưa lấy được danh sách khả năng của Trợ lý"
        description="Vui lòng thử lại sau ít phút. Việc hỏi đáp trên màn chat không bị ảnh hưởng."
      />
    );
  }
  if (packs.length === 0) {
    return <div style={{ textAlign: "center", padding: 32 }}><Spin /></div>;
  }

  return (
    <>
      <div style={{ fontSize: 12.5, opacity: 0.7, marginBottom: 12 }}>
        Trợ lý chỉ trả lời dựa trên số liệu thật đã có trong hệ thống. Dưới đây là những nhóm dữ
        liệu Trợ lý chạm tới được và những việc Trợ lý chưa làm được.
      </div>

      <h4 style={CAPABILITY_SECTION}>Trợ lý tra cứu được</h4>
      {packs.map((pack) => <PackCapability key={pack.key} pack={pack} selected={selected} />)}

      {limits.length > 0 && (
        <>
          <h4 style={{ ...CAPABILITY_SECTION, marginTop: 18 }}>Chưa làm được</h4>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {limits.map((limit) => (
              <div key={limit} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.5, opacity: 0.85 }}>
                <WarningOutlined style={{ color: "var(--warn)", marginTop: 3, flexShrink: 0 }} />
                <span>{limit}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}

const CAPABILITY_DRAWER_WIDTH = 560;

/** Nút mở bảng năng lực. Luôn hiện — kể cả khi chưa lấy được `/packs`, mở ra sẽ báo lý do. */
export function CapabilityButton({ packs, limits, selected, failed }: {
  packs: SkillPack[];
  limits: string[];
  selected: string[];
  failed: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button type="link" size="small" icon={<QuestionCircleOutlined />}
              style={{ paddingInline: 0 }} onClick={() => setOpen(true)}>
        Trợ lý làm được gì?
      </Button>
      <Drawer
        open={open} onClose={() => setOpen(false)}
        width={CAPABILITY_DRAWER_WIDTH} title="Trợ lý làm được gì?"
      >
        <CapabilityBody packs={packs} limits={limits} selected={selected} failed={failed} />
      </Drawer>
    </>
  );
}
