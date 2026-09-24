/* Hai công tắc giới hạn Trợ lý AI (Nguồn tham chiếu · Mức tư vấn) + lớp nâng cao chọn từng gói
   kỹ năng + bảng năng lực. Tách khỏi AssistantPage để màn chat gọn. */

import { InfoCircleOutlined, LockOutlined, SettingOutlined, StopOutlined } from "@ant-design/icons";
import { Button, Popover, Segmented, Tag, Tooltip } from "antd";
import { useMemo } from "react";

import type { AdviceLevel, SkillPack } from "../../../lib/assistant-client";
import { CapabilityButton } from "./AssistantCapabilities";

/** Nguồn tham chiếu — "Trợ lý được đọc tới đâu". `custom` = người dùng tự bật/tắt từng gói. */
export type Scope = "basic" | "extended" | "custom";

const UNAVAILABLE_HINT = "Không khả dụng với tài khoản của bạn hoặc đã tắt trong Cấu hình hệ thống";

/* ── Hai công tắc giới hạn Trợ lý ────────────────────────────────────────────────────────── */

const SCOPE_OPTIONS: { value: Scope; label: string; hint: string }[] = [
  { value: "basic", label: "Cơ bản",
    hint: "Chỉ nhóm nền: thị trường thế giới và giá sàn." },
  { value: "extended", label: "Mở rộng",
    hint: "Thêm số liệu nội bộ Tập đoàn và số liệu đơn vị thành viên." },
];

const CUSTOM_SCOPE_OPTION: { value: Scope; label: string; hint: string } = {
  value: "custom", label: "Tuỳ chỉnh",
  hint: "Bạn đang tự bật/tắt từng nhóm dữ liệu ở phần Nâng cao.",
};

export const ADVICE_OPTIONS: { value: AdviceLevel; label: string; hint: string; note: string }[] = [
  { value: "data", label: "Chỉ tra số",
    hint: "Trợ lý không đưa khuyến nghị nâng/giữ/hạ, chỉ trả số liệu.",
    note: "Trợ lý chỉ trả số liệu và diễn giải số liệu, không đưa khuyến nghị nâng/giữ/hạ giá sàn." },
  { value: "model", label: "Theo mô hình",
    hint: "Trợ lý đưa đúng đề xuất của mô hình, không tự điều chỉnh.",
    note: "Trợ lý nêu đúng mức mô hình gợi ý, không tự điều chỉnh theo bối cảnh. Mọi khuyến nghị chỉ để tham khảo, không ghi vào biểu giá sàn." },
  { value: "adjusted", label: "Có điều chỉnh",
    hint: "Trợ lý được lệch khỏi mức mô hình dựa trên bối cảnh, phải giải trình.",
    note: "Trợ lý có thể đề xuất khác mức mô hình và phải nêu rõ lý do. Mọi khuyến nghị chỉ để tham khảo, không ghi vào biểu giá sàn." },
];

/* CheckableTag của antd v6 để chip CHƯA chọn nền + viền trong suốt → nhìn như chữ trơ, không ra
   hình viên chip. Vẽ lại viền cho 2 trạng thái tắt để cả hàng đọc được là "các nút bật/tắt". */
const CHIP_BASE: React.CSSProperties = { padding: "3px 10px", fontSize: 13, borderRadius: 8 };
const CHIP_OFF: React.CSSProperties = { ...CHIP_BASE, border: "1px solid rgba(125,180,140,.45)", background: "rgba(125,180,140,.10)" };
const CHIP_LOCKED: React.CSSProperties = { ...CHIP_BASE, cursor: "default" };
const CHIP_UNAVAILABLE: React.CSSProperties = { ...CHIP_BASE, border: "1px dashed rgba(140,140,140,.45)", opacity: 0.6 };

/** Hàng chip chọn gói kỹ năng (lớp NÂNG CAO, trong Popover).
 *  3 trạng thái: nền (khoá) · bật/tắt được · không khả dụng (mờ). */
