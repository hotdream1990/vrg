/* Danh sách đoạn văn của tờ trình: mỗi đoạn = nhãn in đậm-nghiêng (tuỳ chọn) + nội dung.
   Thêm · xoá · đổi thứ tự. Ô sửa được luôn có viền (dễ nhận ra chỗ nào sửa được). */

import { ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Input, Tooltip } from "antd";

import type { Para } from "../../../../lib/floor-draft-flow-client";

type Props = {
  title: string;
  hint?: string;
  items: Para[];
  readOnly?: boolean;
  leadPlaceholder?: string;      // không truyền = đoạn không có nhãn
  onChange: (items: Para[]) => void;
};

export default function MemoParaList({ title, hint, items, readOnly, leadPlaceholder, onChange }: Props) {
  const set = (i: number, p: Partial<Para>) => onChange(items.map((x, j) => (j === i ? { ...x, ...p } : x)));
  const swap = (i: number, j: number) => {
    const next = [...items];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  };

  return (
    <div className="fd-paras">
      <div className="fd-paras-head">
        <b>{title}</b>
        {hint && <span className="form-note" style={{ fontSize: 12 }}>{hint}</span>}
      </div>
      {items.length === 0 && <div style={{ color: "var(--muted)", fontSize: 12.5 }}>Chưa có đoạn nào.</div>}
      {items.map((p, i) => (
        <div key={i} className="fd-para">
          <div className="fd-para-body">
            {(leadPlaceholder || p.lead) && (
              <Input value={p.lead} readOnly={readOnly} maxLength={200} placeholder={leadPlaceholder}
                className="fd-lead-input" onChange={(e) => set(i, { lead: e.target.value })} />
            )}
            <Input.TextArea value={p.text} readOnly={readOnly} maxLength={4000} autoSize={{ minRows: 2, maxRows: 12 }}
              onChange={(e) => set(i, { text: e.target.value })} />
          </div>
          {!readOnly && (
            <div className="fd-para-tools">
              <Tooltip title="Lên"><Button size="small" type="text" icon={<ArrowUpOutlined />} disabled={i === 0}
                onClick={() => swap(i, i - 1)} /></Tooltip>
              <Tooltip title="Xuống"><Button size="small" type="text" icon={<ArrowDownOutlined />}
                disabled={i === items.length - 1} onClick={() => swap(i, i + 1)} /></Tooltip>
              <Tooltip title="Xoá đoạn"><Button size="small" type="text" danger icon={<DeleteOutlined />}
                onClick={() => onChange(items.filter((_, j) => j !== i))} /></Tooltip>
            </div>
          )}
        </div>
      ))}
      {!readOnly && (
        <Button size="small" icon={<PlusOutlined />} onClick={() => onChange([...items, { lead: "", text: "" }])}>
          Thêm đoạn
        </Button>
      )}
    </div>
  );
}
