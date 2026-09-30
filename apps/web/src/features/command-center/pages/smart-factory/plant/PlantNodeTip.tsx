/* Nội dung Tooltip khi rê chuột lên thiết bị: từng tag · giá trị · giờ đọc (gọn). */

import type { PlantNode, PlantValues } from "../../../../../lib/smart-factory-client";
import { fmtNum, hms, withUnit } from "../smart-factory-format";
import { RUN_MIN, VALUE_DIGITS, valueOf } from "./plant-format";

type Row = { tag: string; text: string };

function tipRows(node: PlantNode, values: PlantValues): Row[] {
  const status = valueOf(values, node.status_tag);
  const digits = node.kind === "counter" ? 0 : VALUE_DIGITS;
  return [
    ...(node.status_tag
      ? [{ tag: node.status_tag, text: status == null ? "—" : status >= RUN_MIN ? "Chạy" : "Dừng" }]
      : []),
    ...(node.metrics ?? []).map((m) => ({ tag: m.tag, text: withUnit(fmtNum(valueOf(values, m.tag), digits), m.unit) })),
    ...(node.temps ?? []).map((t) => ({ tag: t.tag, text: withUnit(fmtNum(valueOf(values, t.tag), VALUE_DIGITS), "°C") })),
  ];
}

export default function PlantNodeTip({ node, values }: { node: PlantNode; values: PlantValues }) {
  return (
    <div className="pl-tip">
      <div className="pl-tip-title">{node.label}</div>
      {tipRows(node, values).map((r) => (
        <div key={r.tag} className="pl-tip-row">
          <span>{r.tag}</span>
          <b>{r.text}</b>
          <span className="pl-tip-at">{hms(values[r.tag]?.at)}</span>
        </div>
      ))}
    </div>
  );
}
