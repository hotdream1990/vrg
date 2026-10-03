/* Bảng PHƯƠNG ÁN GIÁ SÀN sửa được — dùng chung cho Trợ lý AI (nháp trong phiên) và màn soạn Bản
   nháp tờ trình. Mọi thay đổi (sửa ô, ±bước, làm lại, hoàn tác) đi qua hàng đợi `applier`
   (`POST /api/floor-proposal/apply`) của màn cha rồi thay bằng phương án server trả về — FE không tự
   tính delta/nội địa. Hàng đợi ở màn cha để màn cha chờ được nó rảnh trước khi gửi chat / lưu. */

import { DownOutlined, MinusOutlined, PlusOutlined, ReloadOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, Collapse, Dropdown, Space, Spin, Tooltip } from "antd";

import type { Proposal, ProposalChange, ProposalRow } from "../../../../lib/floor-proposal-client";
import { dmy } from "../../../../lib/date";
import { FLOOR_MODELS } from "../../../../lib/floor-suggest-client";
import { DeltaText, GradeCell, OriginTag, ProposalNumCell, fmtVi } from "./FloorProposalCells";
import type { ProposalApplier } from "./useProposalApply";
import "../../../bulletin/bulletin.css";
import "../floor-draft.css";

type Props = {
  proposal: Proposal;
  applier: ProposalApplier;     // từ useProposalApply(proposal, onChange) ở màn cha
  readOnly?: boolean;   // chỉ xem hẳn (vd Lãnh đạo Tập đoàn) — ẩn thanh công cụ
  locked?: boolean;     // tạm khoá (vd Trợ lý đang xử lý) — tránh sửa tay rồi bị bản AI đè mất
};

const TH: React.CSSProperties = { padding: "7px 6px", fontSize: 10.5, whiteSpace: "nowrap" };
const TD: React.CSSProperties = { padding: "5px 6px", fontSize: 12.5 };
const MUTED: React.CSSProperties = { ...TD, color: "var(--muted)", textAlign: "right", whiteSpace: "nowrap" };
const STICKY: React.CSSProperties = { position: "sticky", left: 0, zIndex: 1, background: "var(--panel)" };
const CHANGED_BG = "#eef7fc";   // dòng khác mức mô hình — màu ĐỤC để cột dính (sticky) cùng màu cả dòng
const LOG_BY: Record<string, string> = { ai: "Trợ lý AI", manual: "Sửa tay", system: "Hệ thống" };

const ALL: ProposalChange["grades"] = ["all"];

/** Dòng lệch khỏi mức mô hình (chỉ so khi mô hình có số). */
const differsFromModel = (r: ProposalRow) =>
  (r.model_fob != null && r.fob !== r.model_fob) || (r.model_vnd != null && r.vnd !== r.model_vnd);