function SkillPackChips({ packs, selected, onToggle }: {
  packs: SkillPack[];
  selected: string[];
  onToggle: (pack: SkillPack, checked: boolean) => void;
}) {
  if (packs.length === 0) return null; // API lỗi hoặc chưa tải xong → ẩn hàng chip, không chặn chat

  return (
    <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
      {packs.map((pack) => {
        const checked = selected.includes(pack.key);
        const base = `${pack.desc} (${pack.tools} công cụ)`;
        if (pack.core) {
          return (
            <Tooltip key={pack.key} title={`${base} · Nhóm nền — luôn bật.`}>
              <Tag.CheckableTag
                checked
                icon={<LockOutlined />}
                onChange={() => { /* gói nền: khoá, bấm không đổi trạng thái */ }}
                style={CHIP_LOCKED}
              >
                {pack.label}
              </Tag.CheckableTag>
            </Tooltip>
          );
        }
        if (!pack.active) {
          return (
            <Tooltip key={pack.key} title={`${base} · ${UNAVAILABLE_HINT}.`}>
              <Tag.CheckableTag
                checked={false}
                disabled
                icon={<StopOutlined />}
                style={CHIP_UNAVAILABLE}
              >
                {pack.label}
              </Tag.CheckableTag>
            </Tooltip>
          );
        }
        return (
          <Tooltip key={pack.key} title={base}>
            <Tag.CheckableTag
              checked={checked}
              onChange={(next) => onToggle(pack, next)}
              style={checked ? CHIP_BASE : CHIP_OFF}
            >
              {pack.label}
            </Tag.CheckableTag>
          </Tooltip>
        );
      })}
    </div>
  );
}

const SWITCH_LABEL: React.CSSProperties = { fontSize: 12.5, opacity: 0.7 };

/** Nhãn Segmented kèm Tooltip giải thích — người dùng hiểu ngay "cho AI đi xa tới đâu". */
function tipOptions<T extends string>(opts: { value: T; label: string; hint: string }[]) {
  return opts.map((o) => ({
    value: o.value,
    label: <Tooltip title={o.hint}><span>{o.label}</span></Tooltip>,
  }));
}

/** Hai công tắc + lối vào lớp nâng cao (chi tiết từng gói kỹ năng) + bảng năng lực. */
export function AssistantControls({ packs, limits, packsFailed, scope, advice, selected,
                                    onScope, onAdvice, onToggle, extra }: {
  packs: SkillPack[];
  limits: string[];
  packsFailed: boolean;
  scope: Scope;
  advice: AdviceLevel;
  selected: string[];
  onScope: (next: Scope) => void;
  onAdvice: (next: AdviceLevel) => void;
  onToggle: (pack: SkillPack, checked: boolean) => void;
  extra?: React.ReactNode;   // nút thêm cạnh "Nâng cao" (vd Lập phương án giá sàn)
}) {
  // "Tuỳ chỉnh" chỉ hiện khi người dùng đã tự chỉnh chip — công tắc thường chỉ có 2 lựa chọn.
  const scopeOptions = useMemo(
    () => tipOptions(scope === "custom" ? [...SCOPE_OPTIONS, CUSTOM_SCOPE_OPTION] : SCOPE_OPTIONS),
    [scope],
  );
  const adviceOptions = useMemo(() => tipOptions(ADVICE_OPTIONS), []);
  const note = ADVICE_OPTIONS.find((o) => o.value === advice)?.note ?? "";

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px 14px" }}>
        <span style={SWITCH_LABEL}>Nguồn tham chiếu:</span>
        <Segmented size="small" value={scope} options={scopeOptions}
                   onChange={(v) => onScope(v as Scope)} />
        <span style={SWITCH_LABEL}>Mức tư vấn:</span>
        <Segmented size="small" value={advice} options={adviceOptions}
                   onChange={(v) => onAdvice(v as AdviceLevel)} />
        {packs.length > 0 && (
          <Popover
            trigger="click"
            placement="bottomLeft"
            title="Chi tiết nhóm dữ liệu"
            content={(
              <div style={{ maxWidth: 460 }}>
                <div style={{ ...SWITCH_LABEL, marginBottom: 8 }}>
                  Bật/tắt từng nhóm Trợ lý được phép tra cứu. Nhóm nền luôn bật; nhóm mờ là không
                  khả dụng với tài khoản của bạn.
                </div>
                <SkillPackChips packs={packs} selected={selected} onToggle={onToggle} />
              </div>
            )}
          >
            <Button type="link" size="small" icon={<SettingOutlined />} style={{ paddingInline: 0 }}>
              Nâng cao
            </Button>
          </Popover>
        )}
        {extra}
        <CapabilityButton packs={packs} limits={limits} selected={selected} failed={packsFailed} />
      </div>
      <div style={{ fontSize: 12, opacity: 0.65, marginTop: 6 }}>
        <InfoCircleOutlined style={{ marginRight: 6 }} />{note}
      </div>
    </div>
  );
}
