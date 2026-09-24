/* Khối diễn giải của tờ trình (mục 1 / mục 2) — danh sách đoạn, mỗi đoạn một ô sửa, thêm/xoá đoạn. */

import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Input, Tooltip } from "antd";

// Khớp giới hạn server (schemas/floor_proposal.py): tối đa 20 đoạn, mỗi đoạn 1.500 ký tự.
const MAX_PARAGRAPHS = 20;
const MAX_PARAGRAPH_LEN = 1500;

type Props = {
  title: string;
  hint?: string;
  paragraphs: string[];
  onChange: (next: string[]) => void;
  readOnly?: boolean;
};

export default function FloorDraftNarrative({ title, hint, paragraphs, onChange, readOnly }: Props) {
  const setAt = (i: number, v: string) => onChange(paragraphs.map((p, j) => (j === i ? v : p)));
  const removeAt = (i: number) => onChange(paragraphs.filter((_, j) => j !== i));

  return (
    <div className="card" style={{ minWidth: 0 }}>
      <div className="card-head" style={{ marginBottom: 6 }}><h3 style={{ margin: 0 }}>{title}</h3></div>
      {hint && !readOnly && <div className="form-note" style={{ fontSize: 12.5, marginBottom: 8 }}>{hint}</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {paragraphs.length === 0 && (
          <span style={{ color: "var(--muted)", fontSize: 13 }}>Chưa có đoạn nào.</span>
        )}
        {paragraphs.map((p, i) => (
          <div key={i} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
            <Input.TextArea value={p} readOnly={readOnly} autoSize={{ minRows: 1, maxRows: 8 }}
              maxLength={MAX_PARAGRAPH_LEN} onChange={(e) => setAt(i, e.target.value)} />
            {!readOnly && (
              <Tooltip title="Xoá đoạn này">
                <Button type="text" danger icon={<DeleteOutlined />} onClick={() => removeAt(i)} />
              </Tooltip>
            )}
          </div>
        ))}
      </div>
      {!readOnly && (
        <Button type="dashed" size="small" icon={<PlusOutlined />} style={{ marginTop: 8 }}
          disabled={paragraphs.length >= MAX_PARAGRAPHS} onClick={() => onChange([...paragraphs, ""])}>
          Thêm đoạn
        </Button>
      )}
    </div>
  );
}