/** ISO → "HH:mm DD/MM". */
function hmDm(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth() + 1)}`;
}

export default function FloorProposalPanel({ proposal, applier, readOnly, locked }: Props) {
  const { apply, busy } = applier;
  const frozen = Boolean(readOnly || locked);
  const modelLabel = FLOOR_MODELS.find((m) => m.value === proposal.model)?.short ?? proposal.model;

  const setCell = (row: ProposalRow, field: "fob" | "vnd") => (value: number) =>
    apply([{ grades: [row.grade], op: "set", value, field }]);

  const resetItems = [
    { key: "reset_model", label: "Mức mô hình" },
    { key: "reset_current", label: "Giá hiện hành (lần ban hành trước)" },
  ];

  return (
    <div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
        Ngày tờ trình <b>{dmy(proposal.as_of)}</b> · so với lần ban hành <b>{dmy(proposal.prev_as_of)}</b>
        {" · "}Mô hình: {modelLabel} · Xuất phát: {proposal.base === "current" ? "giá hiện hành" : "mức mô hình"}
      </div>

      {!readOnly && (
        <Space wrap size={6} style={{ marginBottom: 8 }}>
          <Tooltip title="Bỏ thay đổi gần nhất">
            <Button size="small" icon={<UndoOutlined />} disabled={frozen || proposal.log.length === 0}
              onClick={() => apply([{ op: "undo" }])}>Hoàn tác</Button>
          </Tooltip>
          <Dropdown disabled={frozen} trigger={["click"]}
            menu={{ items: resetItems, onClick: ({ key }) => apply([{ grades: ALL, op: key as ProposalChange["op"] }]) }}>
            <Button size="small" icon={<ReloadOutlined />} disabled={frozen}>Làm lại từ <DownOutlined /></Button>
          </Dropdown>
          <Tooltip title="Giảm mọi dòng 1 bước ban hành (5 USD/tấn · 50.000 đ/tấn)">
            <Button size="small" icon={<MinusOutlined />} disabled={frozen}
              onClick={() => apply([{ grades: ALL, op: "step", value: -1 }])}>1 bước</Button>
          </Tooltip>
          <Tooltip title="Tăng mọi dòng 1 bước ban hành (5 USD/tấn · 50.000 đ/tấn)">
            <Button size="small" icon={<PlusOutlined />} disabled={frozen}
              onClick={() => apply([{ grades: ALL, op: "step", value: 1 }])}>1 bước</Button>
          </Tooltip>
          {busy && <Spin size="small" />}
          {locked && <span style={{ fontSize: 12, color: "var(--muted)" }}>Trợ lý đang xử lý — tạm khoá bảng.</span>}
        </Space>
      )}

      <div style={{ overflowX: "auto", border: "1px solid var(--line)", borderRadius: 8 }}>
        <table style={{ fontSize: 12.5, minWidth: 900 }}>
          <thead>
            <tr>
              <th style={{ ...TH, ...STICKY }}>Chủng loại</th>
              <th className="r" style={TH}>Lần trước FOB</th>
              <th className="r" style={TH}>Mô hình FOB</th>
              <th className="r" style={TH}>Phương án FOB</th>
              <th className="r" style={TH}>±</th>
              <th className="r" style={TH}>Lần trước nội địa</th>
              <th className="r" style={TH}>Mô hình nội địa</th>
              <th className="r" style={TH}>Phương án nội địa</th>
              <th className="r" style={TH}>±</th>
              <th style={TH}>Nguồn</th>
            </tr>
          </thead>
          <tbody>
            {proposal.rows.map((r) => {
              const bg = differsFromModel(r) ? CHANGED_BG : undefined;
              const vndOnly = r.unit === "VNĐ/T";
              return (
                <tr key={r.grade} style={{ background: bg }}>
                  <td style={{ ...TD, ...STICKY, background: bg ?? "var(--panel)" }}>
                    <GradeCell row={r} />
                  </td>
                  <td style={MUTED}>{fmtVi(r.prev_fob)}</td>
                  <td style={MUTED}>{fmtVi(r.model_fob)}</td>
                  <td style={{ ...TD, width: 96 }}>
                    {vndOnly ? <div style={{ textAlign: "right", color: "var(--muted)" }}>—</div> : (
                      <ProposalNumCell value={r.fob} prev={r.prev_fob} readOnly={frozen}
                        syncKey={proposal} onCommit={setCell(r, "fob")} />
                    )}
                  </td>
                  <td className="r" style={TD}><DeltaText delta={r.fob_delta} pct={r.fob_delta_pct} /></td>
                  <td style={MUTED}>{fmtVi(r.prev_vnd)}</td>
                  <td style={MUTED}>{fmtVi(r.model_vnd)}</td>
                  <td style={{ ...TD, width: 116 }}>
                    <ProposalNumCell value={r.vnd} prev={r.prev_vnd} readOnly={frozen}
                      syncKey={proposal} onCommit={setCell(r, "vnd")} />
                  </td>
                  <td className="r" style={TD}><DeltaText delta={r.vnd_delta} pct={r.vnd_delta_pct} /></td>
                  <td style={TD}><OriginTag origin={r.origin} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 6 }}>
        FOB: USD/tấn · Nội địa: đồng/tấn. Dòng tô nền = khác mức mô hình.
      </div>
      {!frozen && (
        <div className="form-note" style={{ fontSize: 11.5, marginTop: 2 }}>
          Gõ xong bấm Enter hoặc bấm ra ngoài để áp dụng. Sửa FOB thì nội địa tự tính lại theo tỉ lệ, trừ khi nội địa
          đã sửa tay.
        </div>
      )}

      <Collapse size="small" ghost style={{ marginTop: 6 }} items={[{
        key: "log",
        label: `Nhật ký chỉnh sửa (${proposal.log.length})`,
        children: proposal.log.length === 0
          ? <span style={{ color: "var(--muted)", fontSize: 12.5 }}>Chưa có chỉnh sửa nào.</span>
          : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12.5 }}>
              {[...proposal.log].reverse().map((l, i) => (
                <div key={`${l.at}-${i}`}>
                  <span style={{ color: "var(--muted)", marginRight: 6 }}>{hmDm(l.at)} · {LOG_BY[l.by] ?? l.by}:</span>
                  {l.text}
                </div>
              ))}
            </div>
          ),
      }]} />
    </div>
  );
}
