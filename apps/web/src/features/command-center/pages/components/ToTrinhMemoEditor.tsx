/* Soạn nội dung tờ trình theo mẫu mới (Tờ trình 54/TTr-TTKD): số · ngày · mục I (nguồn + diễn giải
   từng sàn) · mục II (tiêu đề phụ + ghi chú + diễn giải) · cung – cầu · tồn kho · câu kính trình · người ký.
   Bảng số (mục I, II, phương án) do hệ thống dựng — không sửa ở đây. */

import { Input } from "antd";

import type { Memo, Signers } from "../../../../lib/floor-draft-flow-client";
import DateInput from "../../sections/DateInput";
import MemoParaList from "./MemoParaList";

type Props = { memo: Memo; readOnly: boolean; onChange: (m: Memo) => void };

const LABEL: React.CSSProperties = { display: "block", fontSize: 12.5, color: "var(--muted)", marginBottom: 4 };
const SIGN_ROWS: [keyof Signers, keyof Signers, string][] = [
  ["left_role", "left_name", "Bên trái"], ["right_role", "right_name", "Bên phải"],
  ["approver_role", "approver_name", "Người duyệt"],
];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label style={{ display: "block" }}><span style={LABEL}>{label}</span>{children}</label>;
}

export default function ToTrinhMemoEditor({ memo, readOnly, onChange }: Props) {
  const set = (p: Partial<Memo>) => onChange({ ...memo, ...p });
  const area = (key: "futures_note" | "physical_note" | "intro", rows = 2) => (
    <Input.TextArea value={memo[key]} readOnly={readOnly} maxLength={1500} autoSize={{ minRows: rows, maxRows: 8 }}
      onChange={(e) => set({ [key]: e.target.value } as Partial<Memo>)} />
  );

  return (
    <div className="fd-memo">
      <div className="card fd-grid">
        <Field label="Số tờ trình">
          <Input value={memo.so} readOnly={readOnly} maxLength={40} placeholder="vd 54/TTr-TTKD"
            onChange={(e) => set({ so: e.target.value })} />
        </Field>
        <Field label="Ngày ghi trên tờ trình">
          <DateInput value={memo.sign_date} readOnly={readOnly} onChange={(iso) => iso && set({ sign_date: iso })} />
        </Field>
      </div>

      <div className="card">
        <h3 className="fd-sec">I. So sánh giá các sàn kỳ hạn</h3>
        <Field label="Dòng nguồn dưới bảng (in nghiêng, chữ nhỏ)">{area("futures_note")}</Field>
        <MemoParaList title="Diễn giải theo từng sàn" readOnly={readOnly} items={memo.futures}
          leadPlaceholder="Nhãn in đậm-nghiêng, vd: SGX (Singapore Exchange/SICOM) – RSS3 & TSR20:"
          hint="Mỗi đoạn in dưới bảng giá các sàn, mở đầu bằng nhãn sàn." onChange={(futures) => set({ futures })} />
      </div>

      <div className="card">
        <h3 className="fd-sec">II. So sánh giá các sàn vật chất (Thái Lan, Mã Lai, Indonesia)</h3>
        <Field label="Phần sau tiêu đề mục II">
          <Input value={memo.physical_title} readOnly={readOnly} maxLength={300}
            placeholder="vd tham chiếu giá nguồn từ ANRPC các ngày 21/9 và 22/9"
            onChange={(e) => set({ physical_title: e.target.value })} />
        </Field>
        <div style={{ height: 10 }} />
        <Field label="Ghi chú ngay dưới bảng (tuỳ chọn)">{area("physical_note")}</Field>
        <MemoParaList title="Diễn giải thị trường vật chất" readOnly={readOnly} items={memo.physical}
          onChange={(physical) => set({ physical })} />
        <MemoParaList title="Cán cân cung – cầu, triển vọng" readOnly={readOnly} items={memo.outlook}
          hint="Nên kết bằng cơ sở đề xuất điều chỉnh giá sàn lần này." onChange={(outlook) => set({ outlook })} />
      </div>

      <div className="card">
        <h3 className="fd-sec">Tồn kho và đề xuất</h3>
        <div className="fd-grid">
          <Field label="Tồn kho — phần in đậm">
            <Input value={memo.inventory.lead} readOnly={readOnly} maxLength={200}
              onChange={(e) => set({ inventory: { ...memo.inventory, lead: e.target.value } })} />
          </Field>
          <Field label="Tồn kho — phần tiếp theo">
            <Input value={memo.inventory.text} readOnly={readOnly} maxLength={4000}
              onChange={(e) => set({ inventory: { ...memo.inventory, text: e.target.value } })} />
          </Field>
        </div>
        <div style={{ height: 10 }} />
        <Field label="Câu kính trình (ngay trên bảng giá đề xuất)">{area("intro", 3)}</Field>
      </div>

      <div className="card">
        <h3 className="fd-sec">Người ký</h3>
        <div className="fd-grid fd-grid-3">
          {SIGN_ROWS.map(([role, name, label]) => (
            <div key={role} style={{ display: "grid", gap: 6 }}>
              <Field label={`${label} — chức danh (Enter = xuống dòng)`}>
                <Input.TextArea value={memo.signers[role]} readOnly={readOnly} maxLength={120} autoSize={{ minRows: 1, maxRows: 3 }}
                  onChange={(e) => set({ signers: { ...memo.signers, [role]: e.target.value } })} />
              </Field>
              <Field label={`${label} — họ tên`}>
                <Input value={memo.signers[name]} readOnly={readOnly} maxLength={120}
                  onChange={(e) => set({ signers: { ...memo.signers, [name]: e.target.value } })} />
              </Field>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
